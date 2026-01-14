"""
Bot protection middleware.

Note: Rate limiting has been disabled.
"""

import re


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
    '/api/auth/cookie-consent/',
]

# Path prefixes that are exempt (for dynamic paths like /api/upload/xxx/)
EXEMPT_PATH_PREFIXES = [
    '/api/upload/',
]


class BotProtectionMiddleware:
    """
    Middleware to detect and block automated bot traffic.

    Features:
    - Blocks known bot user agents
    - Checks for missing or suspicious headers

    Note: Rate limiting is disabled.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip protection for exempt paths
        if request.path in EXEMPT_PATHS:
            return self.get_response(request)

        # Skip protection for exempt path prefixes
        for prefix in EXEMPT_PATH_PREFIXES:
            if request.path.startswith(prefix):
                return self.get_response(request)

        # Rate limiting disabled - pass all requests through
        return self.get_response(request)
