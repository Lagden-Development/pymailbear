import logging
import ssl
import base64
import asyncio
from typing import Dict, Optional, List, BinaryIO, Union, Any
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
import mimetypes
import traceback
import backoff

from app.config import SMTPConfig
from app.storage import FormSubmission

logger = logging.getLogger(__name__)


class EmailSender:
    """
    Handles sending emails with form submission data and file attachments.
    
    This class provides asynchronous email sending capabilities with retries,
    proper error handling, and support for various email configurations.
    """
    
    def __init__(self, smtp_config: SMTPConfig):
        """
        Initialize the email sender with SMTP configuration.
        
        Args:
            smtp_config: Configuration for SMTP server connection
        """
        self.config = smtp_config
    
    @backoff.on_exception(
        backoff.expo,
        (aiosmtplib.SMTPException, ConnectionError, asyncio.TimeoutError),
        max_tries=3,
        jitter=backoff.full_jitter
    )
    async def send_email(
        self, 
        to_emails: Union[str, List[str]], 
        subject: str, 
        form_data: Dict[str, str], 
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Send email with form submission data and optional attachments.
        
        Args:
            to_emails: Single recipient email address or list of recipients
            subject: Email subject line
            form_data: Dictionary of form field names and values
            attachments: Optional list of file attachments
            
        Raises:
            aiosmtplib.SMTPException: If email sending fails
        """
        try:
            # Convert to list if single email provided
            if isinstance(to_emails, str):
                email_list = [email.strip() for email in to_emails.split(',') if email.strip()]
            else:
                email_list = to_emails
            
            # Create message
            message = MIMEMultipart('mixed')
            message["From"] = self.config.from_email
            message["To"] = ", ".join(email_list)
            message["Subject"] = subject
            
            # Create HTML version (main part)
            html_part = MIMEMultipart('alternative')
            
            # Create email body with form data
            # Remove file fields from form data as they will be added as attachments
            form_data_for_body = {
                k: v for k, v in form_data.items() 
                if not k.startswith('_') and not isinstance(v, (bytes, bytearray, memoryview))
            }
            
            # Format email content with responsive design
            body = self._format_email_body(form_data_for_body)
            html_part.attach(MIMEText(body, "html"))
            message.attach(html_part)
            
            # Add attachments if any
            if attachments:
                for attachment in attachments:
                    if "content" in attachment and "filename" in attachment:
                        self._add_attachment(
                            message, 
                            attachment["content"], 
                            attachment["filename"], 
                            attachment.get("content_type")
                        )
            
            # Add files from form data if they are binary
            for field_name, field_value in form_data.items():
                if isinstance(field_value, (bytes, bytearray, memoryview)) and not field_name.startswith('_'):
                    filename = form_data.get(f"{field_name}_filename", f"{field_name}.bin")
                    content_type = form_data.get(
                        f"{field_name}_content_type", 
                        mimetypes.guess_type(filename)[0] or "application/octet-stream"
                    )
                    self._add_attachment(message, field_value, filename, content_type)
            
            # Setup SSL context if needed
            ssl_context = None
            if self.config.ssl_context:
                ssl_context = ssl.create_default_context()
                if not self.config.verify_cert:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
            
            # Determine TLS settings if not explicitly set
            use_tls = self.config.use_tls
            if use_tls is None:
                use_tls = self.config.port == 465
                
            start_tls = self.config.start_tls
            if start_tls is None:
                start_tls = self.config.port == 587
            
            # Connect to SMTP server
            smtp = aiosmtplib.SMTP(
                hostname=self.config.host,
                port=self.config.port,
                use_tls=use_tls,
                start_tls=start_tls,
                tls_context=ssl_context,
                timeout=self.config.timeout
            )
            
            try:
                await smtp.connect()
                
                if self.config.username and self.config.password:
                    await smtp.login(self.config.username, self.config.password)
                
                # Send email
                await smtp.send_message(message)
                logger.info(f"Email sent successfully to {', '.join(email_list)}")
            finally:
                # Always try to quit the SMTP connection
                try:
                    await smtp.quit()
                except Exception:
                    # Ignore errors during quit
                    pass
                
        except aiosmtplib.SMTPException as e:
            logger.error(f"SMTP error sending email to {', '.join(email_list)}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending email to {', '.join(email_list)}: {str(e)}")
            logger.error(traceback.format_exc())
            raise aiosmtplib.SMTPException(f"Failed to send email: {str(e)}")
    
    def _add_attachment(
        self, 
        message: MIMEMultipart, 
        content: bytes, 
        filename: str, 
        content_type: Optional[str] = None
    ) -> None:
        """
        Add an attachment to the email message.
        
        Args:
            message: Email message to add attachment to
            content: Binary content of the attachment
            filename: Name of the file
            content_type: MIME type of the file
        """
        if not content_type:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            
        # Create the appropriate MIME part based on content type
        if content_type.startswith("image/"):
            attachment = MIMEImage(content, _subtype=content_type.split("/")[1])
        else:
            attachment = MIMEApplication(content)
            
        # Add content disposition header
        attachment.add_header("Content-Disposition", "attachment", filename=filename)
        
        # Add content type if not automatically set
        if "Content-Type" not in attachment:
            attachment.add_header("Content-Type", content_type)
            
        # Add to message
        message.attach(attachment)
    
    def _format_email_body(self, form_data: Dict[str, str]) -> str:
        """
        Format form data as responsive HTML for email body.
        
        Args:
            form_data: Dictionary of form field names and values
            
        Returns:
            str: HTML formatted email body
        """
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Form Submission</title>
            <style>
                /* Base styles */
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }
                
                /* Container */
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }
                
                /* Header */
                .header {
                    background-color: #0066cc;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 5px 5px 0 0;
                }
                
                /* Content */
                .content {
                    background-color: #f9f9f9;
                    padding: 20px;
                    border: 1px solid #ddd;
                    border-top: none;
                    border-radius: 0 0 5px 5px;
                }
                
                /* Table */
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                    background-color: white;
                }
                
                th, td {
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }
                
                th {
                    background-color: #f2f2f2;
                    font-weight: bold;
                }
                
                tr:nth-child(even) {
                    background-color: #f9f9f9;
                }
                
                /* Footer */
                .footer {
                    margin-top: 30px;
                    font-size: 12px;
                    color: #777;
                    text-align: center;
                }
                
                /* Responsive */
                @media only screen and (max-width: 480px) {
                    .container {
                        padding: 10px;
                    }
                    
                    .header, .content {
                        padding: 15px;
                    }
                    
                    th, td {
                        padding: 8px 10px;
                    }
                    
                    .header h2 {
                        font-size: 18px;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>New Form Submission</h2>
                </div>
                <div class="content">
                    <table>
                        <tr>
                            <th>Field</th>
                            <th>Value</th>
                        </tr>
        """
        
        for field, value in form_data.items():
            # Skip special fields and binary data
            if field.startswith('_'):
                continue
                
            # Format the value
            if isinstance(value, str):
                # Replace newlines with HTML line breaks
                value = value.replace("\n", "<br>")
            
            html += f"""
                <tr>
                    <td><strong>{field}</strong></td>
                    <td>{value}</td>
                </tr>
            """
        
        html += """
                    </table>
                </div>
                <div class="footer">
                    <p>This email was sent via MailBear form submission service.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html