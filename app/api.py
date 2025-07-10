from fastapi import FastAPI, Request, Depends, HTTPException, Form, status, Cookie
from fastapi.responses import JSONResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
from typing import Dict, Any, Optional
import os
import time
import traceback
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.config import Config, get_config
from app.email_sender import EmailSender
import secrets
from datetime import datetime, timedelta
import asyncio
from app.utils.ip_utils import get_real_ip, get_client_info
from app.metrics import start_metrics_server
from app.database.connection import get_db
from app.database.repository import FormRepository
from app.form_controller import router as form_router
from app.auth import (
    verify_password, 
    create_session, 
    invalidate_session, 
    login_required_redirect
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize rate limiter with custom key function
def get_real_ip_for_limiter(request: Request) -> str:
    """Get real IP for rate limiting purposes."""
    real_ip = get_real_ip(request)
    return real_ip or "unknown"

limiter = Limiter(key_func=get_real_ip_for_limiter)

# Initialize FastAPI app
app = FastAPI(
    title="MailBear",
    description="A simple form submission to email service",
    version="1.0.0",
    docs_url=None,  # Disable default docs to use custom implementation
    redoc_url=None,  # Disable default redoc to use custom implementation
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include form router
app.include_router(form_router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # This will be overridden per-form
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Origin", "X-Requested-With", "X-Form-Origin", "Referer"],
)

# Add middleware for request timing and logging
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    
    # Get real IP for logging and rate limiting
    real_ip = get_real_ip(request)
    
    # Add real IP to request state for use in endpoints
    request.state.real_ip = real_ip
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log request details with real IP
        logger.info(
            f"Request: {request.method} {request.url.path} - "
            f"Real IP: {real_ip} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.4f}s"
        )
        
        return response
    except Exception as e:
        # Log the exception
        logger.error(
            f"Error processing request: {request.method} {request.url.path}\n"
            f"Error: {str(e)}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        
        # Return a properly formatted error response
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "An internal server error occurred"}
        )

# Initialize templates
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Global instances
config = None


def get_local_config():
    """Dependency to get config."""
    global config
    if config is None:
        config = get_config()
    return config


# Background task for token cleanup
async def cleanup_tokens_task():
    """Background task to clean up expired tokens every hour."""
    while True:
        try:
            # Wait 1 hour between cleanups
            await asyncio.sleep(3600)
            
            # Get a database session
            from app.database.connection import AsyncSessionLocal
            if AsyncSessionLocal is not None:
                async with AsyncSessionLocal() as db:
                    from app.database.repository import FormTokenRepository
                    
                    # Clean up expired tokens
                    expired_count = await FormTokenRepository.cleanup_expired_tokens(db)
                    
                    # Clean up used tokens older than 24 hours
                    used_count = await FormTokenRepository.cleanup_used_tokens(db, older_than_hours=24)
                    
                    if expired_count > 0 or used_count > 0:
                        logger.info(f"Token cleanup: removed {expired_count} expired and {used_count} old used tokens")
                        
        except Exception as e:
            logger.error(f"Error in token cleanup task: {str(e)}")
            # Continue running even if there's an error
            continue


# Background task for rate limiter cleanup
async def cleanup_rate_limiter_task():
    """Background task to clean up rate limiter memory every 5 minutes."""
    while True:
        try:
            # Wait 5 minutes between cleanups
            await asyncio.sleep(300)
            
            from app.rate_limiter import rate_limiter
            rate_limiter.cleanup()
            
            logger.debug("Rate limiter cleanup completed")
                        
        except Exception as e:
            logger.error(f"Error in rate limiter cleanup task: {str(e)}")
            # Continue running even if there's an error
            continue


# Background task for security monitor cleanup
async def cleanup_security_monitor_task():
    """Background task to clean up security monitor every 10 minutes."""
    while True:
        try:
            # Wait 10 minutes between cleanups
            await asyncio.sleep(600)
            
            from app.security_monitor import security_monitor
            security_monitor.cleanup()
            
            logger.debug("Security monitor cleanup completed")
                        
        except Exception as e:
            logger.error(f"Error in security monitor cleanup task: {str(e)}")
            # Continue running even if there's an error
            continue


# Custom OpenAPI and documentation endpoints
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="MailBear API Documentation",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="MailBear API Documentation",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
    )


@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_endpoint():
    return get_openapi(
        title="MailBear",
        version="1.0.0",
        description="A production-ready form submission to email service",
        routes=app.routes,
    )


@app.on_event("startup")
async def startup_event():
    """Initialize app on startup."""
    try:
        # Load config
        cfg = get_local_config()
        
        # Start metrics server
        start_metrics_server(cfg.metrics_port)
        
        # Start background token cleanup task
        if cfg.use_db:
            asyncio.create_task(cleanup_tokens_task())
            logger.info("Started background token cleanup task")
        
        # Start background rate limiter cleanup task
        asyncio.create_task(cleanup_rate_limiter_task())
        logger.info("Started background rate limiter cleanup task")
        
        # Start background security monitor cleanup task
        asyncio.create_task(cleanup_security_monitor_task())
        logger.info("Started background security monitor cleanup task")
        
        logger.info(f"MailBear started on port {cfg.port}")
        logger.info(f"Metrics available on port {cfg.metrics_port}")
    except Exception as e:
        logger.critical(f"Failed to start MailBear: {str(e)}")
        logger.critical(traceback.format_exc())
        # Re-raise to prevent app from starting in a bad state
        raise


@app.options("/api/v1/form/{form_id}")
async def options_form_submit(form_id: str, request: Request):
    """Handle preflight OPTIONS request for form submission endpoint."""
    origin = request.headers.get("Origin", "*")
    
    response = Response(status_code=200)
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Origin, X-Requested-With, X-Form-Origin, Referer"
    response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours
    
    return response

@app.post("/api/v1/form/{form_id}", status_code=status.HTTP_200_OK)
async def submit_form(
    form_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config)
):
    """
    Submit a form for processing.
    
    The form data is sent as multipart/form-data and will be validated
    against the allowed origins and honeypot protection before processing.
    
    If successful, the form data will be sent via email and stored.
    """
    # Check request size early to prevent large payload attacks
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            content_length = int(content_length)
            max_size = 50 * 1024 * 1024  # 50MB max
            if content_length > max_size:
                logger.warning(f"Request too large from IP {get_real_ip(request)}: {content_length} bytes")
                return JSONResponse(
                    status_code=413,
                    content={"status": "error", "message": "Request too large"}
                )
        except (ValueError, TypeError):
            pass  # Invalid content-length header, let it proceed
    
    # Get origin header and real client information
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")
    client_info = get_client_info(request)
    ip_address = client_info["ip_address"]
    user_agent = client_info["user_agent"]
    
    # Check if IP is blocked due to suspicious activity
    from app.security_monitor import security_monitor
    if security_monitor.is_ip_blocked(ip_address):
        logger.warning(f"Blocked IP {ip_address} attempted form submission")
        return JSONResponse(
            status_code=403,
            content={"status": "error", "message": "Access denied"}
        )
    
    # Log Cloudflare detection for debugging
    if client_info["is_cloudflare"]:
        logger.info(f"Cloudflare request detected for form {form_id}. Real IP: {ip_address}, Proxy headers: {client_info['proxy_headers']}")
    else:
        logger.debug(f"Direct connection for form {form_id}. IP: {ip_address}")
    
    # Extract relevant headers for validation
    request_headers = {
        "X-Requested-With": request.headers.get("X-Requested-With", ""),
        "X-Form-Origin": request.headers.get("X-Form-Origin", ""),
    }
    
    try:
        # Use database form handler to get form config for rate limiting
        from app.database_form_handler import DatabaseFormHandler
        email_sender = EmailSender(config.smtp)
        db_form_handler = DatabaseFormHandler(db, email_sender)
        
        # Get form configuration for rate limiting
        try:
            form_config = await db_form_handler.get_form_config(form_id)
        except HTTPException as e:
            if e.status_code == 404:
                return JSONResponse(status_code=404, content={"status": "error", "message": "Form not found"})
            raise
        
        # Apply basic per-IP rate limiting before expensive operations to prevent DoS
        from app.rate_limiter import rate_limiter
        basic_ip_limit = min(form_config.get("rate_limit_per_ip_per_minute", 5) * 3, 50)  # 3x normal limit for basic checks
        
        basic_rate_allowed, basic_rate_reason = rate_limiter.is_allowed(
            form_id=f"basic_{form_id}",  # Separate namespace for basic rate limiting
            ip_address=ip_address,
            ip_limit=basic_ip_limit
        )
        
        if not basic_rate_allowed:
            logger.warning(f"Basic rate limit exceeded for form {form_id} from IP {ip_address}: {basic_rate_reason}")
            return JSONResponse(
                status_code=429,
                content={"status": "error", "message": "Too many requests"}
            )
        
        # Parse form data with error handling for malformed requests
        try:
            form_data = await request.form()
        except Exception as e:
            logger.warning(f"Malformed form data from IP {ip_address} for form {form_id}: {str(e)}")
            
            # Record failed attempt for malformed data (potential attack)
            security_monitor.record_failed_attempt(ip_address, "malformed_form_data")
            
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Invalid form data"}
            )
        
        try:
            submission = await db_form_handler.process_submission(
                form_id=form_id,
                form_data=dict(form_data),
                origin=origin,
                referer=referer,
                ip_address=ip_address,
                user_agent=user_agent,
                request_headers=request_headers
            )
        except HTTPException as e:
            # Record security violations
            if e.status_code == 403:
                error_detail = str(e.detail)
                if any(keyword in error_detail.lower() for keyword in 
                      ["origin", "referer", "javascript", "token", "not allowed"]):
                    security_monitor.record_failed_attempt(ip_address, f"security_violation: {error_detail}")
            raise
        
        # Return response
        if submission.success:
            # Apply per-IP rate limiting only after successful submission
            from app.rate_limiter import rate_limiter
            ip_limit = form_config.get("rate_limit_per_ip_per_minute", 5)
            
            rate_allowed, rate_reason = rate_limiter.is_allowed(
                form_id=form_id,
                ip_address=ip_address,
                ip_limit=ip_limit
            )
            
            if not rate_allowed:
                logger.warning(f"Rate limit exceeded for successful form {form_id} from IP {ip_address}: {rate_reason}")
                return JSONResponse(
                    status_code=429,
                    content={"status": "error", "message": f"Rate limit exceeded: {rate_reason}"}
                )
            
            # Get success message or redirect URL if available
            success_message = "Form submitted successfully"
            redirect_url = None
            
            try:
                # Check if form has custom success message or redirect URL
                form = await FormRepository.get_by_id(db, form_id)
                if form:
                    if form.success_message:
                        success_message = form.success_message
                    if form.redirect_url:
                        redirect_url = form.redirect_url
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving form details: {str(e)}")
                # Continue with default message/redirect
            
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "success", 
                    "message": success_message,
                    "redirect": redirect_url
                }
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"status": "error", "message": f"Failed to process form: {submission.error}"}
            )
    except HTTPException:
        # Re-raise HTTP exceptions (e.g., 403 for invalid origin)
        raise
    except Exception as e:
        logger.error(f"Error processing form submission: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "An error occurred processing your submission"}
        )


@app.options("/api/v1/form/{form_id}/token")
async def options_form_token(form_id: str, request: Request):
    """Handle preflight OPTIONS request for token endpoint."""
    origin = request.headers.get("Origin", "*")
    
    response = Response(status_code=200)
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Origin, X-Requested-With, X-Form-Origin, Referer"
    response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours
    
    return response

@app.get("/api/v1/form/{form_id}/token", status_code=status.HTTP_200_OK)
async def get_form_token(
    form_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config)
):
    """
    Generate a time-limited token for form submission.
    
    This endpoint provides CSRF-like protection by generating tokens that must
    be included with form submissions. Tokens expire after 15 minutes.
    """
    # Get origin and real client information for validation
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")
    client_info = get_client_info(request)
    ip_address = client_info["ip_address"]
    user_agent = client_info["user_agent"]
    
    # Log Cloudflare detection for token requests
    if client_info["is_cloudflare"]:
        logger.debug(f"Cloudflare token request for form {form_id}. Real IP: {ip_address}")
    
    try:
        # Verify the form exists and get its configuration
        from app.database_form_handler import DatabaseFormHandler
        email_sender = EmailSender(config.smtp)
        db_form_handler = DatabaseFormHandler(db, email_sender)
        
        try:
            form_config = await db_form_handler.get_form_config(form_id)
        except HTTPException as e:
            if e.status_code == 404:
                response = JSONResponse(status_code=404, content={"status": "error", "message": "Form not found"})
                response.headers["Access-Control-Allow-Origin"] = origin or "*"
                response.headers["Access-Control-Allow-Credentials"] = "true"
                return response
            raise
        
        # Apply rate limiting for token requests (separate from form submissions)
        from app.rate_limiter import rate_limiter
        ip_limit = form_config.get("rate_limit_per_ip_per_minute", 5)
        
        rate_allowed, rate_reason = rate_limiter.is_allowed(
            form_id=f"token_{form_id}",  # Separate namespace for token requests
            ip_address=ip_address,
            ip_limit=ip_limit
        )
        
        if not rate_allowed:
            logger.warning(f"Rate limit exceeded for token request form {form_id} from IP {ip_address}: {rate_reason}")
            response = JSONResponse(
                status_code=429,
                content={"status": "error", "message": f"Rate limit exceeded: {rate_reason}"}
            )
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            return response
        
        # Validate origin for token generation (same rules as submission)
        allowed_domains = form_config["allowed_domains"]
        if "*" not in allowed_domains:
            origin_valid = origin and db_form_handler.validate_origin(origin, allowed_domains)
            referer_valid = referer and db_form_handler.validate_referer(referer, allowed_domains)
            
            if not (origin_valid or referer_valid):
                logger.warning(f"Invalid origin/referer for token request form {form_id}: origin={origin}, referer={referer}, allowed_domains={allowed_domains}")
                response = JSONResponse(status_code=403, content={
                    "status": "error", 
                    "message": "Invalid origin or referer",
                    "debug": {
                        "origin": origin,
                        "referer": referer,
                        "allowed_domains": allowed_domains
                    }
                })
                response.headers["Access-Control-Allow-Origin"] = origin or "*"
                response.headers["Access-Control-Allow-Credentials"] = "true"
                return response
        
        # Generate a cryptographically secure token
        token = secrets.token_urlsafe(32)  # 256 bits of entropy
        
        # Set expiration time (15 minutes from now)
        expires_at = datetime.now() + timedelta(minutes=15)
        
        # Store the token in the database
        from app.database.repository import FormTokenRepository
        await FormTokenRepository.create(
            db=db,
            form_id=form_id,
            token=token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Clean up expired tokens periodically (1% chance)
        if secrets.randbelow(100) == 0:
            await FormTokenRepository.cleanup_expired_tokens(db)
        
        response = JSONResponse(content={
            "status": "success",
            "token": token,
            "expires_at": expires_at.isoformat(),
            "expires_in": 900  # 15 minutes in seconds
        })
        
        # Add CORS headers for token response
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Origin, X-Requested-With, X-Form-Origin, Referer"
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating token for form {form_id}: {str(e)}")
        response = JSONResponse(status_code=500, content={"status": "error", "message": "Internal server error"})
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response


@app.get("/")
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
    session_token: Optional[str] = Cookie(None, alias="session")
):
    """Render dashboard."""
    # Check authentication
    auth_redirect = login_required_redirect(request, session_token)
    if auth_redirect:
        return auth_redirect
    
    try:
        # Use database storage
        from app.metrics_service import MetricsService
        from app.database_storage import DatabaseStorage
        
        # Get metrics
        metrics_service = MetricsService(db)
        metrics = await metrics_service.get_dashboard_metrics()
        
        # Get recent submissions
        db_storage = DatabaseStorage(db)
        submissions = await db_storage.get_submissions(limit=20)
        
        # Get forms from database
        db_forms = await FormRepository.get_all(db)
        forms = {form.id: form for form in db_forms}
        
        # Get submission counts per form
        form_counts = {}
        for form_id in forms:
            form_counts[form_id] = await db_storage.get_submission_count(form_id)
        
        # Get success rate
        success_rate = metrics.get("success_rate", 0)
        trend_percentage = metrics.get("trend_percentage", 0)
        total_count = metrics.get("total_count", 0)
        
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "submissions": submissions,
                "forms": forms,
                "form_counts": form_counts,
                "total_count": total_count,
                "success_rate": success_rate,
                "trend_percentage": trend_percentage
            }
        )
    except Exception as e:
        logger.error(f"Error rendering dashboard: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return error template
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_message": "An error occurred loading the dashboard",
                "status_code": 500
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.get("/forms")
async def list_forms(
    request: Request,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
    session_token: Optional[str] = Cookie(None, alias="session")
):
    """Render forms list."""
    # Check authentication
    auth_redirect = login_required_redirect(request, session_token)
    if auth_redirect:
        return auth_redirect
    
    try:
        # Get forms from database
        db_forms = await FormRepository.get_all(db)
        forms_dict = {form.id: form for form in db_forms}
        
        # Get submission counts per form
        from app.database_storage import DatabaseStorage
        db_storage = DatabaseStorage(db)
        form_counts = {}
        for form_id in forms_dict:
            form_counts[form_id] = await db_storage.get_submission_count(form_id)
        
        return templates.TemplateResponse(
            "forms.html",
            {
                "request": request, 
                "forms": forms_dict,
                "form_counts": form_counts
            }
        )
    except Exception as e:
        logger.error(f"Error rendering forms list: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return error template
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_message": "An error occurred loading the forms list",
                "status_code": 500
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.get("/metrics")
async def show_metrics(
    request: Request,
    range: str = "month",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    session_token: Optional[str] = Cookie(None, alias="session")
):
    """Show metrics dashboard."""
    # Check authentication
    auth_redirect = login_required_redirect(request, session_token)
    if auth_redirect:
        return auth_redirect
    
    try:
        from app.metrics_service import MetricsService
        from datetime import datetime, timedelta
        
        # Parse date range
        now = datetime.now()
        from_datetime = None
        to_datetime = now
        
        if range == "week":
            from_datetime = now - timedelta(days=7)
        elif range == "month":
            from_datetime = now - timedelta(days=30)
        elif range == "year":
            from_datetime = now - timedelta(days=365)
        elif range == "custom" and from_date:
            try:
                from_datetime = datetime.strptime(from_date, "%Y-%m-%d")
                if to_date:
                    to_datetime = datetime.strptime(to_date, "%Y-%m-%d")
            except ValueError:
                # Invalid date format, fallback to month
                from_datetime = now - timedelta(days=30)
        else:
            # Default to month
            from_datetime = now - timedelta(days=30)
        
        # Get metrics data
        metrics_service = MetricsService(db)
        metrics = await metrics_service.get_full_metrics(from_datetime, to_datetime)
        
        return templates.TemplateResponse(
            "metrics.html",
            {
                "request": request,
                "metrics": metrics,
                "range": range,
                "from_date": from_datetime.strftime("%Y-%m-%d"),
                "to_date": to_datetime.strftime("%Y-%m-%d")
            }
        )
    except Exception as e:
        logger.error(f"Error rendering metrics: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return error template
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_message": "An error occurred loading the metrics dashboard",
                "status_code": 500
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.get("/submissions")
async def all_submissions(
    request: Request,
    page: int = 1,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    form_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    config: Config = Depends(get_config),
    session_token: Optional[str] = Cookie(None, alias="session")
):
    """Show all submissions across all forms."""
    # Check authentication
    auth_redirect = login_required_redirect(request, session_token)
    if auth_redirect:
        return auth_redirect
    
    try:
        from datetime import datetime
        
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
        limit = 20
        skip = (page - 1) * limit
        
        # Use database storage
        from app.database_storage import DatabaseStorage
        
        db_storage = DatabaseStorage(db)
        
        # Get submissions
        submissions = await db_storage.get_submissions(
            form_id=form_id,
            limit=limit,
            skip=skip,
            success=success,
            from_date=from_datetime,
            to_date=to_datetime
        )
        
        # Get total count for pagination
        total_count = await db_storage.get_submission_count(
            form_id=form_id,
            success=success,
            from_date=from_datetime,
            to_date=to_datetime
        )
        
        # Get forms from database
        db_forms = await FormRepository.get_all(db)
        forms = {form.id: form for form in db_forms}
        
        # Calculate total pages
        total_pages = (total_count + limit - 1) // limit
        
        return templates.TemplateResponse(
            "submissions.html",
            {
                "request": request,
                "submissions": submissions,
                "forms": forms,
                "page": page,
                "total_pages": total_pages,
                "total_count": total_count,
                "config": config,
                "status": status,
                "from_date": from_date,
                "to_date": to_date,
                "form_id": form_id
            }
        )
    except Exception as e:
        logger.error(f"Error rendering submissions: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return error template
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_message": "An error occurred loading the submissions",
                "status_code": 500
            },
            status_code=500
        )


@app.get("/login")
async def login_page(
    request: Request,
    next: Optional[str] = None,
    error: Optional[str] = None
):
    """Show login page."""
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "next": next,
            "error": error
        }
    )


@app.post("/login")
async def login_submit(
    request: Request,
    password: str = Form(...),
    next: Optional[str] = Form(None),
    config: Config = Depends(get_config)
):
    """Handle login form submission."""
    if verify_password(password, config):
        # Create session
        session_token = create_session()
        
        # Create response
        redirect_url = next if next else "/"
        response = RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)
        
        # Set session cookie
        response.set_cookie(
            key="session",
            value=session_token,
            max_age=24 * 60 * 60,  # 24 hours
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )
        
        return response
    else:
        # Invalid password
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "next": next,
                "error": "Invalid password"
            },
            status_code=400
        )


@app.get("/logout")
async def logout(
    session_token: Optional[str] = Cookie(None, alias="session")
):
    """Handle logout."""
    # Invalidate session
    invalidate_session(session_token)
    
    # Create response and clear cookie
    response = RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("session")
    
    return response