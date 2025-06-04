import logging
import os
from typing import Dict, Optional, List, Any, BinaryIO
from fastapi import HTTPException, UploadFile, File
import tldextract
import mimetypes
import tempfile
import shutil

from app.config import FormConfig
from app.storage import FormSubmission, StorageInterface
from app.email_sender import EmailSender
from app.metrics import (
    increment_form_submission,
    increment_email_send,
    track_in_progress,
)

logger = logging.getLogger(__name__)


class FormHandler:
    def __init__(self, storage: StorageInterface, email_sender: EmailSender):
        self.storage = storage
        self.email_sender = email_sender

    def get_form_config(self, form_id: str, forms: Dict[str, FormConfig]) -> FormConfig:
        """Get form configuration by ID."""
        if form_id not in forms:
            logger.warning(f"Form ID not found: {form_id}")
            raise HTTPException(status_code=404, detail="Form not found")
        return forms[form_id]

    def validate_origin(self, origin: Optional[str], allowed_domains: list) -> bool:
        """Validate that the origin domain is allowed."""
        if not origin:
            return False

        # Extract domain from origin
        extracted = tldextract.extract(origin)
        domain = f"{extracted.domain}.{extracted.suffix}"

        # Allow if wildcard or domain matches
        return (
            "*" in allowed_domains
            or domain in allowed_domains
            or origin in allowed_domains
        )

    @track_in_progress
    async def process_submission(
        self,
        form_id: str,
        forms: Dict[str, FormConfig],
        form_data: Dict[str, Any],
        origin: Optional[str] = None,
    ) -> FormSubmission:
        """Process a form submission."""
        # Get form configuration
        form_config = self.get_form_config(form_id, forms)

        # Validate origin if provided
        if origin and not self.validate_origin(origin, form_config.allowed_domains):
            logger.warning(f"Invalid origin for form {form_id}: {origin}")
            raise HTTPException(status_code=403, detail="Origin not allowed")

        # Check for honeypot
        honeypot_field = "_honeypot"  # Default honeypot field name
        if honeypot_field in form_data and form_data[honeypot_field]:
            # Honeypot triggered - this is likely a spam submission
            # We'll silently accept it but mark it as failed
            logger.warning(f"Honeypot triggered for form {form_id}")
            submission = FormSubmission(
                form_id=form_id,
                data=form_data,
                success=False,
                error="Honeypot triggered",
            )
            await self.storage.save_submission(submission)
            return submission

        # Extract files from form data if any
        attachments = []

        # Check if there are any file uploads
        has_files = False
        for key, value in form_data.items():
            # Check if it's a file upload
            if isinstance(value, (UploadFile, File)) or (
                hasattr(value, "read") and callable(value.read)
            ):
                has_files = True
                break

        # Process file uploads if any
        if has_files:
            for field_name, field_value in list(form_data.items()):
                # Skip special fields and non-file fields
                if (
                    field_name.startswith("_")
                    or not hasattr(field_value, "read")
                    or not callable(field_value.read)
                ):
                    continue

                try:
                    # Extract file information
                    file_obj = field_value
                    filename = getattr(file_obj, "filename", f"{field_name}.bin")
                    content_type = getattr(
                        file_obj,
                        "content_type",
                        mimetypes.guess_type(filename)[0] or "application/octet-stream",
                    )

                    # Read file content
                    content = await file_obj.read()

                    # Add to attachments
                    attachments.append(
                        {
                            "content": content,
                            "filename": filename,
                            "content_type": content_type,
                        }
                    )

                    # Remove file object from form data and add filename
                    form_data[f"{field_name}_filename"] = filename
                    form_data[f"{field_name}_content_type"] = content_type
                    del form_data[field_name]
                except Exception as e:
                    logger.error(
                        f"Error processing file upload '{field_name}': {str(e)}"
                    )

        # Clean form data to make it JSON serializable for storage
        cleaned_form_data = {}
        for key, value in form_data.items():
            # Skip files and special fields
            if hasattr(value, "read") and callable(value.read):
                continue

            # Convert value to string if it's not a basic type
            if not isinstance(value, (str, int, float, bool, type(None))):
                cleaned_form_data[key] = str(value)
            else:
                cleaned_form_data[key] = value

        # Create submission record
        submission = FormSubmission(form_id=form_id, data=cleaned_form_data)

        try:
            # Send email with attachments
            await self.email_sender.send_email(
                to_email=form_config.to_email,
                subject=form_config.subject,
                form_data=cleaned_form_data,
                attachments=attachments,
            )

            # Mark submission as successful
            submission.success = True
            increment_email_send(True)
            increment_form_submission(form_id, True)

            logger.info(f"Successfully processed form {form_id}")
        except Exception as e:
            # Record error if email sending fails
            error_msg = str(e)
            submission.error = error_msg
            increment_email_send(False)
            increment_form_submission(form_id, False)

            logger.error(f"Error processing form {form_id}: {error_msg}")

        # Save submission to storage
        await self.storage.save_submission(submission)

        return submission
