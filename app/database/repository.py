from sqlalchemy import select, func, desc, and_, or_, Integer, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any, Tuple
import uuid
from datetime import datetime, timedelta

from app.database.models import (
    User,
    Form,
    FormDomain,
    Submission,
    FormTemplate,
    APIKey,
    Setting,
    FormToken,
)


class UserRepository:
    """Repository for User operations."""

    @staticmethod
    async def create(
        db: AsyncSession,
        email: str,
        password_hash: str,
        name: Optional[str] = None,
        role: str = "user",
    ) -> User:
        """Create a new user."""
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=password_hash,
            name=name,
            role=role,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return await db.get(User, user_id)

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email."""
        query = select(User).where(User.email == email)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_last_login(db: AsyncSession, user_id: str) -> None:
        """Update user's last login time."""
        user = await db.get(User, user_id)
        if user:
            user.last_login = datetime.now()
            await db.commit()


class FormRepository:
    """Repository for Form operations."""

    @staticmethod
    async def create(
        db: AsyncSession,
        name: str,
        to_emails: str,  # Comma-separated list of emails
        from_email: str,
        subject: str = "New form submission",
        description: Optional[str] = None,
        success_message: Optional[str] = None,
        redirect_url: Optional[str] = None,
        honeypot_enabled: bool = False,
        honeypot_field: str = "_honeypot",
        hcaptcha_enabled: bool = False,
        hcaptcha_site_key: Optional[str] = None,
        hcaptcha_secret_key: Optional[str] = None,
        max_field_length: int = 5000,
        max_fields: int = 50,
        max_file_size: int = 10485760,
        rate_limit_per_ip_per_minute: int = 5,
        user_id: Optional[str] = None,
        allowed_domains: Optional[List[str]] = None,
    ) -> Form:
        """Create a new form."""
        form_id = str(uuid.uuid4())
        form = Form(
            id=form_id,
            name=name,
            description=description,
            to_emails=to_emails,
            from_email=from_email,
            subject=subject,
            success_message=success_message,
            redirect_url=redirect_url,
            honeypot_enabled=honeypot_enabled,
            honeypot_field=honeypot_field,
            hcaptcha_enabled=hcaptcha_enabled,
            hcaptcha_site_key=hcaptcha_site_key,
            hcaptcha_secret_key=hcaptcha_secret_key,
            max_field_length=max_field_length,
            max_fields=max_fields,
            max_file_size=max_file_size,
            rate_limit_per_ip_per_minute=rate_limit_per_ip_per_minute,
            user_id=user_id,
        )

        db.add(form)

        # Add allowed domains if provided
        if allowed_domains:
            for domain in allowed_domains:
                form_domain = FormDomain(form_id=form_id, domain=domain)
                db.add(form_domain)

        await db.commit()
        await db.refresh(form)
        return form

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        form_id: str,
    ) -> Optional[Form]:
        """Get form by ID with related data."""
        query = select(Form).where(Form.id == form_id)

        # Always include domains
        query = query.options(selectinload(Form.domains))

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(
        db: AsyncSession,
        user_id: Optional[str] = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Form]:
        """Get all forms, optionally filtered by user_id."""
        query = select(Form).options(selectinload(Form.domains))

        if user_id:
            query = query.where(Form.user_id == user_id)

        if active_only:
            query = query.where(Form.active == True)

        query = query.order_by(Form.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        form_id: str,
        data: Dict[str, Any],
        allowed_domains: Optional[List[str]] = None,
    ) -> Optional[Form]:
        """Update a form."""
        form = await FormRepository.get_by_id(db, form_id)
        if not form:
            return None

        # Update form attributes
        for key, value in data.items():
            if hasattr(form, key) and key != "id":
                setattr(form, key, value)

        # Update domains if provided
        if allowed_domains is not None:
            # Delete existing domains
            await db.execute(
                delete(FormDomain).where(FormDomain.form_id == form_id)
            )

            # Add new domains
            for domain in allowed_domains:
                form_domain = FormDomain(form_id=form_id, domain=domain)
                db.add(form_domain)

        await db.commit()
        await db.refresh(form)
        return form

    @staticmethod
    async def delete(db: AsyncSession, form_id: str) -> bool:
        """Delete a form."""
        form = await FormRepository.get_by_id(db, form_id)
        if not form:
            return False

        await db.delete(form)
        await db.commit()
        return True


class SubmissionRepository:
    """Repository for Submission operations."""

    @staticmethod
    async def create(
        db: AsyncSession,
        form_id: str,
        data: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = False,
        error: Optional[str] = None,
    ) -> Submission:
        """Create a new submission."""
        submission = Submission(
            id=str(uuid.uuid4()),
            form_id=form_id,
            data=data,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error=error,
        )

        db.add(submission)
        await db.commit()
        await db.refresh(submission)
        return submission

    @staticmethod
    async def get_by_id(db: AsyncSession, submission_id: str) -> Optional[Submission]:
        """Get submission by ID."""
        return await db.get(Submission, submission_id)

    @staticmethod
    async def get_by_form_id(
        db: AsyncSession,
        form_id: str,
        skip: int = 0,
        limit: int = 100,
        success: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Submission]:
        """Get submissions for a specific form with filtering and pagination."""
        query = select(Submission).where(Submission.form_id == form_id)

        # Apply filters
        filters = []

        if success is not None:
            filters.append(Submission.success == success)

        if from_date:
            filters.append(Submission.created_at >= from_date)

        if to_date:
            filters.append(Submission.created_at <= to_date)

        if filters:
            query = query.where(and_(*filters))

        # Order and paginate
        query = query.order_by(Submission.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_all(
        db: AsyncSession,
        search: Optional[str] = None,
        success: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Submission]:
        """Get all submissions with optional filtering."""
        query = select(Submission).options(selectinload(Submission.form))

        # Apply filters
        filters = []

        if success is not None:
            filters.append(Submission.success == success)

        if from_date:
            filters.append(Submission.created_at >= from_date)

        if to_date:
            filters.append(Submission.created_at <= to_date)

        if filters:
            query = query.where(and_(*filters))

        # Order and paginate
        query = query.order_by(Submission.created_at.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_stats(
        db: AsyncSession, form_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get submission statistics."""
        # Base query for total count
        count_query = select(func.count(Submission.id))
        success_query = select(func.count(Submission.id)).where(
            Submission.success == True
        )
        failure_query = select(func.count(Submission.id)).where(
            Submission.success == False
        )

        if form_id:
            count_query = count_query.where(Submission.form_id == form_id)
            success_query = success_query.where(Submission.form_id == form_id)
            failure_query = failure_query.where(Submission.form_id == form_id)

        total_count = await db.execute(count_query)
        success_count = await db.execute(success_query)
        failure_count = await db.execute(failure_query)

        # Get stats per form
        form_stats_query = select(
            Submission.form_id,
            func.count(Submission.id).label("total"),
            func.sum(func.cast(Submission.success, Integer)).label("success_count"),
        ).group_by(Submission.form_id)

        form_stats_result = await db.execute(form_stats_query)
        form_stats = {
            form_id: {
                "total": total,
                "success": success_count or 0,
                "failure": total - (success_count or 0),
            }
            for form_id, total, success_count in form_stats_result
        }

        return {
            "total": total_count.scalar() or 0,
            "success": success_count.scalar() or 0,
            "failure": failure_count.scalar() or 0,
            "by_form": form_stats,
        }

    @staticmethod
    async def delete(db: AsyncSession, submission_id: str) -> bool:
        """Delete a submission by ID."""
        submission = await db.get(Submission, submission_id)
        if not submission:
            return False
        
        await db.delete(submission)
        await db.commit()
        return True


class FormTemplateRepository:
    """Repository for FormTemplate operations."""

    @staticmethod
    async def create(
        db: AsyncSession,
        name: str,
        fields: Dict[str, Any],
        description: Optional[str] = None,
        user_id: Optional[str] = None,
        public: bool = False,
    ) -> FormTemplate:
        """Create a new form template."""
        template = FormTemplate(
            name=name,
            description=description,
            fields=fields,
            user_id=user_id,
            public=public,
        )

        db.add(template)
        await db.commit()
        await db.refresh(template)
        return template

    @staticmethod
    async def get_by_id(db: AsyncSession, template_id: int) -> Optional[FormTemplate]:
        """Get template by ID."""
        return await db.get(FormTemplate, template_id)

    @staticmethod
    async def get_all(
        db: AsyncSession,
        user_id: Optional[str] = None,
        public_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[FormTemplate]:
        """Get all templates, optionally filtered by user_id or public status."""
        query = select(FormTemplate)

        if user_id and public_only:
            query = query.where(
                or_(FormTemplate.user_id == user_id, FormTemplate.public == True)
            )
        elif user_id:
            query = query.where(FormTemplate.user_id == user_id)
        elif public_only:
            query = query.where(FormTemplate.public == True)

        query = query.order_by(FormTemplate.name).offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())


class APIKeyRepository:
    """Repository for APIKey operations."""

    @staticmethod
    async def create(
        db: AsyncSession, user_id: str, name: str, key_hash: str
    ) -> APIKey:
        """Create a new API key."""
        api_key = APIKey(
            id=str(uuid.uuid4()), user_id=user_id, name=name, key_hash=key_hash
        )

        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        return api_key

    @staticmethod
    async def get_by_id(db: AsyncSession, key_id: str) -> Optional[APIKey]:
        """Get API key by ID."""
        return await db.get(APIKey, key_id)

    @staticmethod
    async def get_by_hash(db: AsyncSession, key_hash: str) -> Optional[APIKey]:
        """Get API key by hash."""
        query = select(APIKey).where(
            and_(APIKey.key_hash == key_hash, APIKey.active == True)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_user(
        db: AsyncSession, user_id: str, active_only: bool = True
    ) -> List[APIKey]:
        """Get API keys for a user."""
        query = select(APIKey).where(APIKey.user_id == user_id)

        if active_only:
            query = query.where(APIKey.active == True)

        query = query.order_by(APIKey.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_last_used(db: AsyncSession, key_id: str) -> None:
        """Update API key's last used time."""
        api_key = await db.get(APIKey, key_id)
        if api_key:
            api_key.last_used = datetime.now()
            await db.commit()

    @staticmethod
    async def deactivate(db: AsyncSession, key_id: str) -> bool:
        """Deactivate an API key."""
        api_key = await db.get(APIKey, key_id)
        if not api_key:
            return False

        api_key.active = False
        await db.commit()
        return True


class SettingRepository:
    """Repository for Setting operations."""

    @staticmethod
    async def get(db: AsyncSession, key: str) -> Optional[str]:
        """Get a setting value by key."""
        query = select(Setting).where(Setting.key == key)
        result = await db.execute(query)
        setting = result.scalar_one_or_none()
        return setting.value if setting else None

    @staticmethod
    async def set(
        db: AsyncSession, key: str, value: str, description: Optional[str] = None
    ) -> Setting:
        """Set a setting value."""
        query = select(Setting).where(Setting.key == key)
        result = await db.execute(query)
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = value
            if description:
                setting.description = description
        else:
            setting = Setting(key=key, value=value, description=description)
            db.add(setting)

        await db.commit()
        await db.refresh(setting)
        return setting

    @staticmethod
    async def get_all(db: AsyncSession) -> Dict[str, str]:
        """Get all settings as a dictionary."""
        query = select(Setting)
        result = await db.execute(query)
        settings = result.scalars().all()
        return {setting.key: setting.value for setting in settings}


class FormTokenRepository:
    """Repository for FormToken operations."""

    @staticmethod
    async def create(
        db: AsyncSession,
        form_id: str,
        token: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> FormToken:
        """Create a new form token."""
        form_token = FormToken(
            id=str(uuid.uuid4()),
            form_id=form_id,
            token=token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        db.add(form_token)
        await db.commit()
        await db.refresh(form_token)
        return form_token

    @staticmethod
    async def get_by_token(db: AsyncSession, token: str) -> Optional[FormToken]:
        """Get a form token by token value."""
        query = select(FormToken).where(FormToken.token == token)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_form_and_token(
        db: AsyncSession, form_id: str, token: str
    ) -> Optional[FormToken]:
        """Get a form token by form ID and token value."""
        query = select(FormToken).where(
            and_(FormToken.form_id == form_id, FormToken.token == token)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def mark_as_used(db: AsyncSession, token_id: str) -> bool:
        """Mark a token as used."""
        token = await db.get(FormToken, token_id)
        if not token:
            return False

        token.used = True
        await db.commit()
        return True

    @staticmethod
    async def cleanup_expired_tokens(db: AsyncSession) -> int:
        """Remove expired tokens and return count of deleted tokens."""
        now = datetime.now()
        query = delete(FormToken).where(FormToken.expires_at < now)
        result = await db.execute(query)
        await db.commit()
        return result.rowcount

    @staticmethod
    async def cleanup_used_tokens(db: AsyncSession, older_than_hours: int = 24) -> int:
        """Remove used tokens older than specified hours."""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        query = delete(FormToken).where(
            and_(FormToken.used == True, FormToken.created_at < cutoff_time)
        )
        result = await db.execute(query)
        await db.commit()
        return result.rowcount
