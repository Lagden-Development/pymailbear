# MailBear Project Documentation

## Project Overview

MailBear is a form submission to email service that allows websites to easily collect form data and send it via email. It provides:

- Form to email conversion
- Spam protection mechanisms
- Multiple storage backends (file-based or database)
- Multi-step form support
- File upload handling
- Analytics and metrics
- Admin dashboard

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

- `app/config.py`: Handles configuration loading and validation:
  - Defines Pydantic models for configuration validation
  - Loads configuration from YAML files
  - Supports environment variable overrides
  - Provides singleton access to the configuration

## API and Routing

- `app/api.py`: Core FastAPI application with main routes:
  - Defines FastAPI app and middleware (CORS, rate limiting)
  - Handles form submission endpoint (/api/v1/form/{form_id})
  - Renders dashboard pages
  - Serves JavaScript for forms
  - Includes the form controller router
  - Sets up application startup events

- `app/form_controller.py`: Handles form management routes:
  - Form creation, editing, viewing, and deletion
  - Form submission management
  - Multi-step form configuration

## Form Processing

- `app/database_form_handler.py`: Handles all form submissions with database storage:
  - Fetches form configuration from database
  - Validates form origins against allowed domains
  - Checks for honeypot fields to prevent spam
  - Processes file uploads and attachments
  - Sends emails to multiple recipients
  - Stores submissions in the database

- `app/email_sender.py`: Handles sending emails:
  - Configures SMTP connections with various security options
  - Formats HTML emails with form data
  - Handles file attachments
  - Provides error handling for email sending failures

- `app/js_handler.py`: Generates client-side JavaScript:
  - Creates customized form submission scripts
  - Handles caching for performance
  - Combines JS and CSS templates
  - Supports multi-step form configuration

## Storage

- `app/database_storage.py`: Database implementation for all storage operations:
  - Stores submissions in the database
  - Provides filtering and pagination
  - Generates submission statistics
  - Supports advanced querying and analytics

## Database

- `app/database/models.py`: SQLAlchemy ORM models:
  - User: User accounts for administration
  - Form: Form configuration
  - FormDomain: Allowed domains for forms
  - Submission: Form submissions
  - FormTemplate: Reusable form templates
  - APIKey: API authentication
  - FormStep: Multi-step form steps
  - FormStepCondition: Logic for multi-step navigation
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

## Utilities

- `app/utils/minify.py`: Minifies JavaScript and CSS for better performance

## Dependencies and Relationships

1. The FastAPI application in `app/api.py` depends on:
   - Configuration from `app/config.py`
   - Form handler from `app/form_handler.py` or `app/database_form_handler.py`
   - JS handler from `app/js_handler.py`
   - Storage from `app/storage.py` or `app/database_storage.py`

2. Form handlers depend on:
   - Email sender from `app/email_sender.py`
   - Storage implementations
   - Metrics from `app/metrics.py`

3. Database components rely on:
   - Models from `app/database/models.py`
   - Connection setup from `app/database/connection.py`

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

If you're upgrading from a previous version that used file-based storage:

```bash
# Run the database migration to support multiple email recipients
mysql -u username -p database_name < migrate_to_emails.sql
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

## Storage Mode

MailBear operates in **database-only mode** for enhanced functionality:

- All forms are created and managed through the web dashboard
- Supports multiple email recipients per form
- Full multi-step form support
- Advanced analytics and metrics
- Form templates and API key management
- Comprehensive submission tracking

Database configuration is required in config.yml.

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
- `DB_HOST`: Database host
- `DB_PORT`: Database port
- `DB_USER`: Database username
- `DB_PASS`: Database password
- `DB_NAME`: Database name
- `DB_ECHO`: Enable SQL query logging (true/false)
- `JWT_SECRET`: Secret key for JWT tokens