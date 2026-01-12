"""
Custom authentication classes and middleware.
"""

from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Session authentication that doesn't enforce CSRF.

    Since we're running the frontend and backend on the same origin (via nginx proxy),
    and using SameSite cookies, CSRF protection is less critical. The session cookie
    itself provides authentication.

    For additional security, CORS is configured to only allow the frontend origin.
    """

    def enforce_csrf(self, request):
        """Skip CSRF validation - handled by SameSite cookies and CORS."""
        return None


class DisableCSRFForAPIMiddleware:
    """
    Middleware that disables CSRF checks for API endpoints.

    This is safe because:
    1. API uses SameSite=Lax cookies which prevent cross-site requests
    2. CORS only allows requests from the configured frontend origin
    3. Session authentication still validates the user
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Mark API requests as CSRF exempt
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
        return self.get_response(request)
