from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime

from app.storage import StorageInterface, FormSubmission
from app.database.repository import SubmissionRepository, FormRepository
from app.database.models import Submission as DBSubmission


class DatabaseStorage(StorageInterface):
    """Database implementation of StorageInterface."""

    def __init__(self, db_session: AsyncSession):
        """Initialize with a database session."""
        self.db = db_session

    async def save_submission(self, submission: FormSubmission) -> None:
        """Save a form submission to the database."""
        await SubmissionRepository.create(
            db=self.db,
            form_id=submission.form_id,
            data=submission.data,
            success=submission.success,
            error=submission.error,
        )

    async def get_submissions(
        self,
        form_id: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
        success: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[FormSubmission]:
        """Get form submissions from the database with filtering and pagination."""
        if form_id:
            db_submissions = await SubmissionRepository.get_by_form_id(
                db=self.db, form_id=form_id, limit=limit, skip=skip
            )
        else:
            db_submissions = await SubmissionRepository.get_all(
                db=self.db,
                success=success,
                from_date=from_date,
                to_date=to_date,
                skip=skip,
                limit=limit,
            )

        # Filter by success if specified
        if success is not None and form_id:
            db_submissions = [s for s in db_submissions if s.success == success]

        # Filter by date range if specified
        if from_date and form_id:
            db_submissions = [s for s in db_submissions if s.created_at >= from_date]

        if to_date and form_id:
            db_submissions = [s for s in db_submissions if s.created_at <= to_date]

        # Convert DB submissions to FormSubmission objects
        return [
            FormSubmission(
                id=sub.id,  # Include the database ID
                form_id=sub.form_id,
                data=sub.data,
                created_at=sub.created_at,
                success=sub.success,
                error=sub.error,
            )
            for sub in db_submissions
        ]

    async def get_submission_count(
        self,
        form_id: Optional[str] = None,
        success: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> int:
        """Get the count of submissions for a form or all forms with filtering."""
        # Get all stats
        stats = await SubmissionRepository.get_stats(self.db, form_id)

        # Apply filters
        if success is not None:
            if success:
                return stats["success"]
            else:
                return stats["failure"]

        # Date filtering would require more complex queries
        # For simplicity, we'll just return total count for now
        return stats["total"]

    async def get_submission_stats(self) -> Dict:
        """Get submission statistics."""
        return await SubmissionRepository.get_stats(self.db)

    async def get_form_stats(self, form_id: str) -> Dict:
        """Get statistics for a specific form."""
        return await SubmissionRepository.get_stats(self.db, form_id)
