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
from app.database.repository import FormRepository, SubmissionRepository, FormTokenRepository
from app.hcaptcha_service import hcaptcha_service

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
            "hcaptcha_enabled": form.hcaptcha_enabled,
            "hcaptcha_site_key": form.hcaptcha_site_key,
            "hcaptcha_secret_key": form.hcaptcha_secret_key,
            "max_field_length": form.max_field_length,
            "max_fields": form.max_fields,
            "max_file_size": form.max_file_size,
            "rate_limit_per_ip_per_minute": form.rate_limit_per_ip_per_minute,
        }

        return form_dict

    def validate_origin(self, origin: Optional[str], allowed_domains: list) -> bool:
        """Validate that the origin domain is allowed with strict matching."""
        if not origin:
            return False

        # Allow if explicit wildcard is configured
        if "*" in allowed_domains:
            return True

        # Extract domain from origin URL
        extracted = tldextract.extract(origin)
        origin_domain = f"{extracted.domain}.{extracted.suffix}"
        
        # Check for exact matches in allowed domains
        for allowed_domain in allowed_domains:
            # Skip empty domains
            if not allowed_domain.strip():
                continue
                
            # Exact origin match (e.g., "https://example.com")
            if origin == allowed_domain:
                return True
                
            # Exact domain match (e.g., "example.com")
            if origin_domain == allowed_domain:
                return True
                
            # Subdomain wildcard match (e.g., "*.example.com")
            if allowed_domain.startswith("*."):
                parent_domain = allowed_domain[2:]  # Remove "*."
                if origin_domain.endswith(f".{parent_domain}") or origin_domain == parent_domain:
                    return True
        
        return False

    def validate_referer(self, referer: Optional[str], allowed_domains: list) -> bool:
        """Validate that the referer domain is allowed."""
        if not referer:
            return False
            
        # Use same validation logic as origin
        return self.validate_origin(referer, allowed_domains)

    def check_honeypot(self, form_data: Dict[str, str], honeypot_field: str) -> bool:
        """Check if honeypot field is filled (indicating spam)."""
        return honeypot_field in form_data and form_data[honeypot_field]

    def validate_field_limits(self, form_data: Dict[str, str], form_config: Dict[str, Any]) -> Optional[str]:
        """Validate form data against field limits. Returns error message if validation fails."""
        max_field_length = form_config.get("max_field_length", 5000)
        max_fields = form_config.get("max_fields", 50)
        
        # System fields that should be excluded from validation
        system_fields = {
            "g-recaptcha-response",  # reCAPTCHA response token
            "form_token",           # CSRF protection token
            "_honeypot",            # Default honeypot field
        }
        
        # Add configured honeypot field to system fields
        honeypot_field = form_config.get("honeypot_field", "_honeypot")
        if honeypot_field:
            system_fields.add(honeypot_field)
        
        # Filter out system fields for validation
        user_fields = {k: v for k, v in form_data.items() if k not in system_fields}
        
        # Check number of user fields (excluding system fields)
        if len(user_fields) > max_fields:
            return f"Too many fields. Maximum {max_fields} fields allowed, got {len(user_fields)}"
        
        # Check field lengths for user fields only
        for field_name, field_value in user_fields.items():
            if isinstance(field_value, str) and len(field_value) > max_field_length:
                return f"Field '{field_name}' exceeds maximum length of {max_field_length} characters"
        
        return None

    def validate_custom_headers(self, request_headers: Dict[str, str]) -> bool:
        """Validate that required custom headers are present for JavaScript submissions."""
        # Require X-Requested-With header to indicate AJAX request
        x_requested_with = request_headers.get("X-Requested-With", "")
        if x_requested_with != "XMLHttpRequest":
            return False
        
        # Require X-Form-Origin header
        x_form_origin = request_headers.get("X-Form-Origin", "")
        if not x_form_origin:
            return False
            
        return True

    async def validate_form_token(self, form_id: str, token: str) -> bool:
        """Validate that the form token is valid and not expired."""
        if not token:
            return False
        
        # Get the token from database
        form_token = await FormTokenRepository.get_by_form_and_token(self.db, form_id, token)
        
        if not form_token:
            logger.warning(f"Token not found for form {form_id}: {token[:8]}...")
            return False
        
        # Check if token is already used
        if form_token.used:
            logger.warning(f"Token already used for form {form_id}: {token[:8]}...")
            return False
        
        # Check if token is expired
        if form_token.expires_at < datetime.now():
            logger.warning(f"Token expired for form {form_id}: {token[:8]}...")
            return False
        
        # Mark token as used
        await FormTokenRepository.mark_as_used(self.db, form_token.id)
        
        return True

    @track_in_progress
    async def process_submission(
        self,
        form_id: str,
        form_data: Dict[str, str],
        origin: Optional[str] = None,
        referer: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> FormSubmission:
        """Process a form submission."""
        # Get form configuration
        form_config = await self.get_form_config(form_id)

        # Validate field limits
        validation_error = self.validate_field_limits(form_data, form_config)
        if validation_error:
            logger.warning(f"Field validation failed for form {form_id}: {validation_error}")
            raise HTTPException(status_code=400, detail=validation_error)

        # Validate custom headers for JavaScript-only submissions
        if request_headers and not self.validate_custom_headers(request_headers):
            logger.warning(f"Required custom headers missing for form {form_id}")
            raise HTTPException(status_code=403, detail="JavaScript submission required")

        # Validate form token if provided
        form_token = form_data.get("form_token", "")
        if form_token:
            if not await self.validate_form_token(form_id, form_token):
                logger.warning(f"Invalid or expired form token for form {form_id}")
                raise HTTPException(status_code=403, detail="Invalid or expired form token")
            # Remove token from form data so it's not included in email
            form_data = {k: v for k, v in form_data.items() if k != "form_token"}

        # Enhanced origin validation - require both Origin and Referer headers unless wildcard
        allowed_domains = form_config["allowed_domains"]
        if "*" not in allowed_domains:
            # Require both Origin and Referer headers for strict validation
            if not origin and not referer:
                logger.warning(f"Origin and Referer headers required for form {form_id} but not provided")
                raise HTTPException(status_code=403, detail="Origin and Referer headers required")
            
            # Validate Origin header if provided
            if origin and not self.validate_origin(origin, allowed_domains):
                logger.warning(f"Invalid origin for form {form_id}: {origin}")
                raise HTTPException(status_code=403, detail="Origin not allowed")
            
            # Validate Referer header if provided
            if referer and not self.validate_referer(referer, allowed_domains):
                logger.warning(f"Invalid referer for form {form_id}: {referer}")
                raise HTTPException(status_code=403, detail="Referer not allowed")
            
            # Require at least one valid header
            origin_valid = origin and self.validate_origin(origin, allowed_domains)
            referer_valid = referer and self.validate_referer(referer, allowed_domains)
            
            if not (origin_valid or referer_valid):
                logger.warning(f"No valid origin or referer for form {form_id}: origin={origin}, referer={referer}")
                raise HTTPException(status_code=403, detail="Invalid origin or referer")
        else:
            # If wildcard is allowed but headers are provided, still validate them
            if origin and not self.validate_origin(origin, allowed_domains):
                logger.warning(f"Invalid origin for form {form_id}: {origin}")
                raise HTTPException(status_code=403, detail="Origin not allowed")
            if referer and not self.validate_referer(referer, allowed_domains):
                logger.warning(f"Invalid referer for form {form_id}: {referer}")
                raise HTTPException(status_code=403, detail="Referer not allowed")

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

        # Validate hCaptcha if enabled
        if form_config["hcaptcha_enabled"]:
            hcaptcha_token = form_data.get("h-captcha-response")
            if not hcaptcha_token:
                logger.warning(f"hCaptcha token missing for form {form_id}")
                raise HTTPException(status_code=400, detail="hCaptcha verification required")
            
            # Use form-specific secret key if available, otherwise use global config
            secret_key = form_config.get("hcaptcha_secret_key")
            if not secret_key:
                secret_key = hcaptcha_service.hcaptcha_config.secret_key
            
            if not secret_key:
                logger.error(f"No hCaptcha secret key configured for form {form_id}")
                raise HTTPException(status_code=500, detail="hCaptcha configuration error")
            
            # Verify hCaptcha token
            verification_result = await hcaptcha_service.verify_token(
                token=hcaptcha_token,
                remote_ip=ip_address,
                secret_key=secret_key
            )
            
            if not verification_result.success:
                logger.warning(f"hCaptcha verification failed for form {form_id}: {verification_result}")
                # Create a failed submission for hCaptcha failure
                submission = FormSubmission(
                    form_id=form_id,
                    data=form_data,
                    success=False,
                    error="hCaptcha verification failed",
                )
                
                # Save to database
                await SubmissionRepository.create(
                    db=self.db,
                    form_id=form_id,
                    data=form_data,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                    error="hCaptcha verification failed",
                )
                
                increment_form_submission(form_id, False)
                raise HTTPException(status_code=400, detail="hCaptcha verification failed")
            
            # Remove hCaptcha token from form data before processing
            form_data.pop("h-captcha-response", None)
            
            logger.info(f"hCaptcha verification successful for form {form_id}")

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
