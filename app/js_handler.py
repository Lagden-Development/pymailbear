import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request
from fastapi.responses import Response
import os
import aiofiles
from jinja2 import Template

from app.utils.minify import minify_js, minify_css
from app.database.repository import FormRepository
from app.database.models import Form

logger = logging.getLogger(__name__)

# Cache for minified scripts
script_cache = {}
CACHE_MAX_AGE = 3600  # 1 hour in seconds


class JSHandler:
    """Handler for JavaScript generation and delivery."""

    def __init__(self):
        """Initialize the JS handler."""
        self.js_template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app",
            "js_templates",
            "form_handler.js",
        )
        self.css_template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app",
            "js_templates",
            "form_handler.css",
        )
        self.multi_step_css_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "app",
            "js_templates",
            "multi_step_form.css",
        )
        self.js_template = None
        self.css_template = None
        self.multi_step_css = None

    async def load_templates(self):
        """Load JS and CSS templates."""
        if self.js_template is None:
            try:
                async with aiofiles.open(self.js_template_path, "r") as f:
                    self.js_template = Template(await f.read())
            except Exception as e:
                logger.error(f"Error loading JS template: {str(e)}")
                raise HTTPException(status_code=500, detail="Error loading JS template")

        if self.css_template is None:
            try:
                async with aiofiles.open(self.css_template_path, "r") as f:
                    self.css_template = await f.read()
            except Exception as e:
                logger.error(f"Error loading CSS template: {str(e)}")
                raise HTTPException(
                    status_code=500, detail="Error loading CSS template"
                )

        if self.multi_step_css is None:
            try:
                async with aiofiles.open(self.multi_step_css_path, "r") as f:
                    self.multi_step_css = await f.read()
            except Exception as e:
                logger.error(f"Error loading multi-step CSS template: {str(e)}")
                # Don't raise exception, just log the error

    def get_cache_key(self, form_id: str, form_data: Dict[str, Any]) -> str:
        """Generate a cache key for the form script."""
        # Include form ID and updated_at timestamp to invalidate cache when form is updated
        return f"{form_id}_{form_data.get('updated_at', '')}"

    async def get_form_script(
        self,
        form_id: str,
        request: Request,
        form: Optional[Form] = None,
        db_form_data: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Generate and return JavaScript for the form."""
        await self.load_templates()

        # Get form data
        form_data = {}
        if db_form_data:
            form_data = db_form_data
        elif form:
            # Convert form to dict
            form_data = {
                "id": form.id,
                "name": form.name,
                "to_email": form.to_email,
                "from_email": form.from_email,
                "subject": form.subject,
                "honeypot_enabled": form.honeypot_enabled,
                "honeypot_field": form.honeypot_field,
                "redirect_url": form.redirect_url,
                "success_message": form.success_message,
                "updated_at": form.updated_at.isoformat() if form.updated_at else "",
                "allowed_domains": [domain.domain for domain in form.domains],
            }
        else:
            raise HTTPException(status_code=404, detail="Form not found")

        # Check cache
        cache_key = self.get_cache_key(form_id, form_data)
        if cache_key in script_cache:
            return self.create_js_response(script_cache[cache_key])

        # Get base URL for API endpoint
        base_url = str(request.base_url).rstrip("/")

        # Get multi-step form configuration if enabled
        multi_step_enabled = form_data.get("multi_step_enabled", False)
        steps = []
        step_conditions = []

        if (
            multi_step_enabled
            and form
            and hasattr(form, "steps")
            and len(form.steps) > 0
        ):
            # Convert steps to JSON-serializable format
            for step in form.steps:
                step_data = {
                    "id": step.id,
                    "title": step.title,
                    "description": step.description,
                    "step_order": step.step_order,
                    "fields": step.fields,
                    "required_fields": step.required_fields,
                    "next_button_text": step.next_button_text,
                    "previous_button_text": step.previous_button_text,
                }
                steps.append(step_data)

                # Get step conditions if any
                if hasattr(step, "conditions"):
                    for condition in step.conditions:
                        condition_data = {
                            "stepIndex": step.step_order,
                            "fieldName": condition.field_name,
                            "operator": condition.operator,
                            "value": condition.value,
                            "nextStepIndex": condition.next_step_order,
                        }
                        step_conditions.append(condition_data)

        # Prepare template variables
        template_vars = {
            "form_id": form_id,
            "api_endpoint": f"{base_url}/api/v1/form/{form_id}",
            "generation_timestamp": datetime.now().isoformat(),
            "honeypot_enabled": form_data.get("honeypot_enabled", False),
            "honeypot_field": form_data.get("honeypot_field", "_honeypot"),
            "redirect_url": form_data.get("redirect_url", ""),
            "success_message": form_data.get(
                "success_message", "Form submitted successfully!"
            ),
            "error_message": "An error occurred. Please try again.",
            "validation_enabled": True,
            "submit_timeout": 30000,  # 30 seconds
            "csrf_enabled": False,
            "file_upload_enabled": True,  # Enable file uploads by default
            "allowed_file_types": json.dumps(
                [
                    "jpg",
                    "jpeg",
                    "png",
                    "gif",
                    "webp",
                    "pdf",
                    "doc",
                    "docx",
                    "xls",
                    "xlsx",
                    "txt",
                    "zip",
                ]
            ),
            "max_file_size": 10,  # 10MB
            "custom_styles": json.dumps({}),
            "debug": False,
            # Multi-step form configuration
            "multi_step_enabled": multi_step_enabled,
            "show_progress_indicator": form_data.get("show_progress_indicator", True),
            "progress_indicator_type": form_data.get(
                "progress_indicator_type", "steps"
            ),
            "steps": json.dumps(steps),
            "step_conditions": json.dumps(step_conditions),
        }

        # Add CSS to JS
        css_content = self.css_template

        # Add multi-step CSS if enabled
        if multi_step_enabled and self.multi_step_css:
            css_content += "\n" + self.multi_step_css

        # Render JS template
        js_content = self.js_template.render(**template_vars)

        js_with_css = f"{js_content}\n// Inject CSS\n(function() {{\n  const style = document.createElement('style');\n  style.textContent = `{css_content}`;\n  document.head.appendChild(style);\n}})();"

        # Minify JS
        minified_js = minify_js(js_with_css)

        # Cache the result
        script_cache[cache_key] = minified_js

        # Return JS response
        return self.create_js_response(minified_js)

    def create_js_response(self, js_content: str) -> Response:
        """Create a Response object with appropriate headers for JavaScript."""
        response = Response(content=js_content, media_type="application/javascript")

        # Set cache headers
        response.headers["Cache-Control"] = f"public, max-age={CACHE_MAX_AGE}"

        return response
