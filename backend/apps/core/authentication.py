"""
Custom authentication classes.
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
