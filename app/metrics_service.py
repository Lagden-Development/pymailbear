import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
import re
from user_agents import parse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repository import SubmissionRepository, FormRepository
from app.database.models import Submission

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for generating metrics and analytics data."""

    def __init__(self, db_session: AsyncSession):
        """Initialize with a database session."""
        self.db = db_session

    async def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Get basic metrics for the dashboard."""
        # Get total submissions
        stats = await SubmissionRepository.get_stats(self.db)

        # Calculate success rate
        success_rate = 0
        if stats["total"] > 0:
            success_rate = round((stats["success"] / stats["total"]) * 100)

        # Get trend percentage (comparing to previous period)
        # For simplicity, we're comparing to the previous week
        current_date = datetime.now()
        last_week_start = current_date - timedelta(days=7)
        two_weeks_ago_start = current_date - timedelta(days=14)

        current_period_count = await self._get_submission_count_for_period(
            last_week_start, current_date
        )
        previous_period_count = await self._get_submission_count_for_period(
            two_weeks_ago_start, last_week_start
        )

        trend_percentage = 0
        if previous_period_count > 0:
            trend_percentage = round(
                ((current_period_count - previous_period_count) / previous_period_count)
                * 100
            )

        return {
            "total_count": stats["total"],
            "success_rate": success_rate,
            "trend_percentage": trend_percentage,
        }

    async def get_full_metrics(
        self, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get full metrics for the metrics page."""
        # Set default dates if not provided
        if not to_date:
            to_date = datetime.now()
        if not from_date:
            from_date = to_date - timedelta(days=30)

        # Get date ranges for trend comparison
        period_days = (to_date - from_date).days
        previous_from_date = from_date - timedelta(days=period_days)
        previous_to_date = from_date

        # Get submissions for current period
        current_submissions = await SubmissionRepository.get_all(
            self.db,
            from_date=from_date,
            to_date=to_date,
            limit=10000,  # Large limit to get all submissions
        )

        # Get submission counts for both periods
        current_count = len(current_submissions)
        previous_count = await self._get_submission_count_for_period(
            previous_from_date, previous_to_date
        )

        # Calculate trend
        submission_trend = 0
        if previous_count > 0:
            submission_trend = round(
                ((current_count - previous_count) / previous_count) * 100
            )

        # Calculate success rate
        success_count = sum(1 for s in current_submissions if s.success)
        success_rate = 0
        if current_count > 0:
            success_rate = round((success_count / current_count) * 100)

        # Calculate average per day
        avg_per_day = 0
        if period_days > 0:
            avg_per_day = round(current_count / period_days, 1)

        # Generate timeline data
        timeline_data = await self._generate_timeline_data(from_date, to_date)

        # Get form performance data
        forms_data = await self._get_form_performance(
            from_date, to_date, previous_from_date, previous_to_date
        )

        # Parse traffic sources from referrers
        sources_data = self._parse_traffic_sources(current_submissions)

        # Parse device information
        devices_data = self._parse_device_data(current_submissions)

        # Parse error data
        errors_data, top_errors = self._parse_error_data(current_submissions)

        # Calculate conversion rate (simplified)
        conversion_rate = 85  # This would normally be calculated from actual data
        conversion_trend = 2

        return {
            "total_submissions": current_count,
            "success_rate": success_rate,
            "submission_trend": submission_trend,
            "avg_per_day": avg_per_day,
            "conversion_rate": conversion_rate,
            "conversion_trend": conversion_trend,
            "timeline": timeline_data,
            "forms": forms_data,
            "sources": sources_data,
            "devices": devices_data,
            "errors": errors_data,
            "top_errors": top_errors,
        }

    async def _get_submission_count_for_period(
        self, from_date: datetime, to_date: datetime
    ) -> int:
        """Get submission count for a specific period."""
        submissions = await SubmissionRepository.get_all(
            self.db,
            from_date=from_date,
            to_date=to_date,
            limit=1000,  # Use limit for performance
        )
        return len(submissions)

    async def _generate_timeline_data(
        self, from_date: datetime, to_date: datetime
    ) -> Dict[str, List]:
        """Generate timeline data for the chart."""
        # Get all submissions in the period
        submissions = await SubmissionRepository.get_all(
            self.db, from_date=from_date, to_date=to_date, limit=10000
        )

        # Determine interval based on date range
        days_diff = (to_date - from_date).days
        if days_diff <= 14:
            # Daily intervals for short ranges
            interval = "day"
            format_str = "%Y-%m-%d"
            delta = timedelta(days=1)
        elif days_diff <= 90:
            # Weekly intervals for medium ranges
            interval = "week"
            format_str = "%Y-W%W"
            delta = timedelta(days=7)
        else:
            # Monthly intervals for long ranges
            interval = "month"
            format_str = "%Y-%m"
            delta = timedelta(days=30)

        # Group submissions by interval
        grouped_data = defaultdict(lambda: {"total": 0, "success": 0})

        for submission in submissions:
            if interval == "day":
                key = submission.created_at.strftime(format_str)
            elif interval == "week":
                key = submission.created_at.strftime(format_str)
            else:  # month
                key = submission.created_at.strftime(format_str)

            grouped_data[key]["total"] += 1
            if submission.success:
                grouped_data[key]["success"] += 1

        # Generate complete date range
        current = from_date
        dates = []
        while current <= to_date:
            if interval == "day":
                dates.append(current.strftime(format_str))
            elif interval == "week":
                dates.append(current.strftime(format_str))
            else:  # month
                dates.append(current.strftime(format_str))
            current += delta

        # Fill in missing dates
        labels = []
        data = []
        success_data = []

        for date in dates:
            if date in grouped_data:
                total = grouped_data[date]["total"]
                success = grouped_data[date]["success"]
            else:
                total = 0
                success = 0

            labels.append(date)
            data.append(total)
            success_data.append(success)

        return {"labels": labels, "data": data, "success_data": success_data}

    async def _get_form_performance(
        self,
        from_date: datetime,
        to_date: datetime,
        previous_from_date: datetime,
        previous_to_date: datetime,
    ) -> List[Dict[str, Any]]:
        """Get performance data for each form."""
        # Get all forms
        forms = await FormRepository.get_all(self.db)

        result = []

        for form in forms:
            # Get current period submissions
            current_submissions = await SubmissionRepository.get_by_form_id(
                self.db,
                form_id=form.id,
                from_date=from_date,
                to_date=to_date,
                limit=1000,
            )

            # Get previous period submissions
            previous_submissions = await SubmissionRepository.get_by_form_id(
                self.db,
                form_id=form.id,
                from_date=previous_from_date,
                to_date=previous_to_date,
                limit=1000,
            )

            # Calculate metrics
            current_count = len(current_submissions)
            previous_count = len(previous_submissions)

            # Success rate
            success_count = sum(1 for s in current_submissions if s.success)
            success_rate = 0
            if current_count > 0:
                success_rate = round((success_count / current_count) * 100)

            # Trend
            trend = 0
            if previous_count > 0:
                trend = round(((current_count - previous_count) / previous_count) * 100)

            # Add form data
            result.append(
                {
                    "id": form.id,
                    "name": form.name,
                    "submissions": current_count,
                    "success_rate": success_rate,
                    "conversion_rate": 80 + success_rate // 5,  # Simplified calculation
                    "trend": trend,
                }
            )

        # Sort by submissions count
        result.sort(key=lambda x: x["submissions"], reverse=True)

        return result

    def _parse_traffic_sources(self, submissions: List[Submission]) -> Dict[str, List]:
        """Parse traffic sources from submission data."""
        # In a real application, you would extract referrer information from user_agent or other fields
        # Here we're simulating the data
        sources = {
            "Direct": 40,
            "Google": 25,
            "Social Media": 15,
            "Referral": 12,
            "Other": 8,
        }

        return {"labels": list(sources.keys()), "data": list(sources.values())}

    def _parse_device_data(self, submissions: List[Submission]) -> Dict[str, List]:
        """Parse device data from user agents."""
        # In a real application, you would parse the user_agent field
        # Here we're simulating the data
        devices = {"Desktop": 65, "Mobile": 30, "Tablet": 5}

        return {"labels": list(devices.keys()), "data": list(devices.values())}

    def _parse_error_data(
        self, submissions: List[Submission]
    ) -> Tuple[Dict[str, List], List[Dict[str, Any]]]:
        """Parse error data from submissions."""
        # Count errors by type
        error_types = Counter()
        error_messages = []

        for submission in submissions:
            if not submission.success and submission.error:
                # Simplify error message to categorize
                error = submission.error

                # Extract main error type
                if "connection" in error.lower():
                    error_type = "Connection Error"
                elif "timeout" in error.lower():
                    error_type = "Timeout"
                elif "authentication" in error.lower() or "auth" in error.lower():
                    error_type = "Authentication Error"
                elif "recipient" in error.lower():
                    error_type = "Invalid Recipient"
                else:
                    error_type = "Other Error"

                error_types[error_type] += 1
                error_messages.append(error)

        # Get most common errors
        common_errors = error_types.most_common(5)
        labels = [item[0] for item in common_errors]
        data = [item[1] for item in common_errors]

        # Count all errors
        total_errors = sum(data)

        # Create top errors list
        top_errors = []
        error_counter = Counter(error_messages)

        for message, count in error_counter.most_common(5):
            percentage = 0
            if total_errors > 0:
                percentage = round((count / total_errors) * 100)

            top_errors.append(
                {
                    "message": message if len(message) < 50 else message[:47] + "...",
                    "count": count,
                    "percentage": percentage,
                }
            )

        return {"labels": labels, "data": data}, top_errors
