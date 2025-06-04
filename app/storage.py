from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional
import json
import os
from pydantic import BaseModel, Field


class FormSubmission(BaseModel):
    form_id: str
    data: Dict[str, str]
    created_at: datetime = Field(default_factory=datetime.now)
    success: bool = False
    error: Optional[str] = None


class StorageInterface(ABC):
    @abstractmethod
    async def save_submission(self, submission: FormSubmission) -> None:
        pass

    @abstractmethod
    async def get_submissions(
        self, form_id: Optional[str] = None, limit: int = 100
    ) -> List[FormSubmission]:
        pass

    @abstractmethod
    async def get_submission_count(self, form_id: Optional[str] = None) -> int:
        pass


class FileStorage(StorageInterface):
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

    async def save_submission(self, submission: FormSubmission) -> None:
        """Save a form submission to file storage."""
        form_dir = os.path.join(self.data_dir, submission.form_id)
        os.makedirs(form_dir, exist_ok=True)

        # Create filename with timestamp
        timestamp = submission.created_at.strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}.json"
        file_path = os.path.join(form_dir, filename)

        # Save submission as JSON
        with open(file_path, "w") as f:
            f.write(submission.model_dump_json())

    async def get_submissions(
        self, form_id: Optional[str] = None, limit: int = 100
    ) -> List[FormSubmission]:
        """Get recent form submissions."""
        submissions = []

        # If form_id is specified, only look in that directory
        if form_id:
            form_dirs = [os.path.join(self.data_dir, form_id)]
        else:
            # Otherwise, look in all form directories
            try:
                form_dirs = [
                    os.path.join(self.data_dir, d) for d in os.listdir(self.data_dir)
                ]
            except FileNotFoundError:
                return []

        # Collect submissions from each form directory
        for form_dir in form_dirs:
            if not os.path.isdir(form_dir):
                continue

            try:
                files = sorted(
                    [f for f in os.listdir(form_dir) if f.endswith(".json")],
                    reverse=True,
                )

                for filename in files[:limit]:
                    file_path = os.path.join(form_dir, filename)
                    with open(file_path, "r") as f:
                        submission_data = json.load(f)
                        submissions.append(FormSubmission(**submission_data))

                    if len(submissions) >= limit:
                        break
            except FileNotFoundError:
                continue

        # Sort by created_at (newest first) and limit results
        submissions.sort(key=lambda x: x.created_at, reverse=True)
        return submissions[:limit]

    async def get_submission_count(self, form_id: Optional[str] = None) -> int:
        """Get the count of submissions for a form or all forms."""
        count = 0

        if form_id:
            form_dir = os.path.join(self.data_dir, form_id)
            try:
                count = len([f for f in os.listdir(form_dir) if f.endswith(".json")])
            except FileNotFoundError:
                count = 0
        else:
            try:
                for form in os.listdir(self.data_dir):
                    form_dir = os.path.join(self.data_dir, form)
                    if os.path.isdir(form_dir):
                        count += len(
                            [f for f in os.listdir(form_dir) if f.endswith(".json")]
                        )
            except FileNotFoundError:
                count = 0

        return count
