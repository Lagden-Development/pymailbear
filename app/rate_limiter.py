"""
Custom rate limiting service for per-IP rate limiting.
"""

import time
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Thread-safe rate limiter for per-IP rate limiting.
    Uses in-memory storage with automatic cleanup.
    """
    
    def __init__(self):
        self._ip_form_requests: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(deque))  # ip -> form_id -> timestamps
        self._lock = Lock()
    
    def _cleanup_old_requests(self, request_queue: deque, window_seconds: int = 60) -> None:
        """Remove requests older than the time window."""
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        
        while request_queue and request_queue[0] < cutoff_time:
            request_queue.popleft()
    
    def _check_rate_limit(self, request_queue: deque, limit: int, window_seconds: int = 60) -> bool:
        """Check if the request queue is within rate limits."""
        current_time = time.time()
        
        # Clean up old requests
        self._cleanup_old_requests(request_queue, window_seconds)
        
        # Check if we're within limits
        if len(request_queue) >= limit:
            return False
        
        # Add current request
        request_queue.append(current_time)
        return True
    
    def is_allowed(self, form_id: str, ip_address: str, ip_limit: int) -> Tuple[bool, str]:
        """
        Check if a request is allowed based on per-IP rate limits.
        
        Args:
            form_id: The form ID
            ip_address: The client IP address
            ip_limit: Maximum requests per minute per IP for this form
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        with self._lock:
            # Check per-IP rate limit for this form
            ip_form_queue = self._ip_form_requests[ip_address][form_id]
            if not self._check_rate_limit(ip_form_queue, ip_limit):
                logger.warning(f"IP rate limit exceeded for IP {ip_address} on form {form_id}: {len(ip_form_queue)}/{ip_limit}")
                return False, f"IP rate limit exceeded ({ip_limit} requests/minute per IP)"
            
            return True, "OK"
    
    def get_stats(self) -> Dict[str, any]:
        """Get current rate limiter statistics."""
        with self._lock:
            current_time = time.time()
            stats = {
                "total_ips": len(self._ip_form_requests),
                "ip_requests": {}
            }
            
            # Get IP request counts
            for ip, form_queues in self._ip_form_requests.items():
                ip_total = 0
                for form_id, queue in form_queues.items():
                    self._cleanup_old_requests(queue)
                    ip_total += len(queue)
                stats["ip_requests"][ip] = ip_total
            
            return stats
    
    def cleanup(self) -> None:
        """Clean up old requests to prevent memory leaks."""
        with self._lock:
            # Clean up IP requests
            for ip, form_queues in list(self._ip_form_requests.items()):
                for form_id, queue in list(form_queues.items()):
                    self._cleanup_old_requests(queue)
                    if not queue:
                        del form_queues[form_id]
                
                # Remove IP if no forms have requests
                if not form_queues:
                    del self._ip_form_requests[ip]


# Global rate limiter instance
rate_limiter = RateLimiter()