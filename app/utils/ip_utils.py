"""
Utility functions for handling IP address detection, including Cloudflare support.
"""

from fastapi import Request
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def get_real_ip(request: Request) -> Optional[str]:
    """
    Extract the real client IP address, accounting for Cloudflare and other proxies.
    
    Checks headers in order of priority:
    1. CF-Connecting-IP (Cloudflare)
    2. X-Real-IP 
    3. X-Forwarded-For (first IP)
    4. request.client.host (fallback)
    
    Args:
        request: FastAPI Request object
        
    Returns:
        str: The real client IP address, or None if unable to determine
    """
    
    # Cloudflare's real IP header (highest priority)
    cf_connecting_ip = request.headers.get("CF-Connecting-IP")
    if cf_connecting_ip:
        logger.debug(f"Using Cloudflare CF-Connecting-IP: {cf_connecting_ip}")
        return cf_connecting_ip.strip()
    
    # Standard real IP header (used by some proxies)
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        logger.debug(f"Using X-Real-IP: {x_real_ip}")
        return x_real_ip.strip()
    
    # X-Forwarded-For header (may contain multiple IPs, take the first)
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # Take the first IP in the chain (the original client)
        first_ip = x_forwarded_for.split(",")[0].strip()
        logger.debug(f"Using X-Forwarded-For (first IP): {first_ip}")
        return first_ip
    
    # Fallback to direct connection IP
    direct_ip = request.client.host if request.client else None
    if direct_ip:
        logger.debug(f"Using direct connection IP: {direct_ip}")
        return direct_ip
    
    logger.warning("Unable to determine client IP address")
    return None


def is_cloudflare_request(request: Request) -> bool:
    """
    Check if the request is coming through Cloudflare.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        bool: True if request is from Cloudflare, False otherwise
    """
    
    # Check for Cloudflare-specific headers
    cf_headers = [
        "CF-Connecting-IP",
        "CF-RAY", 
        "CF-Visitor",
        "CF-IPCountry"
    ]
    
    for header in cf_headers:
        if request.headers.get(header):
            return True
    
    return False


def get_client_info(request: Request) -> dict:
    """
    Get comprehensive client information including IP, user agent, and proxy details.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        dict: Client information including IP, user agent, and proxy status
    """
    
    real_ip = get_real_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    is_cf = is_cloudflare_request(request)
    
    # Get all proxy headers for debugging
    proxy_headers = {}
    for header_name in ["CF-Connecting-IP", "X-Real-IP", "X-Forwarded-For", "CF-RAY", "CF-IPCountry"]:
        header_value = request.headers.get(header_name)
        if header_value:
            proxy_headers[header_name] = header_value
    
    return {
        "ip_address": real_ip,
        "user_agent": user_agent,
        "is_cloudflare": is_cf,
        "proxy_headers": proxy_headers,
        "direct_ip": request.client.host if request.client else None
    }