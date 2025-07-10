"""
hCaptcha verification service for MailBear
"""

import logging
import httpx
from typing import Optional, Dict, Any
from dataclasses import dataclass

from app.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class HcaptchaVerificationResult:
    """Result of hCaptcha verification"""
    success: bool
    challenge_ts: Optional[str] = None
    hostname: Optional[str] = None
    error_codes: Optional[list] = None
    

class HcaptchaService:
    """Service for verifying hCaptcha tokens with hCaptcha's API"""
    
    def __init__(self):
        self.config = get_config()
        self.hcaptcha_config = self.config.hcaptcha
        
    async def verify_token(
        self, 
        token: str, 
        remote_ip: Optional[str] = None,
        secret_key: Optional[str] = None
    ) -> HcaptchaVerificationResult:
        """
        Verify hCaptcha token with hCaptcha's API
        
        Args:
            token: hCaptcha token from frontend
            remote_ip: IP address of the user (optional)
            secret_key: Override secret key (for per-form keys)
            
        Returns:
            HcaptchaVerificationResult: Verification result
        """
        if not token:
            logger.warning("hCaptcha token is empty")
            return HcaptchaVerificationResult(success=False, error_codes=["missing-input-response"])
        
        # Use provided secret key or fall back to global config
        secret = secret_key or self.hcaptcha_config.secret_key
        if not secret:
            logger.error("No hCaptcha secret key configured")
            return HcaptchaVerificationResult(success=False, error_codes=["missing-input-secret"])
        
        # Prepare request data
        data = {
            "secret": secret,
            "response": token
        }
        
        if remote_ip:
            data["remoteip"] = remote_ip
        
        try:
            # Make request to hCaptcha API
            async with httpx.AsyncClient(timeout=self.hcaptcha_config.timeout) as client:
                response = await client.post(
                    self.hcaptcha_config.api_url,
                    data=data
                )
                response.raise_for_status()
                result = response.json()
                
                logger.debug(f"hCaptcha API response: {result}")
                
                return HcaptchaVerificationResult(
                    success=result.get("success", False),
                    challenge_ts=result.get("challenge_ts"),
                    hostname=result.get("hostname"),
                    error_codes=result.get("error-codes")
                )
                
        except httpx.TimeoutException:
            logger.error("hCaptcha API request timeout")
            return HcaptchaVerificationResult(success=False, error_codes=["timeout-or-duplicate"])
        except httpx.HTTPStatusError as e:
            logger.error(f"hCaptcha API HTTP error: {e}")
            return HcaptchaVerificationResult(success=False, error_codes=["bad-request"])
        except Exception as e:
            logger.error(f"hCaptcha verification error: {e}")
            return HcaptchaVerificationResult(success=False, error_codes=["unknown-error"])
    
    def is_enabled(self) -> bool:
        """Check if hCaptcha is globally enabled"""
        return self.hcaptcha_config.enabled
    
    def get_site_key(self) -> Optional[str]:
        """Get the global hCaptcha site key"""
        return self.hcaptcha_config.site_key
    
    def is_invisible(self) -> bool:
        """Check if hCaptcha is configured for invisible mode"""
        return self.hcaptcha_config.invisible


# Global instance
hcaptcha_service = HcaptchaService()