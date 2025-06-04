# MailBear Python

A simple, self-hosted forms backend built with Python and FastAPI. MailBear accepts form submissions via HTTP POST requests and forwards them as emails to configured recipients.

## Features

- **Simple Forms Backend**: Easy integration with any HTML form
- **Multiple Forms**: Configure multiple forms with different settings
- **Email Delivery**: Send form submissions via email
- **Email Encryption**: Support for TLS, STARTTLS, and custom SSL contexts
- **Domain Validation**: Control which domains can submit forms
- **Rate Limiting**: Prevent abuse of your forms
- **Metrics**: Prometheus metrics for monitoring
- **Dashboard**: Web interface to view form submissions

## Quick Start

### Using Docker

1. Clone this repository
2. Copy `config_sample.yml` to `config.yml` and configure your settings
3. Run with Docker Compose:

```bash
docker-compose up -d
```

### Manual Setup

1. Clone this repository
2. Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Copy `config_sample.yml` to `config.yml` and configure your settings
4. Run the application:

```bash
python main.py
```

## Configuration

Create a `config.yml` file based on the provided `config_sample.yml`:

```yaml
# Server settings
port: 1234
metrics_port: 9090
rate_limit: 5  # requests per minute

# SMTP Configuration
smtp:
  host: smtp.example.com
  port: 587
  username: your_username
  password: your_password
  from_email: forms@example.com
  # Email encryption options
  use_tls: null  # Set to true for SSL/TLS or null to auto-detect based on port
  start_tls: null  # Set to true for STARTTLS or null to auto-detect based on port
  verify_cert: true  # Set to false to disable SSL certificate verification (not recommended)
  ssl_context: null  # Advanced SSL context settings
  timeout: 60  # Connection timeout in seconds

# Forms Configuration
forms:
  - id: contact
    name: Contact Form
    allowed_domains:
      - example.com
      - localhost
    to_email: contact@example.com
    subject: New Contact Form Submission
```

## Form Integration

To integrate a form with MailBear, use the form ID in the action URL:

```html
<form action="http://your-mailbear-server:1234/api/v1/form/contact" method="POST">
  <input type="text" name="name" placeholder="Name" required>
  <input type="email" name="email" placeholder="Email" required>
  <textarea name="message" placeholder="Message" required></textarea>
  <button type="submit">Send</button>
</form>
```

## Dashboard

Access the dashboard at the root URL:

```
http://your-mailbear-server:1234/
```

## Email Encryption Options

MailBear supports various email encryption options:

- **Auto-detection**: By default, MailBear will automatically detect the encryption method based on the port:
  - Port 465: Uses SSL/TLS (implicit TLS)
  - Port 587: Uses STARTTLS (explicit TLS)

- **Manual configuration**: You can override the auto-detection by setting these options in the config.yml:
  - `use_tls`: Set to `true` to use implicit SSL/TLS, or `null` for auto-detection
  - `start_tls`: Set to `true` to use STARTTLS, or `null` for auto-detection
  - `verify_cert`: Set to `false` to disable SSL certificate verification (not recommended)
  - `ssl_context`: Advanced SSL context settings
  - `timeout`: Connection timeout in seconds

Example for Gmail with explicit settings:
```yaml
smtp:
  host: smtp.gmail.com
  port: 587
  username: your_email@gmail.com
  password: your_app_password
  from_email: your_email@gmail.com
  start_tls: true
  use_tls: false
  verify_cert: true
  timeout: 30
```

## Metrics

Prometheus metrics are available at:

```
http://your-mailbear-server:9090/
```

## License

MIT