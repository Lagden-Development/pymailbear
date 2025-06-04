from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    Text,
    ForeignKey,
    DateTime,
    Enum,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.database.connection import Base


def generate_uuid():
    """Generate a UUID string."""
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100))
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime)
    role = Column(Enum("admin", "user"), default="user", nullable=False)

    forms = relationship("Form", back_populates="user")
    api_keys = relationship("APIKey", back_populates="user")

    def __repr__(self):
        return f"<User {self.email}>"


class Form(Base):
    __tablename__ = "forms"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    to_emails = Column(Text, nullable=False)  # Comma-separated list of emails
    from_email = Column(String(255), nullable=False)
    subject = Column(String(255), default="New form submission", nullable=False)
    success_message = Column(Text)
    redirect_url = Column(String(255))
    honeypot_enabled = Column(Boolean, default=False, nullable=False)
    honeypot_field = Column(String(50), default="_honeypot")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    active = Column(Boolean, default=True, nullable=False)

    # Multi-step form configuration
    multi_step_enabled = Column(Boolean, default=False, nullable=False)
    show_progress_indicator = Column(Boolean, default=True, nullable=False)
    progress_indicator_type = Column(
        Enum("steps", "progress-bar", "dots"), default="steps", nullable=False
    )

    # User relationship (optional, a form could be owned by a user)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    user = relationship("User", back_populates="forms")

    # Relationships
    domains = relationship(
        "FormDomain", back_populates="form", cascade="all, delete-orphan"
    )
    submissions = relationship(
        "Submission", back_populates="form", cascade="all, delete-orphan"
    )
    steps = relationship(
        "FormStep",
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="FormStep.step_order",
    )

    def __repr__(self):
        return f"<Form {self.name}>"


class FormDomain(Base):
    __tablename__ = "form_domains"

    id = Column(Integer, primary_key=True, autoincrement=True)
    form_id = Column(
        String(36), ForeignKey("forms.id", ondelete="CASCADE"), nullable=False
    )
    domain = Column(String(255), nullable=False)

    # Relationships
    form = relationship("Form", back_populates="domains")

    # Constraints
    __table_args__ = (UniqueConstraint("form_id", "domain", name="uix_form_domain"),)

    def __repr__(self):
        return f"<FormDomain {self.domain}>"


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    form_id = Column(
        String(36), ForeignKey("forms.id", ondelete="CASCADE"), nullable=False
    )
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=func.now())
    ip_address = Column(String(45))
    user_agent = Column(Text)
    success = Column(Boolean, default=False, nullable=False)
    error = Column(Text)

    # Relationships
    form = relationship("Form", back_populates="submissions")

    # Indexes
    __table_args__ = (Index("idx_form_created", form_id, created_at.desc()),)

    def __repr__(self):
        return f"<Submission {self.id[:8]}>"


class FormTemplate(Base):
    __tablename__ = "form_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    fields = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=func.now())
    public = Column(Boolean, default=False, nullable=False)

    # User relationship (optional, a template could be created by a user)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"))

    def __repr__(self):
        return f"<FormTemplate {self.name}>"


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    key_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=func.now())
    last_used = Column(DateTime)
    active = Column(Boolean, default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="api_keys")

    def __repr__(self):
        return f"<APIKey {self.name}>"


class FormStep(Base):
    __tablename__ = "form_steps"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    form_id = Column(
        String(36), ForeignKey("forms.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(100), nullable=False)
    description = Column(Text)
    step_order = Column(Integer, nullable=False)
    fields = Column(JSON)  # Field configurations for this step
    required_fields = Column(JSON)  # Fields that must be filled before proceeding
    next_button_text = Column(String(50), default="Next", nullable=False)
    previous_button_text = Column(String(50), default="Previous", nullable=False)

    # Relationships
    form = relationship("Form", back_populates="steps")
    conditions = relationship(
        "FormStepCondition", back_populates="step", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("form_id", "step_order", name="uix_form_step_order"),
    )

    def __repr__(self):
        return f"<FormStep {self.title} (Order: {self.step_order})>"


class FormStepCondition(Base):
    __tablename__ = "form_step_conditions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    step_id = Column(
        String(36), ForeignKey("form_steps.id", ondelete="CASCADE"), nullable=False
    )
    field_name = Column(String(100), nullable=False)  # Field to check
    operator = Column(
        Enum(
            "equals",
            "not_equals",
            "contains",
            "not_contains",
            "greater_than",
            "less_than",
        ),
        nullable=False,
    )
    value = Column(String(255), nullable=False)  # Value to compare against
    next_step_order = Column(
        Integer, nullable=False
    )  # Which step to go to if condition is met

    # Relationships
    step = relationship("FormStep")

    def __repr__(self):
        return f"<FormStepCondition {self.field_name} {self.operator} {self.value}>"


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(Text)
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Setting {self.key}>"
