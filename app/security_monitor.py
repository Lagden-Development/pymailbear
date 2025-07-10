"""
Security monitoring and blocking for suspicious activity.
"""

import time
from typing import Dict, Set
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class SecurityMonitor:
    """
    Monitors and blocks suspicious IP addresses based on patterns.
    """
    
    def __init__(self):
        self._failed_attempts: Dict[str, list] = {}  # ip -> [timestamps]
        self._blocked_ips: Dict[str, float] = {}  # ip -> block_until_timestamp
        self._lock = Lock()
        
        # Thresholds
        self.max_failed_attempts = 10  # Max failed attempts in time window
        self.time_window = 300  # 5 minutes in seconds
        self.block_duration = 1800  # 30 minutes in seconds
    
    def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if an IP is currently blocked."""
        if not ip_address:
            return False
            
        with self._lock:
            if ip_address in self._blocked_ips:
                block_until = self._blocked_ips[ip_address]
                if time.time() < block_until:
                    return True
                else:
                    # Block expired, remove it
                    del self._blocked_ips[ip_address]
                    logger.info(f"IP {ip_address} block expired")
            
            return False
    
    def record_failed_attempt(self, ip_address: str, reason: str) -> bool:
        """
        Record a failed attempt. Returns True if IP should be blocked.
        """
        if not ip_address:
            return False
            
        current_time = time.time()
        
        with self._lock:
            # Initialize or get existing attempts
            if ip_address not in self._failed_attempts:
                self._failed_attempts[ip_address] = []
            
            attempts = self._failed_attempts[ip_address]
            
            # Clean up old attempts outside time window
            cutoff_time = current_time - self.time_window
            attempts[:] = [t for t in attempts if t > cutoff_time]
            
            # Add new attempt
            attempts.append(current_time)
            
            # Check if threshold exceeded
            if len(attempts) >= self.max_failed_attempts:
                # Block the IP
                block_until = current_time + self.block_duration
                self._blocked_ips[ip_address] = block_until
                
                logger.warning(
                    f"IP {ip_address} blocked for {self.block_duration/60:.1f} minutes. "
                    f"Reason: {len(attempts)} failed attempts ({reason})"
                )
                
                # Clear attempts after blocking
                del self._failed_attempts[ip_address]
                
                return True
            
            return False
    
    def get_stats(self) -> Dict[str, any]:
        """Get current monitoring statistics."""
        with self._lock:
            current_time = time.time()
            
            # Count active blocks
            active_blocks = sum(1 for block_until in self._blocked_ips.values() 
                              if block_until > current_time)
            
            # Count IPs with recent failed attempts
            suspicious_ips = 0
            for attempts in self._failed_attempts.values():
                cutoff_time = current_time - self.time_window
                recent_attempts = [t for t in attempts if t > cutoff_time]
                if len(recent_attempts) >= 3:  # 3+ attempts is suspicious
                    suspicious_ips += 1
            
            return {
                "active_blocks": active_blocks,
                "suspicious_ips": suspicious_ips,
                "total_tracked_ips": len(self._failed_attempts),
                "blocked_ips": list(self._blocked_ips.keys())
            }
    
    def cleanup(self) -> None:
        """Clean up expired blocks and old attempts."""
        current_time = time.time()
        
        with self._lock:
            # Remove expired blocks
            expired_blocks = [ip for ip, block_until in self._blocked_ips.items() 
                            if block_until <= current_time]
            for ip in expired_blocks:
                del self._blocked_ips[ip]
            
            # Clean up old failed attempts
            cutoff_time = current_time - self.time_window
            for ip in list(self._failed_attempts.keys()):
                attempts = self._failed_attempts[ip]
                attempts[:] = [t for t in attempts if t > cutoff_time]
                if not attempts:
                    del self._failed_attempts[ip]


# Global security monitor instance
security_monitor = SecurityMonitor()