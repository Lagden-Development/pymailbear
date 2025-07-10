# reCAPTCHA Setup Guide for MailBear

This guide walks you through setting up Google reCAPTCHA v3 integration in MailBear to prevent spam and bot submissions.

## Prerequisites

- MailBear database mode enabled
- Google account for reCAPTCHA admin access
- Domain where MailBear will be deployed

## Step-by-Step Setup

### 1. Get reCAPTCHA Keys

1. Visit [Google reCAPTCHA Admin Console](https://www.google.com/recaptcha/admin)
2. Click "Create" to add a new site
3. Fill in the form:
   - **Label**: Choose a descriptive name (e.g., "MailBear - Production")
   - **reCAPTCHA type**: Select "reCAPTCHA v3"
   - **Domains**: Add your domain(s) where MailBear will be accessed
     - For local development: `localhost`
     - For production: `yourdomain.com`
   - **Owners**: Add additional Google accounts if needed
4. Accept the Terms of Service
5. Click "Submit"
6. Copy your **Site Key** and **Secret Key**

### 2. Database Migration

Run the migration to add reCAPTCHA fields to your database:

```bash
# Option 1: Using Python script
python migrations/001_add_recaptcha_fields.py

# Option 2: Using SQL directly
mysql -u username -p database_name < migrations/001_add_recaptcha_fields.sql
```

### 3. Configuration

Choose one of the following configuration methods:

#### Option A: Configuration File (config.yml)

Add the reCAPTCHA section to your `config.yml`:

```yaml
recaptcha:
  enabled: true
  site_key: "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"  # Replace with your site key
  secret_key: "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"  # Replace with your secret key
  default_threshold: 0.5
  timeout: 10
```

#### Option B: Environment Variables

Set the following environment variables:

```bash
export RECAPTCHA_ENABLED=true
export RECAPTCHA_SITE_KEY="your_site_key_here"
export RECAPTCHA_SECRET_KEY="your_secret_key_here"
export RECAPTCHA_DEFAULT_THRESHOLD=0.5
export RECAPTCHA_TIMEOUT=10
```

### 4. Restart MailBear

After updating the configuration, restart the MailBear application:

```bash
# If running directly
python main.py

# If using Docker
docker-compose restart
```

### 5. Configure Forms

#### Global Configuration
If you configured reCAPTCHA globally, it will be available for all forms but disabled by default.

#### Per-Form Configuration
1. Access the MailBear dashboard at `http://localhost:1234/forms`
2. Create a new form or edit an existing one
3. In the form editor, find the "reCAPTCHA Protection" section
4. Check the "Enable reCAPTCHA Protection" checkbox
5. (Optional) Enter form-specific Site Key and Secret Key if different from global config
6. Set the threshold (recommended: 0.5)
7. Save the form

## Configuration Options

### Threshold Settings

The threshold determines how strict the reCAPTCHA verification is:

- **0.0**: Accept all traffic (including bots)
- **0.1-0.3**: Very permissive (may allow some sophisticated bots)
- **0.4-0.6**: Balanced (recommended for most use cases)
- **0.7-0.9**: Strict (may block some legitimate users)
- **1.0**: Very strict (may block many legitimate users)

### Recommended Thresholds by Use Case

- **Contact forms**: 0.5
- **Newsletter signup**: 0.3
- **Account registration**: 0.7
- **Payment forms**: 0.8
- **Admin forms**: 0.9

## Testing the Integration

### 1. Basic Functionality Test

1. Create a test form with reCAPTCHA enabled
2. Embed the form on a webpage
3. Submit the form normally
4. Check the logs for reCAPTCHA verification messages

### 2. Threshold Testing

1. Set a very high threshold (0.9) temporarily
2. Submit the form multiple times rapidly
3. Some submissions should be blocked
4. Reset to your desired threshold

### 3. Error Handling Test

1. Temporarily use an invalid secret key
2. Submit the form
3. Verify error handling works correctly
4. Restore the correct secret key

## Troubleshooting

### Common Issues

#### 1. "reCAPTCHA verification failed" Error

**Possible causes:**
- Invalid Site Key or Secret Key
- Domain not registered with reCAPTCHA
- Network connectivity issues
- API timeout

**Solutions:**
- Verify your keys in the Google reCAPTCHA console
- Check that your domain is listed in the reCAPTCHA site configuration
- Test with localhost for development
- Increase the timeout value

#### 2. Forms Not Loading reCAPTCHA

**Possible causes:**
- JavaScript errors on the page
- Content Security Policy blocking reCAPTCHA
- Network issues loading Google's scripts

**Solutions:**
- Check browser console for JavaScript errors
- Update CSP headers to allow reCAPTCHA domains
- Test on different networks/devices

#### 3. High False Positive Rate

**Possible causes:**
- Threshold set too high
- Legitimate users being blocked

**Solutions:**
- Lower the threshold gradually
- Monitor form submission patterns
- Consider different thresholds for different forms

#### 4. Bots Still Getting Through

**Possible causes:**
- Threshold set too low
- Advanced bots bypassing reCAPTCHA

**Solutions:**
- Increase the threshold
- Enable honeypot protection as well
- Monitor submission patterns for suspicious activity

### Debug Mode

To enable debug logging for reCAPTCHA:

1. Set `debug: true` in your config.yml
2. Restart MailBear
3. Check logs for detailed reCAPTCHA verification information

### Log Analysis

Look for these log entries:

```
INFO: reCAPTCHA verification successful for form abc123 (score: 0.9)
WARNING: reCAPTCHA verification failed for form abc123: [error details]
ERROR: No reCAPTCHA secret key configured for form abc123
```

## Security Best Practices

1. **Keep Secret Keys Private**: Never commit secret keys to version control
2. **Use Environment Variables**: Store sensitive configuration in environment variables
3. **Rotate Keys Regularly**: Consider rotating reCAPTCHA keys periodically
4. **Monitor Logs**: Regularly check logs for suspicious activity
5. **Combine with Honeypot**: Use reCAPTCHA alongside honeypot protection for better coverage
6. **Test Regularly**: Periodically test your reCAPTCHA integration

## Advanced Configuration

### Custom Error Messages

You can customize error messages in the JavaScript template by modifying the form handler.

### Multiple Site Keys

For multi-tenant applications, you can configure different reCAPTCHA keys per form:

1. Leave global configuration empty or disabled
2. Configure each form individually with its own keys
3. Use different thresholds based on form sensitivity

### Analytics Integration

Monitor reCAPTCHA effectiveness:

1. Track submission success rates
2. Monitor score distributions
3. Adjust thresholds based on data

## Support

For issues specific to reCAPTCHA integration:

1. Check the troubleshooting section above
2. Review MailBear logs for error messages
3. Verify your reCAPTCHA configuration in Google's console
4. Test with the provided test script: `python test_recaptcha_simple.py`

For Google reCAPTCHA issues:
- [reCAPTCHA Developer Guide](https://developers.google.com/recaptcha)
- [reCAPTCHA FAQ](https://developers.google.com/recaptcha/docs/faq)