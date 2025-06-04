from prometheus_client import Counter, Gauge, start_http_server

# Initialize metrics
FORM_SUBMISSIONS_TOTAL = Counter(
    "mailbear_form_submissions_total",
    "Total number of form submissions",
    ["form_id", "status"],
)

FORM_SUBMISSIONS_IN_PROGRESS = Gauge(
    "mailbear_form_submissions_in_progress",
    "Number of form submissions being processed",
)

EMAIL_SEND_TOTAL = Counter(
    "mailbear_email_send_total", "Total number of emails sent", ["status"]
)


def start_metrics_server(port: int = 9090):
    """Start Prometheus metrics server on the specified port."""
    start_http_server(port)


def increment_form_submission(form_id: str, success: bool):
    """Increment form submission counter."""
    status = "success" if success else "failure"
    FORM_SUBMISSIONS_TOTAL.labels(form_id=form_id, status=status).inc()


def increment_email_send(success: bool):
    """Increment email send counter."""
    status = "success" if success else "failure"
    EMAIL_SEND_TOTAL.labels(status=status).inc()


def track_in_progress(func):
    """Decorator to track in-progress form submissions."""

    async def wrapper(*args, **kwargs):
        FORM_SUBMISSIONS_IN_PROGRESS.inc()
        try:
            return await func(*args, **kwargs)
        finally:
            FORM_SUBMISSIONS_IN_PROGRESS.dec()

    return wrapper
