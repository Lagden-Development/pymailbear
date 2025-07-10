# MailBear Project Documentation

## Project Overview

MailBear is a form submission to email service that allows websites to easily collect form data and send it via email. It provides:

- Form to email conversion
- Spam protection mechanisms (honeypot, reCAPTCHA v3)
- Database-driven form management
- Field validation limits
- File upload handling
- Analytics and metrics
- Admin dashboard with developer-focused API documentation

## Core Files

### Entry Points

- `main.py`: The main entry point that starts the Uvicorn server for the FastAPI application. Configures logging and sets up the server on port 1234 (configurable).

- `init_db.py`: Standalone script to initialize the database schema. Creates all tables defined in the SQLAlchemy models. Can drop existing tables with the `--drop` flag.

- `create_admin.py`: Utility script for creating admin users in the database. Prompts for email, name, and password, then creates an admin user account.

### Configuration

- `config_sample.yml`: Sample configuration file showing all available configuration options:
  - Server settings (port, rate limiting, etc.)
  - Database configuration (required)
  - SMTP configuration
  - reCAPTCHA settings

- `app/config.py`: Handles configuration loading and validation:
  - Defines Pydantic models for configuration validation (SMTPConfig, DatabaseConfig, SecurityConfig, RecaptchaConfig)
  - Loads configuration from YAML files
  - Supports environment variable overrides
  - Provides singleton access to the configuration
  - Includes validation for security settings (password strength, JWT secrets)

## API and Routing

- `app/api.py`: Core FastAPI application with main routes:
  - Defines FastAPI app and middleware (CORS, rate limiting)
  - Handles form submission endpoint (/api/v1/form/{form_id})
  - Renders dashboard pages (/, /forms, /metrics, /submissions)
  - Serves JavaScript for forms (/api/v1/form/{form_id}/js)
  - Authentication routes (/login, /logout)
  - Includes the form controller router
  - Sets up application startup events

- `app/form_controller.py`: Handles form management routes:
  - Form creation, editing, viewing, and deletion
  - Form submission management
  - Multi-step form configuration
  - Form domain management

- `app/auth.py`: Authentication module for dashboard access:
  - Session-based authentication with in-memory storage
  - Password verification against configured dashboard password
  - Session token generation and validation
  - Authentication middleware and dependencies

## Form Processing

- `app/database_form_handler.py`: Handles all form submissions with database storage:
  - Fetches form configuration from database
  - Validates field limits (length, count)
  - Validates form origins against allowed domains
  - Checks for honeypot fields to prevent spam
  - Processes reCAPTCHA verification when enabled
  - Processes file uploads and attachments
  - Sends emails to multiple recipients
  - Stores submissions in the database
  - Tracks metrics for form submissions

- `app/email_sender.py`: Handles sending emails:
  - Configures SMTP connections with various security options
  - Formats HTML emails with form data
  - Handles file attachments
  - Provides error handling for email sending failures


## Storage

- `app/database_storage.py`: Database implementation for all storage operations:
  - Stores submissions in the database
  - Provides filtering and pagination
  - Generates submission statistics
  - Supports advanced querying and analytics

## Database

- `app/database/models.py`: SQLAlchemy ORM models:
  - User: User accounts for administration
  - Form: Form configuration with reCAPTCHA settings and validation limits
  - FormDomain: Allowed domains for forms
  - Submission: Form submissions with IP tracking
  - FormTemplate: Reusable form templates
  - APIKey: API authentication
  - Setting: Application settings

- `app/database/repository.py`: Repository pattern implementation:
  - Provides data access methods for each model
  - Separates business logic from database operations
  - Includes query methods, CRUD operations, and statistics

- `app/database/connection.py`: Database connection management:
  - Sets up database URL
  - Defines Base model
  - Provides AsyncSession dependency for FastAPI

- `app/database/init_db.py`: Database initialization module:
  - Creates tables if they don't exist
  - Handles initial database setup

## Metrics and Analytics

- `app/metrics.py`: Prometheus metrics collection:
  - Tracks form submissions
  - Monitors email sends
  - Provides in-progress tracking
  - Exposes metrics HTTP server

- `app/metrics_service.py`: Generates analytics data:
  - Provides dashboard metrics
  - Creates timeline data
  - Analyzes traffic sources and device information
  - Generates error data

## Security and Anti-Spam

- `app/hcaptcha_service.py`: hCaptcha integration service:
  - Verifies hCaptcha tokens with hCaptcha's API
  - Supports Always Challenge mode for maximum security
  - Handles both global and per-form hCaptcha keys
  - Provides comprehensive error handling and logging

## Migration Scripts

- `migrations/001_add_recaptcha_fields.py`: Database migration to add reCAPTCHA fields to forms table (legacy)
- `migrations/001_add_recaptcha_fields.sql`: SQL version of the reCAPTCHA migration (legacy)
- `migrations/002_remove_multistep_forms.py`: Database migration to remove multi-step form functionality
- `migrations/002_remove_multistep_forms.sql`: SQL version of the multi-step removal migration
- `migrations/003_add_validation_limits.py`: Database migration to add field validation limits
- `migrations/003_add_validation_limits.sql`: SQL version of the validation limits migration
- `migrations/004_switch_to_hcaptcha.py`: Database migration to switch from reCAPTCHA to hCaptcha
- `migrations/004_switch_to_hcaptcha.sql`: SQL version of the hCaptcha migration

## Testing

- `test_recaptcha.py`: Comprehensive test suite for reCAPTCHA functionality (legacy)
- `test_recaptcha_simple.py`: Simple test script for basic reCAPTCHA verification (legacy)

## Documentation

- `RECAPTCHA_SETUP.md`: Complete setup guide for reCAPTCHA integration (legacy)

## Templates

- `templates/layout.html`: Base template with common layout and navigation
- `templates/dashboard.html`: Main dashboard showing form statistics and recent submissions
- `templates/forms.html`: Form listing page with creation and management options
- `templates/form_edit.html`: Form creation and editing interface with security and validation settings
- `templates/form_view.html`: Developer-focused API documentation for individual forms
- `templates/form_submissions.html`: Form-specific submission history
- `templates/submissions.html`: Global submission history with filtering
- `templates/metrics.html`: Analytics dashboard with charts and metrics
- `templates/login.html`: Authentication page for dashboard access
- `templates/error.html`: Error page template for handling exceptions

## Dependencies and Relationships

1. The FastAPI application in `app/api.py` depends on:
   - Configuration from `app/config.py`
   - Form handler from `app/database_form_handler.py` (database-only mode)
   - Storage from `app/database_storage.py` (database-only mode)
   - Authentication from `app/auth.py`

2. Form handlers depend on:
   - Email sender from `app/email_sender.py`
   - Storage implementations
   - Metrics from `app/metrics.py`
   - reCAPTCHA service from `app/recaptcha_service.py`

3. Database components rely on:
   - Models from `app/database/models.py`
   - Connection setup from `app/database/connection.py`
   - Repository pattern from `app/database/repository.py`

## Common Commands

### Running the Application

```bash
# Start the application using the default config.yml file
python main.py

# Start with a specific config file
CONFIG_FILE=/path/to/config.yml python main.py

# Run with environment variables for database
DB_HOST=localhost DB_USER=user DB_PASS=password DB_NAME=mailbear python main.py
```

### Migration from Previous Version

If you're upgrading from a previous version:

```bash
# Run the reCAPTCHA migration to add reCAPTCHA fields
python migrations/001_add_recaptcha_fields.py

# Or use SQL directly
mysql -u username -p database_name < migrations/001_add_recaptcha_fields.sql
```

### Database Management

```bash
# Initialize the database (create tables)
python init_db.py

# Reset the database (drop and recreate tables)
python init_db.py --drop

# Create an admin user
python create_admin.py
```

### Database Migrations

```bash
# Run the multi-step removal migration
python migrations/002_remove_multistep_forms.py

# Run the validation limits migration
python migrations/003_add_validation_limits.py

# Or use SQL directly
mysql -u username -p database_name < migrations/002_remove_multistep_forms.sql
mysql -u username -p database_name < migrations/003_add_validation_limits.sql
```

### Testing

```bash
# Test reCAPTCHA functionality
python test_recaptcha_simple.py

# Run comprehensive reCAPTCHA tests
python test_recaptcha.py
```

## Storage Mode

MailBear operates in **database-only mode** for enhanced functionality:

- All forms are created and managed through the web dashboard
- Supports multiple email recipients per form
- Field validation limits (length, count, file size)
- Advanced analytics and metrics
- Form templates and API key management
- Comprehensive submission tracking
- reCAPTCHA v3 integration for spam protection
- Session-based authentication for dashboard access
- Developer-focused API documentation for each form

Database configuration is required in config.yml.

## hCaptcha Integration

MailBear supports hCaptcha integration to prevent spam and bot submissions. hCaptcha uses "Always Challenge" mode for maximum security and is much harder to bypass than reCAPTCHA v3. hCaptcha can be configured globally or per-form.

### Setup Steps

1. **Get hCaptcha Keys**
   - Visit [hCaptcha Dashboard](https://dashboard.hcaptcha.com/)
   - Create a new site and select hCaptcha
   - Note down your Site Key and Secret Key

2. **Database Migration**
   ```bash
   # Run the migration to switch from reCAPTCHA to hCaptcha
   python migrations/004_switch_to_hcaptcha.py
   ```

3. **Configuration**
   
   **Global Configuration (config.yml):**
   ```yaml
   hcaptcha:
     enabled: true
     site_key: "your_site_key_here"
     secret_key: "your_secret_key_here"
     timeout: 10
     invisible: false  # Always Challenge mode
   ```
   
   **Environment Variables:**
   ```bash
   HCAPTCHA_ENABLED=true
   HCAPTCHA_SITE_KEY=your_site_key_here
   HCAPTCHA_SECRET_KEY=your_secret_key_here
   HCAPTCHA_TIMEOUT=10
   HCAPTCHA_INVISIBLE=false
   ```

4. **Per-Form Configuration**
   - Access the form editor in the web dashboard
   - Enable "hCaptcha Protection" checkbox
   - Enter form-specific Site Key and Secret Key (optional)
   - Always Challenge mode provides consistent security

### How it Works

1. **Frontend Integration**: When hCaptcha is enabled, the JavaScript loads the hCaptcha widget which presents users with a challenge in Always Challenge mode.

2. **Backend Verification**: The server verifies the token with hCaptcha's API to ensure the challenge was completed successfully.

3. **Always Challenge Mode**: Unlike score-based systems, hCaptcha Always Challenge mode provides consistent challenge presentation, making it much harder for bots to bypass.

### Configuration Options

- **enabled**: Enable/disable hCaptcha globally
- **site_key**: Your hCaptcha site key (public)
- **secret_key**: Your hCaptcha secret key (private)
- **timeout**: API request timeout in seconds
- **invisible**: Set to false for Always Challenge mode (recommended)

### Security Benefits

- **Always Challenge**: Consistent challenge presentation for all users
- **Harder to Bypass**: Limited captcha solver support for hCaptcha
- **No Score Dependency**: No threshold tuning required
- **Better Bot Detection**: More robust against automated attacks

### Security Notes

- Always keep your secret key private
- Never expose secret keys in client-side code
- hCaptcha works alongside existing honeypot protection
- Failed hCaptcha attempts are logged for analysis

### Troubleshooting

- Ensure your domain is registered with hCaptcha
- Check that your Site Key matches the configured domain
- Verify the Secret Key is correct and not expired
- Monitor logs for hCaptcha verification failures

## Deployment

MailBear can be deployed using:

1. Docker:
   ```bash
   # Build and run with docker-compose
   docker-compose up -d
   ```

2. Direct deployment:
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Run the application
   python main.py
   ```

## Environment Variables

- `CONFIG_FILE`: Path to configuration file (default: config.yml)
- `PORT`: HTTP port for the server (default: 1234)
- `METRICS_PORT`: HTTP port for metrics server (default: 9090)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `DB_HOST`: Database host
- `DB_PORT`: Database port
- `DB_USER`: Database username
- `DB_PASS`: Database password
- `DB_NAME`: Database name
- `DB_ECHO`: Enable SQL query logging (true/false)
- `DASHBOARD_PASSWORD`: Password for dashboard access
- `JWT_SECRET`: Secret key for JWT tokens
- `SMTP_HOST`: SMTP server host
- `SMTP_PORT`: SMTP server port
- `SMTP_USER`: SMTP username
- `SMTP_PASS`: SMTP password
- `SMTP_FROM`: From email address
- `SMTP_USE_TLS`: Use TLS for SMTP (true/false)
- `SMTP_START_TLS`: Use STARTTLS for SMTP (true/false)
- `SMTP_VERIFY_CERT`: Verify SSL certificate (true/false)
- `HCAPTCHA_ENABLED`: Enable hCaptcha globally (true/false)
- `HCAPTCHA_SITE_KEY`: Global hCaptcha site key
- `HCAPTCHA_SECRET_KEY`: Global hCaptcha secret key
- `HCAPTCHA_TIMEOUT`: hCaptcha API timeout in seconds
- `HCAPTCHA_INVISIBLE`: Enable invisible mode (false for Always Challenge)