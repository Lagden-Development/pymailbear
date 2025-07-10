from typing import List, Optional
import os
import logging
import yaml
import secrets
from pydantic import BaseModel, EmailStr, Field, field_validator, ValidationError
from pydantic_settings import BaseSettings
from functools import lru_cache
from email_validator import validate_email, EmailNotValidError

# Setup logging
logger = logging.getLogger(__name__)


class SMTPConfig(BaseModel):
    """
    SMTP server configuration settings for email delivery.
    """
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    from_email: EmailStr
    use_tls: Optional[bool] = None
    start_tls: Optional[bool] = None
    verify_cert: bool = True
    ssl_context: Optional[str] = None  # For custom SSL context settings
    timeout: int = 60  # Connection timeout in seconds
    
    @field_validator('port')
    @classmethod
    def validate_port(cls, v: int) -> int:
        if v < 1 or v > 65535:
            raise ValueError("SMTP port must be between 1 and 65535")
        return v
    
    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v < 1 or v > 300:
            raise ValueError("SMTP timeout must be between 1 and 300 seconds")
        return v


class DatabaseConfig(BaseModel):
    """
    Database connection configuration.
    """
    host: str = "localhost"
    port: int = 3306
    username: str
    password: str
    dbname: str = "mailbear"
    echo: bool = False  # SQL query logging
    
    @field_validator('port')
    @classmethod
    def validate_port(cls, v: int) -> int:
        if v < 1 or v > 65535:
            raise ValueError("Database port must be between 1 and 65535")
        return v




class SecurityConfig(BaseModel):
    """
    Security-related configuration settings.
    """
    dashboard_password: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day
    rate_limit: int = 5  # requests per minute
    cors_allow_origins: List[str] = ["*"]
    
    @field_validator("dashboard_password")
    @classmethod
    def validate_dashboard_password(cls, v: str) -> str:
        if v == "change_this_to_a_secure_random_string" or len(v) < 16:
            logger.warning("Using weak dashboard password. This should be changed in production.")
        return v
    
    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if v == "supersecret" or len(v) < 32:
            logger.warning("Using weak JWT secret. This should be changed in production.")
        return v
    
    @field_validator("rate_limit")
    @classmethod
    def validate_rate_limit(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Rate limit must be at least 1 request per minute")
        return v


class HcaptchaConfig(BaseModel):
    """
    hCaptcha configuration settings.
    """
    enabled: bool = False
    site_key: Optional[str] = None
    secret_key: Optional[str] = None
    api_url: str = "https://hcaptcha.com/siteverify"
    timeout: int = 10
    invisible: bool = False  # Always Challenge mode by default
    
    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v < 1 or v > 30:
            raise ValueError("hCaptcha timeout must be between 1 and 30 seconds")
        return v


class Config(BaseSettings):
    """
    Main application configuration.
    """
    port: int = 1234
    metrics_port: int = 9090
    smtp: SMTPConfig
    security: SecurityConfig = Field(default_factory=lambda: SecurityConfig(jwt_secret=secrets.token_hex(32)))
    database: DatabaseConfig  # Required now
    hcaptcha: HcaptchaConfig = Field(default_factory=HcaptchaConfig)
    use_db: bool = True  # Always use database
    log_level: str = "INFO"
    debug: bool = False

    @field_validator("port", "metrics_port")
    @classmethod
    def validate_ports(cls, v: int, info) -> int:
        if v < 1 or v > 65535:
            raise ValueError(f"{info.field_name} must be between 1 and 65535")
        return v
    
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()


@lru_cache()
def get_config() -> Config:
    """Get config singleton with caching."""
    return load_config()


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from YAML file with environment variable overrides.
    
    Args:
        config_path: Path to YAML configuration file
        
    Returns:
        Config: Validated configuration object
        
    Raises:
        ValueError: If configuration is invalid or missing
    """
    if config_path is None:
        config_path = os.environ.get("CONFIG_FILE", "config.yml")

    logger.info(f"Loading configuration from {config_path}")
    
    try:
        # Try to read configuration file
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f) or {}
        else:
            logger.warning(f"Config file not found: {config_path}, using environment variables")
            config_data = {}

        # Generate security config with proper secrets
        if "security" not in config_data:
            config_data["security"] = {
                "dashboard_password": os.environ.get("DASHBOARD_PASSWORD", "change_this_to_a_secure_random_string"),
                "jwt_secret": os.environ.get("JWT_SECRET", secrets.token_hex(32)),
                "jwt_algorithm": os.environ.get("JWT_ALGORITHM", "HS256"),
                "access_token_expire_minutes": int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 1440)),
                "rate_limit": int(os.environ.get("RATE_LIMIT", 5))
            }
        else:
            if "dashboard_password" not in config_data["security"]:
                config_data["security"]["dashboard_password"] = os.environ.get("DASHBOARD_PASSWORD", "change_this_to_a_secure_random_string")
            if "jwt_secret" not in config_data["security"]:
                config_data["security"]["jwt_secret"] = os.environ.get("JWT_SECRET", secrets.token_hex(32))
            
        # Override with environment variables
        if "port" not in config_data and "PORT" in os.environ:
            config_data["port"] = int(os.environ.get("PORT"))
            
        if "metrics_port" not in config_data and "METRICS_PORT" in os.environ:
            config_data["metrics_port"] = int(os.environ.get("METRICS_PORT"))
            
        if "log_level" not in config_data and "LOG_LEVEL" in os.environ:
            config_data["log_level"] = os.environ.get("LOG_LEVEL")
            
        if "data_dir" not in config_data and "DATA_DIR" in os.environ:
            config_data["data_dir"] = os.environ.get("DATA_DIR")
        
        # Handle database configuration from environment variables
        if "database" not in config_data:
            if all(os.environ.get(env_var) for env_var in ["DB_HOST", "DB_USER", "DB_PASS", "DB_NAME"]):
                config_data["database"] = {
                    "host": os.environ.get("DB_HOST"),
                    "port": int(os.environ.get("DB_PORT", "3306")),
                    "username": os.environ.get("DB_USER"),
                    "password": os.environ.get("DB_PASS"),
                    "dbname": os.environ.get("DB_NAME"),
                    "echo": os.environ.get("DB_ECHO", "false").lower() == "true",
                }
            else:
                raise ValueError("Database configuration is required. Please provide database settings in config file or environment variables.")
        
        # Force database mode
        config_data["use_db"] = True
        
        # Handle SMTP configuration from environment variables
        if "smtp" not in config_data and all(
            os.environ.get(env_var) for env_var in ["SMTP_HOST", "SMTP_PORT", "SMTP_FROM"]
        ):
            config_data["smtp"] = {
                "host": os.environ.get("SMTP_HOST"),
                "port": int(os.environ.get("SMTP_PORT")),
                "username": os.environ.get("SMTP_USER"),
                "password": os.environ.get("SMTP_PASS"),
                "from_email": os.environ.get("SMTP_FROM"),
                "use_tls": os.environ.get("SMTP_USE_TLS", "").lower() == "true",
                "start_tls": os.environ.get("SMTP_START_TLS", "").lower() == "true",
                "verify_cert": os.environ.get("SMTP_VERIFY_CERT", "true").lower() == "true",
            }

        # Handle hCaptcha configuration from environment variables
        if "hcaptcha" not in config_data:
            config_data["hcaptcha"] = {
                "enabled": os.environ.get("HCAPTCHA_ENABLED", "false").lower() == "true",
                "site_key": os.environ.get("HCAPTCHA_SITE_KEY"),
                "secret_key": os.environ.get("HCAPTCHA_SECRET_KEY"),
                "api_url": os.environ.get("HCAPTCHA_API_URL", "https://hcaptcha.com/siteverify"),
                "timeout": int(os.environ.get("HCAPTCHA_TIMEOUT", "10")),
                "invisible": os.environ.get("HCAPTCHA_INVISIBLE", "false").lower() == "true",
            }

        # Validate and create config
        try:
            return Config(**config_data)
        except ValidationError as e:
            logger.error(f"Configuration validation error: {str(e)}")
            # Try to provide more helpful error messages
            errors = e.errors()
            for error in errors:
                loc = ".".join(str(x) for x in error["loc"])
                logger.error(f"  - {loc}: {error['msg']}")
            raise ValueError("Invalid configuration. See error log for details.")
        
    except FileNotFoundError:
        raise ValueError(f"Config file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {str(e)}")
    except Exception as e:
        logger.error(f"Configuration error: {str(e)}")
        raise ValueError(f"Configuration error: {str(e)}")


def validate_email_address(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        validate_email(email)
        return True
    except EmailNotValidError:
        return False