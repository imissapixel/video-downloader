#!/usr/bin/env python3
"""
Rate Limiting Module for Video Downloader
Provides DoS protection and resource management
"""

import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Thread-safe rate limiter with multiple strategies"""
    
    def __init__(self):
        self.requests = defaultdict(deque)  # IP -> deque of timestamps
        self.downloads = defaultdict(deque)  # IP -> deque of download timestamps
        self.failed_attempts = defaultdict(deque)  # IP -> deque of failed attempts
        self.blocked_ips = {}  # IP -> block_until_timestamp
        self.lock = threading.Lock()
        
        # Rate limiting configuration
        self.limits = {
            # General API requests
            'requests_per_minute': 30,
            'requests_per_hour': 200,
            
            # Download requests (more restrictive)
            'downloads_per_minute': 5,
            'downloads_per_hour': 20,
            'downloads_per_day': 50,
            
            # Failed attempts (security)
            'failed_attempts_per_minute': 10,
            'failed_attempts_per_hour': 30,
            
            # Blocking thresholds
            'block_after_failures': 20,
            'block_duration_minutes': 60,
            
            # Burst protection
            'burst_requests_per_second': 10,
            'burst_window_seconds': 1
        }
    
    def get_client_ip(self):
        """Get client IP address with proxy support"""
        # Check for forwarded headers (common in production)
        forwarded_ips = [
            request.headers.get('X-Forwarded-For'),
            request.headers.get('X-Real-IP'),
            request.headers.get('CF-Connecting-IP'),  # Cloudflare
            request.headers.get('X-Client-IP')
        ]
        
        for ip in forwarded_ips:
            if ip:
                # Take first IP if comma-separated
                return ip.split(',')[0].strip()
        
        return request.remote_addr or 'unknown'
    
    def clean_old_entries(self, ip, entry_type='requests'):
        """Clean old entries from tracking deques"""
        now = time.time()
        entries = getattr(self, entry_type)[ip]
        
        # Remove entries older than 1 hour
        while entries and now - entries[0] > 3600:
            entries.popleft()
    
    def is_ip_blocked(self, ip):
        """Check if IP is currently blocked"""
        if ip in self.blocked_ips:
            if time.time() < self.blocked_ips[ip]:
                return True
            else:
                # Block expired, remove it
                del self.blocked_ips[ip]
        return False
    
    def block_ip(self, ip, duration_minutes=None):
        """Block an IP address for specified duration"""
        if duration_minutes is None:
            duration_minutes = self.limits['block_duration_minutes']
        
        block_until = time.time() + (duration_minutes * 60)
        self.blocked_ips[ip] = block_until
        
        logger.warning(f"Blocked IP {ip} for {duration_minutes} minutes due to rate limiting")
    
    def check_rate_limit(self, ip, limit_type='requests'):
        """Check if IP exceeds rate limits"""
        with self.lock:
            now = time.time()
            
            # Check if IP is blocked
            if self.is_ip_blocked(ip):
                return False, "IP temporarily blocked"
            
            # Clean old entries
            self.clean_old_entries(ip, limit_type)
            
            entries = getattr(self, limit_type)[ip]
            
            # Check different time windows
            if limit_type == 'requests':
                # Burst protection (per second)
                recent_entries = [t for t in entries if now - t < self.limits['burst_window_seconds']]
                if len(recent_entries) >= self.limits['burst_requests_per_second']:
                    return False, "Too many requests per second"
                
                # Per minute limit
                minute_entries = [t for t in entries if now - t < 60]
                if len(minute_entries) >= self.limits['requests_per_minute']:
                    return False, "Too many requests per minute"
                
                # Per hour limit
                hour_entries = [t for t in entries if now - t < 3600]
                if len(hour_entries) >= self.limits['requests_per_hour']:
                    return False, "Too many requests per hour"
            
            elif limit_type == 'downloads':
                # Per minute limit
                minute_entries = [t for t in entries if now - t < 60]
                if len(minute_entries) >= self.limits['downloads_per_minute']:
                    return False, "Too many downloads per minute"
                
                # Per hour limit
                hour_entries = [t for t in entries if now - t < 3600]
                if len(hour_entries) >= self.limits['downloads_per_hour']:
                    return False, "Too many downloads per hour"
                
                # Per day limit
                day_entries = [t for t in entries if now - t < 86400]
                if len(day_entries) >= self.limits['downloads_per_day']:
                    return False, "Too many downloads per day"
            
            elif limit_type == 'failed_attempts':
                # Per minute limit
                minute_entries = [t for t in entries if now - t < 60]
                if len(minute_entries) >= self.limits['failed_attempts_per_minute']:
                    return False, "Too many failed attempts per minute"
                
                # Per hour limit
                hour_entries = [t for t in entries if now - t < 3600]
                if len(hour_entries) >= self.limits['failed_attempts_per_hour']:
                    # Block IP after too many failures
                    self.block_ip(ip)
                    return False, "Too many failed attempts - IP blocked"
            
            return True, "OK"
    
    def record_request(self, ip, request_type='requests'):
        """Record a request for rate limiting"""
        with self.lock:
            now = time.time()
            getattr(self, request_type)[ip].append(now)
            
            # Clean old entries periodically
            if len(getattr(self, request_type)[ip]) % 100 == 0:
                self.clean_old_entries(ip, request_type)
    
    def record_failed_attempt(self, ip, reason=""):
        """Record a failed attempt for security monitoring"""
        self.record_request(ip, 'failed_attempts')
        logger.warning(f"Failed attempt from IP {ip}: {reason}")
    
    def get_rate_limit_status(self, ip):
        """Get current rate limit status for an IP"""
        with self.lock:
            now = time.time()
            
            status = {
                'ip': ip,
                'blocked': self.is_ip_blocked(ip),
                'block_expires': None,
                'requests': {
                    'last_minute': 0,
                    'last_hour': 0,
                    'limit_minute': self.limits['requests_per_minute'],
                    'limit_hour': self.limits['requests_per_hour']
                },
                'downloads': {
                    'last_minute': 0,
                    'last_hour': 0,
                    'last_day': 0,
                    'limit_minute': self.limits['downloads_per_minute'],
                    'limit_hour': self.limits['downloads_per_hour'],
                    'limit_day': self.limits['downloads_per_day']
                },
                'failed_attempts': {
                    'last_minute': 0,
                    'last_hour': 0,
                    'limit_minute': self.limits['failed_attempts_per_minute'],
                    'limit_hour': self.limits['failed_attempts_per_hour']
                }
            }
            
            if ip in self.blocked_ips:
                status['block_expires'] = datetime.fromtimestamp(self.blocked_ips[ip]).isoformat()
            
            # Count recent requests
            for entry_type in ['requests', 'downloads', 'failed_attempts']:
                self.clean_old_entries(ip, entry_type)
                entries = getattr(self, entry_type)[ip]
                
                status[entry_type]['last_minute'] = len([t for t in entries if now - t < 60])
                status[entry_type]['last_hour'] = len([t for t in entries if now - t < 3600])
                
                if entry_type == 'downloads':
                    status[entry_type]['last_day'] = len([t for t in entries if now - t < 86400])
            
            return status

# Global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit(limit_type='requests'):
    """Decorator for rate limiting Flask routes"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ip = rate_limiter.get_client_ip()
            
            # Check rate limit
            allowed, message = rate_limiter.check_rate_limit(ip, limit_type)
            
            if not allowed:
                rate_limiter.record_failed_attempt(ip, f"Rate limit exceeded: {message}")
                
                # Return rate limit error
                response = {
                    'error': 'Rate limit exceeded',
                    'message': message,
                    'retry_after': 60  # seconds
                }
                
                return jsonify(response), 429  # Too Many Requests
            
            # Record the request
            rate_limiter.record_request(ip, limit_type)
            
            # Store IP in Flask g for use in the route
            g.client_ip = ip
            
            try:
                # Execute the original function
                result = f(*args, **kwargs)
                return result
            except Exception as e:
                # Record failed attempt if the function fails
                rate_limiter.record_failed_attempt(ip, f"Function error: {str(e)}")
                raise
        
        return decorated_function
    return decorator

def security_rate_limit(f):
    """Special rate limiter for security-sensitive endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = rate_limiter.get_client_ip()
        
        # More restrictive limits for security endpoints
        allowed, message = rate_limiter.check_rate_limit(ip, 'failed_attempts')
        
        if not allowed:
            response = {
                'error': 'Security rate limit exceeded',
                'message': 'Too many failed attempts. Please try again later.',
                'retry_after': 300  # 5 minutes
            }
            return jsonify(response), 429
        
        g.client_ip = ip
        
        try:
            result = f(*args, **kwargs)
            return result
        except Exception as e:
            rate_limiter.record_failed_attempt(ip, f"Security endpoint error: {str(e)}")
            raise
    
    return decorated_function

class RateLimitConfig:
    """Configuration class for rate limiting"""
    
    @staticmethod
    def update_limits(new_limits):
        """Update rate limiting configuration"""
        rate_limiter.limits.update(new_limits)
        logger.info(f"Updated rate limiting configuration: {new_limits}")
    
    @staticmethod
    def get_limits():
        """Get current rate limiting configuration"""
        return rate_limiter.limits.copy()
    
    @staticmethod
    def reset_ip_limits(ip):
        """Reset rate limits for a specific IP"""
        with rate_limiter.lock:
            if ip in rate_limiter.requests:
                del rate_limiter.requests[ip]
            if ip in rate_limiter.downloads:
                del rate_limiter.downloads[ip]
            if ip in rate_limiter.failed_attempts:
                del rate_limiter.failed_attempts[ip]
            if ip in rate_limiter.blocked_ips:
                del rate_limiter.blocked_ips[ip]
        
        logger.info(f"Reset rate limits for IP: {ip}")
    
    @staticmethod
    def get_blocked_ips():
        """Get list of currently blocked IPs"""
        now = time.time()
        blocked = {}
        
        for ip, block_until in rate_limiter.blocked_ips.items():
            if block_until > now:
                blocked[ip] = {
                    'blocked_until': datetime.fromtimestamp(block_until).isoformat(),
                    'remaining_seconds': int(block_until - now)
                }
        
        return blocked

def cleanup_rate_limiter():
    """Periodic cleanup of old rate limiting data"""
    with rate_limiter.lock:
        now = time.time()
        
        # Clean up old entries
        for ip in list(rate_limiter.requests.keys()):
            rate_limiter.clean_old_entries(ip, 'requests')
            if not rate_limiter.requests[ip]:
                del rate_limiter.requests[ip]
        
        for ip in list(rate_limiter.downloads.keys()):
            rate_limiter.clean_old_entries(ip, 'downloads')
            if not rate_limiter.downloads[ip]:
                del rate_limiter.downloads[ip]
        
        for ip in list(rate_limiter.failed_attempts.keys()):
            rate_limiter.clean_old_entries(ip, 'failed_attempts')
            if not rate_limiter.failed_attempts[ip]:
                del rate_limiter.failed_attempts[ip]
        
        # Clean up expired blocks
        expired_blocks = [ip for ip, block_until in rate_limiter.blocked_ips.items() if block_until <= now]
        for ip in expired_blocks:
            del rate_limiter.blocked_ips[ip]
        
        logger.debug(f"Rate limiter cleanup completed. Cleaned {len(expired_blocks)} expired blocks.")

# Start periodic cleanup thread
def start_cleanup_thread():
    """Start background thread for periodic cleanup"""
    def cleanup_worker():
        while True:
            time.sleep(300)  # Clean up every 5 minutes
            try:
                cleanup_rate_limiter()
            except Exception as e:
                logger.error(f"Error in rate limiter cleanup: {e}")
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    logger.info("Rate limiter cleanup thread started")

# Auto-start cleanup thread when module is imported
start_cleanup_thread()