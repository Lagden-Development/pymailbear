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
    
    # hCaptcha configuration
    hcaptcha_enabled = Column(Boolean, default=False, nullable=False)
    hcaptcha_site_key = Column(String(255))
    hcaptcha_secret_key = Column(String(255))
    
    # Field validation limits
    max_field_length = Column(Integer, default=5000, nullable=False)  # Maximum length for any field
    max_fields = Column(Integer, default=50, nullable=False)  # Maximum number of fields allowed
    max_file_size = Column(Integer, default=10485760, nullable=False)  # 10MB in bytes
    
    # Rate limiting settings
    rate_limit_per_ip_per_minute = Column(Integer, default=5, nullable=False)  # Per-IP form submissions per minute
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    active = Column(Boolean, default=True, nullable=False)

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
    tokens = relationship(
        "FormToken", back_populates="form", cascade="all, delete-orphan"
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


class FormToken(Base):
    """Model for time-based form submission tokens."""
    
    __tablename__ = "form_tokens"
    
    id = Column(String(36), primary_key=True)
    form_id = Column(String(36), ForeignKey("forms.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    ip_address = Column(String(45), nullable=True)  # Support IPv6
    user_agent = Column(Text, nullable=True)
    
    # Relationship
    form = relationship("Form", back_populates="tokens")
    
    # Index for cleanup operations
    __table_args__ = (
        Index('idx_form_tokens_expires_at', 'expires_at'),
        Index('idx_form_tokens_form_id_token', 'form_id', 'token'),
    )
    
    def __repr__(self):
        return f"<FormToken {self.token[:8]}... for form {self.form_id}>"
