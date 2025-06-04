import logging
from typing import Dict, Optional, List, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import tldextract
from datetime import datetime

from app.storage import FormSubmission
from app.email_sender import EmailSender
from app.metrics import (
    increment_form_submission,
    increment_email_send,
    track_in_progress,
)
from app.database.repository import FormRepository, SubmissionRepository

logger = logging.getLogger(__name__)


class DatabaseFormHandler:
    """Form handler implementation using database storage."""

    def __init__(self, db_session: AsyncSession, email_sender: EmailSender):
        """Initialize with a database session and email sender."""
        self.db = db_session
        self.email_sender = email_sender

    async def get_form_config(self, form_id: str) -> Dict[str, Any]:
        """Get form configuration by ID."""
        form = await FormRepository.get_by_id(self.db, form_id)
        if not form:
            logger.warning(f"Form ID not found: {form_id}")
            raise HTTPException(status_code=404, detail="Form not found")

        # Convert to dictionary format
        form_dict = {
            "id": form.id,
            "name": form.name,
            "to_emails": form.to_emails,
            "from_email": form.from_email,
            "subject": form.subject,
            "honeypot_enabled": form.honeypot_enabled,
            "honeypot_field": form.honeypot_field,
            "allowed_domains": [domain.domain for domain in form.domains],
            "redirect_url": form.redirect_url,
            "success_message": form.success_message,
        }

        return form_dict

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

    def check_honeypot(self, form_data: Dict[str, str], honeypot_field: str) -> bool:
        """Check if honeypot field is filled (indicating spam)."""
        return honeypot_field in form_data and form_data[honeypot_field]

    @track_in_progress
    async def process_submission(
        self,
        form_id: str,
        form_data: Dict[str, str],
        origin: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> FormSubmission:
        """Process a form submission."""
        # Get form configuration
        form_config = await self.get_form_config(form_id)

        # Validate origin if provided
        if origin and not self.validate_origin(origin, form_config["allowed_domains"]):
            logger.warning(f"Invalid origin for form {form_id}: {origin}")
            raise HTTPException(status_code=403, detail="Origin not allowed")

        # Check honeypot if enabled
        if form_config["honeypot_enabled"] and self.check_honeypot(
            form_data, form_config["honeypot_field"]
        ):
            logger.warning(f"Honeypot triggered for form {form_id}")

            # Create a failed submission without raising an exception
            # This way the spam bot thinks the submission succeeded
            submission = FormSubmission(
                form_id=form_id,
                data=form_data,
                success=False,
                error="Honeypot triggered",
            )

            # Save to database
            await SubmissionRepository.create(
                db=self.db,
                form_id=form_id,
                data=form_data,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error="Honeypot triggered",
            )

            increment_form_submission(form_id, False)
            return submission

        # Create submission record
        submission = FormSubmission(form_id=form_id, data=form_data)

        try:
            # Remove honeypot field if present
            if (
                form_config["honeypot_enabled"]
                and form_config["honeypot_field"] in form_data
            ):
                form_data.pop(form_config["honeypot_field"])

            # Send email
            await self.email_sender.send_email(
                to_emails=form_config["to_emails"],
                subject=form_config["subject"],
                form_data=form_data,
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

        # Save submission to database
        await SubmissionRepository.create(
            db=self.db,
            form_id=form_id,
            data=form_data,
            ip_address=ip_address,
            user_agent=user_agent,
            success=submission.success,
            error=submission.error,
        )

        return submission
