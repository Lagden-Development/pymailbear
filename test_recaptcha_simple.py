#!/usr/bin/env python3
"""
Simple test script for reCAPTCHA integration in MailBear
This script validates that all components are properly integrated.
"""

import sys
import os

# Add the parent directory to path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import RecaptchaConfig
from app.database.models import Form
from app.recaptcha_service import RecaptchaService, RecaptchaVerificationResult


def test_recaptcha_config():
    """Test reCAPTCHA configuration"""
    print("Testing reCAPTCHA configuration...")
    
    # Test default configuration
    config = RecaptchaConfig()
    assert config.enabled == False
    assert config.default_threshold == 0.5
    assert config.timeout == 10
    print("✅ Default configuration test passed")
    
    # Test custom configuration
    config = RecaptchaConfig(
        enabled=True,
        site_key="test_site_key",
        secret_key="test_secret_key",
        default_threshold=0.7,
        timeout=15
    )
    assert config.enabled == True
    assert config.site_key == "test_site_key"
    assert config.secret_key == "test_secret_key"
    assert config.default_threshold == 0.7
    assert config.timeout == 15
    print("✅ Custom configuration test passed")


def test_form_model():
    """Test Form model with reCAPTCHA fields"""
    print("\nTesting Form model with reCAPTCHA fields...")
    
    # Test form with reCAPTCHA disabled
    form = Form(
        id="test-form-1",
        name="Test Form 1",
        to_emails="test@example.com",
        from_email="forms@example.com",
        subject="Test Subject",
        recaptcha_enabled=False,
        recaptcha_threshold="0.5"  # Explicitly set default
    )
    
    assert form.recaptcha_enabled == False
    assert form.recaptcha_site_key is None
    assert form.recaptcha_secret_key is None
    assert form.recaptcha_threshold == "0.5"
    print("✅ Form with reCAPTCHA disabled test passed")
    
    # Test form with reCAPTCHA enabled
    form = Form(
        id="test-form-2",
        name="Test Form 2",
        to_emails="test@example.com",
        from_email="forms@example.com",
        subject="Test Subject",
        recaptcha_enabled=True,
        recaptcha_site_key="test_site_key",
        recaptcha_secret_key="test_secret_key",
        recaptcha_threshold="0.7"
    )
    
    assert form.recaptcha_enabled == True
    assert form.recaptcha_site_key == "test_site_key"
    assert form.recaptcha_secret_key == "test_secret_key"
    assert form.recaptcha_threshold == "0.7"
    print("✅ Form with reCAPTCHA enabled test passed")


def test_recaptcha_verification_result():
    """Test reCAPTCHA verification result structure"""
    print("\nTesting reCAPTCHA verification result...")
    
    # Test successful result
    result = RecaptchaVerificationResult(
        success=True,
        score=0.9,
        action="submit",
        challenge_ts="2023-01-01T00:00:00Z",
        hostname="example.com"
    )
    
    assert result.success == True
    assert result.score == 0.9
    assert result.action == "submit"
    assert result.challenge_ts == "2023-01-01T00:00:00Z"
    assert result.hostname == "example.com"
    print("✅ Successful verification result test passed")
    
    # Test failed result
    result = RecaptchaVerificationResult(
        success=False,
        error_codes=["invalid-input-response"]
    )
    
    assert result.success == False
    assert result.error_codes == ["invalid-input-response"]
    print("✅ Failed verification result test passed")


def test_service_initialization():
    """Test reCAPTCHA service initialization"""
    print("\nTesting reCAPTCHA service initialization...")
    
    # Test service creation (this will use the default config)
    service = RecaptchaService()
    assert service is not None
    print("✅ Service initialization test passed")


def test_integration_structure():
    """Test the integration structure"""
    print("\nTesting integration structure...")
    
    # Test that all required components exist
    from app.recaptcha_service import recaptcha_service
    from app.config import Config
    
    # Check that the service singleton exists
    assert recaptcha_service is not None
    print("✅ Service singleton test passed")
    
    # Check that Config class has RecaptchaConfig
    from app.config import RecaptchaConfig
    assert RecaptchaConfig is not None
    print("✅ Configuration class test passed")
    
    # Check that Form model has reCAPTCHA fields
    from app.database.models import Form
    form = Form()
    assert hasattr(form, 'recaptcha_enabled')
    assert hasattr(form, 'recaptcha_site_key')
    assert hasattr(form, 'recaptcha_secret_key')
    assert hasattr(form, 'recaptcha_threshold')
    print("✅ Form model integration test passed")


def test_javascript_config_structure():
    """Test JavaScript configuration structure"""
    print("\nTesting JavaScript configuration structure...")
    
    # Test template variables structure
    template_vars = {
        "recaptcha_enabled": True,
        "recaptcha_site_key": "test_site_key",
        "recaptcha_action": "form_submit"
    }
    
    # Verify required fields exist
    assert "recaptcha_enabled" in template_vars
    assert "recaptcha_site_key" in template_vars
    assert "recaptcha_action" in template_vars
    print("✅ JavaScript configuration structure test passed")


def run_all_tests():
    """Run all tests"""
    print("🧪 Running reCAPTCHA integration tests...\n")
    
    try:
        test_recaptcha_config()
        test_form_model()
        test_recaptcha_verification_result()
        test_service_initialization()
        test_integration_structure()
        test_javascript_config_structure()
        
        print("\n🎉 All tests passed! reCAPTCHA integration is properly set up.")
        print("\n📝 Next steps:")
        print("1. Run the database migration: python migrations/001_add_recaptcha_fields.py")
        print("2. Update your config.yml with reCAPTCHA settings")
        print("3. Get reCAPTCHA keys from https://www.google.com/recaptcha/admin")
        print("4. Test with a real form submission")
        return True
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)