from fastapi import APIRouter, Depends, HTTPException, Request, Form, Cookie
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Any, Optional
import os
import uuid
from datetime import datetime

from app.config import Config, get_config
from app.database.connection import get_db
from app.database.repository import FormRepository
from app.database.models import Form, FormDomain, FormStep, FormStepCondition
from app.auth import login_required_redirect

# Initialize templates
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Create router
router = APIRouter(prefix="/forms")


@router.get("/create")
async def create_form_page(
    request: Request,
    session_token: Optional[str] = Cookie(None, alias="session")
):
    """Render the form creation page."""
    # Check authentication
    auth_redirect = login_required_redirect(request, session_token)
    if auth_redirect:
        return auth_redirect
    
    return templates.TemplateResponse(
        "form_edit.html", {"request": request, "form": None, "config": get_config()}
    )


@router.post("/create")
async def create_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
    session_token: Optional[str] = Cookie(None, alias="session")
):
    """Create a new form."""
    # Check authentication
    auth_redirect = login_required_redirect(request, session_token)
    if auth_redirect:
        return auth_redirect

    # Get form data
    form_data = await request.form()

    # Extract allowed domains
    allowed_domains_text = form_data.get("allowed_domains", "*")
    allowed_domains = [
        domain.strip() for domain in allowed_domains_text.split("\n") if domain.strip()
    ]

    # Create form
    try:
        form = await FormRepository.create(
            db=db,
            name=form_data.get("name"),
            to_emails=form_data.get("to_emails"),
            from_email=form_data.get("from_email"),
            subject=form_data.get("subject", "New Form Submission"),
            description=form_data.get("description", ""),
            success_message=form_data.get(
                "success_message", "Thank you for your submission!"
            ),
            redirect_url=form_data.get("redirect_url", ""),
            honeypot_enabled=form_data.get("honeypot_enabled") == "on",
            honeypot_field=form_data.get("honeypot_field", "_honeypot"),
            allowed_domains=allowed_domains,
        )

        # Redirect to form view page
        return RedirectResponse(f"/forms/view/{form.id}", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "form_edit.html",
            {"request": request, "form": None, "config": config, "error": str(e)},
            status_code=400,
        )


@router.get("/edit/{form_id}")
async def edit_form_page(
    form_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
    session_token: Optional[str] = Cookie(None, alias="session")
):
    """Render the form edit page."""
    # Check authentication
    auth_redirect = login_required_redirect(request, session_token)
    if auth_redirect:
        return auth_redirect

    # Get form
    form = await FormRepository.get_by_id(db, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    return templates.TemplateResponse(
        "form_edit.html", {"request": request, "form": form, "config": config}
    )


@router.post("/edit/{form_id}")
async def update_form(
    form_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
):
    """Update an existing form."""
    if not config.use_db:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Database storage is not enabled"},
        )

    # Get form
    form = await FormRepository.get_by_id(db, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    # Get form data
    form_data = await request.form()

    # Extract allowed domains
    allowed_domains_text = form_data.get("allowed_domains", "*")
    allowed_domains = [
        domain.strip() for domain in allowed_domains_text.split("\n") if domain.strip()
    ]

    # Update form
    try:
        update_data = {
            "name": form_data.get("name"),
            "to_emails": form_data.get("to_emails"),
            "from_email": form_data.get("from_email"),
            "subject": form_data.get("subject", "New Form Submission"),
            "description": form_data.get("description", ""),
            "success_message": form_data.get(
                "success_message", "Thank you for your submission!"
            ),
            "redirect_url": form_data.get("redirect_url", ""),
            "honeypot_enabled": form_data.get("honeypot_enabled") == "on",
            "honeypot_field": form_data.get("honeypot_field", "_honeypot"),
            "multi_step_enabled": form_data.get("multi_step_enabled") == "on",
            "show_progress_indicator": form_data.get("show_progress_indicator", "on")
            == "on",
            "progress_indicator_type": form_data.get(
                "progress_indicator_type", "steps"
            ),
        }

        updated_form = await FormRepository.update(
            db=db, form_id=form_id, data=update_data, allowed_domains=allowed_domains
        )

        # Redirect to form view page
        return RedirectResponse(f"/forms/view/{form_id}", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "form_edit.html",
            {"request": request, "form": form, "config": config, "error": str(e)},
            status_code=400,
        )


@router.get("/view/{form_id}")
async def view_form(
    form_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
):
    """Render the form view page."""
    if not config.use_db:
        # Check if form exists in config
        forms_dict = {}
        for form in config.forms:
            forms_dict[form.id] = form

        if form_id not in forms_dict:
            raise HTTPException(status_code=404, detail="Form not found")

        form = forms_dict[form_id]
        # Convert to dictionary for template
        form_dict = {
            "id": form_id,
            "name": form.name,
            "to_email": form.to_email,
            "honeypot_enabled": True,  # Default for config forms
            "honeypot_field": "_honeypot",
            "domains": [{"domain": domain} for domain in form.allowed_domains],
        }

        return templates.TemplateResponse(
            "form_view.html", {"request": request, "form": form_dict, "config": config}
        )
    else:
        # Get form from database
        form = await FormRepository.get_by_id(db, form_id)
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")

        return templates.TemplateResponse(
            "form_view.html", {"request": request, "form": form, "config": config}
        )


@router.get("/delete/{form_id}")
async def delete_form(
    form_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
):
    """Delete a form."""
    if not config.use_db:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Database storage is not enabled"},
        )

    # Get form
    form = await FormRepository.get_by_id(db, form_id)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    # Delete form
    await FormRepository.delete(db, form_id)

    # Redirect to forms list
    return RedirectResponse("/forms", status_code=303)


@router.get("/submissions/{form_id}")
async def form_submissions(
    form_id: str,
    request: Request,
    page: int = 1,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
):
    """Render the form submissions page."""
    # Check if form exists
    if config.use_db:
        form = await FormRepository.get_by_id(db, form_id)
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")

        # Parse filters
        success = None
        if status == "success":
            success = True
        elif status == "error":
            success = False

        from_datetime = None
        to_datetime = None

        if from_date:
            try:
                from_datetime = datetime.strptime(from_date, "%Y-%m-%d")
            except ValueError:
                pass

        if to_date:
            try:
                to_datetime = datetime.strptime(to_date, "%Y-%m-%d")
            except ValueError:
                pass

        # Get submissions with pagination
        limit = 10
        skip = (page - 1) * limit

        # Get submissions from database
        from app.database_storage import DatabaseStorage

        db_storage = DatabaseStorage(db)

        # Get submissions
        submissions = await db_storage.get_submissions(
            form_id=form_id,
            limit=limit,
            skip=skip,
            success=success,
            from_date=from_datetime,
            to_date=to_datetime,
        )

        # Get total count for pagination
        total_count = await db_storage.get_submission_count(
            form_id=form_id,
            success=success,
            from_date=from_datetime,
            to_date=to_datetime,
        )

        # Calculate total pages
        total_pages = (total_count + limit - 1) // limit
    else:
        # Check if form exists in config
        forms_dict = {}
        for form in config.forms:
            forms_dict[form.id] = form

        if form_id not in forms_dict:
            raise HTTPException(status_code=404, detail="Form not found")

        form = forms_dict[form_id]

        # Get submissions from file storage
        from app.storage import FileStorage

        storage = FileStorage()

        submissions = await storage.get_submissions(form_id=form_id)

        # Apply filters
        if status == "success":
            submissions = [s for s in submissions if s.success]
        elif status == "error":
            submissions = [s for s in submissions if not s.success]

        # Simple pagination
        limit = 10
        total_count = len(submissions)
        total_pages = (total_count + limit - 1) // limit

        # Apply pagination
        start = (page - 1) * limit
        end = start + limit
        submissions = submissions[start:end]

    return templates.TemplateResponse(
        "form_submissions.html",
        {
            "request": request,
            "form": form,
            "submissions": submissions,
            "page": page,
            "total_pages": total_pages,
            "config": config,
        },
    )


@router.get("/submissions/{form_id}/export")
async def export_form_submissions(
    form_id: str,
    request: Request,
    format: str = "csv",
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
):
    """Export form submissions."""
    # Implementation would go here
    # For now, we'll just redirect back to the submissions page
    return RedirectResponse(f"/forms/submissions/{form_id}", status_code=303)


@router.get("/steps/{form_id}")
async def multi_step_form_editor(
    form_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
):
    """Render the multi-step form editor page."""
    if not config.use_db:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Database storage is not enabled"},
        )

    # Get form with its steps
    form = await FormRepository.get_by_id(
        db, form_id, include_steps=True, include_step_conditions=True
    )
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    return templates.TemplateResponse(
        "multi_step_form_editor.html",
        {"request": request, "form": form, "config": config},
    )


@router.post("/steps/{form_id}")
async def update_multi_step_form(
    form_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
):
    """Update multi-step form configuration."""
    if not config.use_db:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Database storage is not enabled"},
        )

    # Get form
    form = await FormRepository.get_by_id(
        db, form_id, include_steps=True, include_step_conditions=True
    )
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")

    # Get form data
    form_data = await request.form()

    try:
        # Process steps data
        steps_data = {}
        for key, value in form_data.items():
            if key.startswith("steps["):
                # Extract step ID and field name from the key
                # Format is steps[step_id][field_name]
                parts = key.replace("steps[", "").replace("]", "").split("[", 1)
                if len(parts) == 2:
                    step_id = parts[0]
                    field_name = parts[1]

                    if step_id not in steps_data:
                        steps_data[step_id] = {}

                    steps_data[step_id][field_name] = value

        # Process conditions data
        conditions_data = {}
        for key, value in form_data.items():
            if key.startswith("conditions["):
                # Extract condition ID and field name from the key
                # Format is conditions[condition_id][field_name]
                parts = key.replace("conditions[", "").replace("]", "").split("[", 1)
                if len(parts) == 2:
                    condition_id = parts[0]
                    field_name = parts[1]

                    if condition_id not in conditions_data:
                        conditions_data[condition_id] = {}

                    conditions_data[condition_id][field_name] = value

        # Update database
        async with db.begin():
            # Update form to enable multi-step
            form.multi_step_enabled = True

            # Process steps
            # 1. Delete steps that are not in the submitted data
            existing_step_ids = [step.id for step in form.steps]
            for step_id in existing_step_ids:
                if step_id not in steps_data:
                    # Find the step and delete it
                    for i, step in enumerate(form.steps):
                        if step.id == step_id:
                            await db.delete(step)
                            break

            # 2. Update or create steps
            for step_id, step_data in steps_data.items():
                # Convert fields and required_fields from comma-separated to lists
                if "fields" in step_data and step_data["fields"]:
                    fields = [
                        field.strip()
                        for field in step_data["fields"].split(",")
                        if field.strip()
                    ]
                    step_data["fields"] = fields
                else:
                    step_data["fields"] = []

                if "required_fields" in step_data and step_data["required_fields"]:
                    required_fields = [
                        field.strip()
                        for field in step_data["required_fields"].split(",")
                        if field.strip()
                    ]
                    step_data["required_fields"] = required_fields
                else:
                    step_data["required_fields"] = []

                # Convert step_order to int
                if "step_order" in step_data:
                    step_data["step_order"] = int(step_data["step_order"])

                if step_id.startswith("new-"):
                    # Create new step
                    new_step = FormStep(
                        form_id=form_id,
                        title=step_data.get(
                            "title", f"Step {step_data.get('step_order', 1)}"
                        ),
                        description=step_data.get("description", ""),
                        step_order=step_data.get("step_order", 1),
                        fields=step_data.get("fields", []),
                        required_fields=step_data.get("required_fields", []),
                        next_button_text=step_data.get("next_button_text", "Next"),
                        previous_button_text=step_data.get(
                            "previous_button_text", "Previous"
                        ),
                    )
                    db.add(new_step)
                else:
                    # Update existing step
                    for step in form.steps:
                        if step.id == step_id:
                            step.title = step_data.get("title", step.title)
                            step.description = step_data.get(
                                "description", step.description
                            )
                            step.step_order = step_data.get(
                                "step_order", step.step_order
                            )
                            step.fields = step_data.get("fields", step.fields)
                            step.required_fields = step_data.get(
                                "required_fields", step.required_fields
                            )
                            step.next_button_text = step_data.get(
                                "next_button_text", step.next_button_text
                            )
                            step.previous_button_text = step_data.get(
                                "previous_button_text", step.previous_button_text
                            )
                            break

            # Process conditions
            # 1. Delete conditions that are not in the submitted data
            if hasattr(form, "step_conditions"):
                existing_condition_ids = [cond.id for cond in form.step_conditions]
                for cond_id in existing_condition_ids:
                    if cond_id not in conditions_data:
                        # Find the condition and delete it
                        for i, cond in enumerate(form.step_conditions):
                            if cond.id == cond_id:
                                await db.delete(cond)
                                break

            # 2. Update or create conditions
            for cond_id, cond_data in conditions_data.items():
                # Convert next_step_order to int
                if "next_step_order" in cond_data:
                    cond_data["next_step_order"] = int(cond_data["next_step_order"])

                if cond_id.startswith("new-"):
                    # Create new condition
                    new_condition = FormStepCondition(
                        step_id=cond_data.get("step_id"),
                        field_name=cond_data.get("field_name"),
                        operator=cond_data.get("operator"),
                        value=cond_data.get("value"),
                        next_step_order=cond_data.get("next_step_order"),
                    )
                    db.add(new_condition)
                else:
                    # Update existing condition
                    if hasattr(form, "step_conditions"):
                        for cond in form.step_conditions:
                            if cond.id == cond_id:
                                cond.step_id = cond_data.get("step_id", cond.step_id)
                                cond.field_name = cond_data.get(
                                    "field_name", cond.field_name
                                )
                                cond.operator = cond_data.get("operator", cond.operator)
                                cond.value = cond_data.get("value", cond.value)
                                cond.next_step_order = cond_data.get(
                                    "next_step_order", cond.next_step_order
                                )
                                break

        # Commit changes
        await db.commit()

        # Redirect to form view page
        return RedirectResponse(f"/forms/view/{form_id}", status_code=303)
    except Exception as e:
        # Rollback in case of error
        await db.rollback()

        return templates.TemplateResponse(
            "multi_step_form_editor.html",
            {"request": request, "form": form, "config": config, "error": str(e)},
            status_code=400,
        )
