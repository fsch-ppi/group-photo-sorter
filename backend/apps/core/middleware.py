"""
Bot protection and rate limiting middleware.
"""

import re
import hashlib
from django.http import HttpResponseForbidden, JsonResponse
from django.core.cache import cache
from django.conf import settings


# Known bot user agents to block
BOT_USER_AGENTS = [
    r'bot',
    r'crawl',
    r'spider',
    r'scrape',
    r'wget',
    r'curl',
    r'python-requests',
    r'java/',
    r'php/',
    r'ruby/',
    r'perl/',
    r'libwww',
    r'httpclient',
    r'headless',
    r'phantom',
    r'selenium',
]

# Compiled regex for bot detection
BOT_PATTERN = re.compile('|'.join(BOT_USER_AGENTS), re.IGNORECASE)

# Paths that are exempt from bot protection (like robots.txt)
EXEMPT_PATHS = [
    '/robots.txt',
    '/api/auth/config/',
    '/api/auth/privacy/',
]


class BotProtectionMiddleware:
    """
    Middleware to detect and block automated bot traffic.

    Features:
    - Blocks known bot user agents
    - Rate limits by IP address
    - Checks for missing or suspicious headers
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip protection for exempt paths
        if request.path in EXEMPT_PATHS:
            return self.get_response(request)

        # Get client IP
        ip = self._get_client_ip(request)

        # Check if IP is blocked
        if self._is_ip_blocked(ip):
            return JsonResponse(
                {'error': 'Too many requests. Please try again later.'},
                status=429
            )

        # Check for bot user agent (but allow API access without user agent)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if user_agent and BOT_PATTERN.search(user_agent):
            self._increment_suspicious_count(ip)
            return JsonResponse(
                {'error': 'Automated access is not permitted.'},
                status=403
            )

        # Check for honeypot field in POST requests (bot trap)
        if request.method == 'POST':
            # If a hidden honeypot field is filled, it's likely a bot
            honeypot = request.POST.get(
                'website_url_hp', '') or request.POST.get('email_confirm_hp', '')
            if honeypot:
                self._block_ip(ip, duration=3600)  # Block for 1 hour
                return JsonResponse(
                    {'error': 'Request rejected.'},
                    status=403
                )

        return self.get_response(request)

    def _get_client_ip(self, request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')

    def _is_ip_blocked(self, ip):
        """Check if IP is temporarily blocked."""
        cache_key = f'blocked_ip_{hashlib.md5(ip.encode()).hexdigest()}'
        return cache.get(cache_key, False)

    def _block_ip(self, ip, duration=3600):
        """Temporarily block an IP address."""
        cache_key = f'blocked_ip_{hashlib.md5(ip.encode()).hexdigest()}'
        cache.set(cache_key, True, duration)

    def _increment_suspicious_count(self, ip):
        """Track suspicious activity and block if threshold exceeded."""
        cache_key = f'suspicious_count_{hashlib.md5(ip.encode()).hexdigest()}'
        count = cache.get(cache_key, 0) + 1
        cache.set(cache_key, count, 3600)  # Reset after 1 hour

        if count >= 10:  # Block after 10 suspicious requests
            self._block_ip(ip, duration=3600)


class RateLimitMiddleware:
    """
    Simple rate limiting middleware for upload endpoints.
    """

    # Rate limits: (requests, seconds)
    RATE_LIMITS = {
        '/api/upload/': (30, 60),  # 30 uploads per minute
        '/api/auth/login/': (5, 60),  # 5 login attempts per minute
        '/api/folders/': (60, 60),  # 60 API calls per minute
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = self._get_client_ip(request)

        for path_prefix, (max_requests, window) in self.RATE_LIMITS.items():
            if request.path.startswith(path_prefix):
                if not self._check_rate_limit(ip, path_prefix, max_requests, window):
                    return JsonResponse(
                        {'error': f'Rate limit exceeded. Maximum {max_requests} requests per {window} seconds.'},
                        status=429
                    )
                break

        return self.get_response(request)

    def _get_client_ip(self, request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')

    def _check_rate_limit(self, ip, path, max_requests, window):
        """Check if request is within rate limit."""
        cache_key = f'ratelimit_{hashlib.md5((ip + path).encode()).hexdigest()}'

        current = cache.get(cache_key, 0)
        if current >= max_requests:
            return False

        # Increment counter
        if current == 0:
            cache.set(cache_key, 1, window)
        else:
            cache.incr(cache_key)

        return True
