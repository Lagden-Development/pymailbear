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
from app.database.repository import FormRepository, SubmissionRepository, FormTokenRepository
from app.database.models import Form, FormDomain
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
            hcaptcha_enabled=form_data.get("hcaptcha_enabled") == "on",
            hcaptcha_site_key=form_data.get("hcaptcha_site_key", ""),
            hcaptcha_secret_key=form_data.get("hcaptcha_secret_key", ""),
            max_field_length=int(form_data.get("max_field_length", 5000)),
            max_fields=int(form_data.get("max_fields", 50)),
            max_file_size=int(form_data.get("max_file_size", 10485760)),
            rate_limit_per_ip_per_minute=int(form_data.get("rate_limit_per_ip_per_minute", 5)),
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
            "hcaptcha_enabled": form_data.get("hcaptcha_enabled") == "on",
            "hcaptcha_site_key": form_data.get("hcaptcha_site_key", ""),
            "hcaptcha_secret_key": form_data.get("hcaptcha_secret_key", ""),
            "max_field_length": int(form_data.get("max_field_length", 5000)),
            "max_fields": int(form_data.get("max_fields", 50)),
            "max_file_size": int(form_data.get("max_file_size", 10485760)),
            "rate_limit_per_ip_per_minute": int(form_data.get("rate_limit_per_ip_per_minute", 5)),
        }

        updated_form = await FormRepository.update(
            db=db, form_id=form_id, data=update_data, allowed_domains=allowed_domains
        )

        # Redirect back to form edit page
        return RedirectResponse(f"/forms/edit/{form_id}", status_code=303)
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


@router.post("/submissions/{submission_id}/delete")
async def delete_submission(
    submission_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
    session_token: Optional[str] = Cookie(None, alias="session")
):
    """Delete a submission."""
    # Check authentication
    auth_redirect = login_required_redirect(request, session_token)
    if auth_redirect:
        return auth_redirect
    
    if not config.use_db:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Database storage is not enabled"},
        )
    
    # Get the submission to find the form_id for redirect
    submission = await SubmissionRepository.get_by_id(db, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    form_id = submission.form_id
    
    # Delete the submission
    deleted = await SubmissionRepository.delete(db, submission_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Get the referer to determine where to redirect
    referer = request.headers.get("Referer", "")
    
    if f"/forms/submissions/{form_id}" in referer:
        # Redirect back to form-specific submissions page
        return RedirectResponse(f"/forms/submissions/{form_id}", status_code=303)
    else:
        # Redirect to global submissions page
        return RedirectResponse("/submissions", status_code=303)
