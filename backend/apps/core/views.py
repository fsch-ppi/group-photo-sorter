"""
Core API views for authentication.
"""

from django.conf import settings
from django.shortcuts import redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .jwt_auth import generate_session_token, get_token_expiry_info


class AuthStatusView(APIView):
    """Check if user is authenticated. Also ensures CSRF cookie is set."""
    permission_classes = [AllowAny]

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        if request.user.is_authenticated:
            # Generate a fresh JWT session token
            session_token = generate_session_token(request.user)

            return Response({
                'authenticated': True,
                'user': {
                    'id': request.user.id,
                    'username': request.user.username,
                    'email': request.user.email,
                    'first_name': request.user.first_name,
                    'last_name': request.user.last_name,
                },
                'session_token': session_token,
                'session_expires_in_days': 7,
            })
        return Response({'authenticated': False})


@api_view(['GET'])
@permission_classes([AllowAny])
def login_redirect(request):
    """Redirect to Nextcloud OAuth login."""
    return redirect('social:begin', 'nextcloud')


@api_view(['GET'])
@permission_classes([AllowAny])
def auth_callback(request):
    """Handle OAuth callback and redirect to frontend."""
    frontend_url = settings.FRONTEND_URL
    if request.user.is_authenticated:
        return redirect(f'{frontend_url}/dashboard')
    return redirect(f'{frontend_url}/login?error=auth_failed')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Logout user."""
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    return Response({'success': True})


@api_view(['GET'])
@permission_classes([AllowAny])
def nextcloud_config(request):
    """Return Nextcloud URL for frontend configuration."""
    return Response({
        'nextcloud_url': settings.NEXTCLOUD_URL,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def robots_txt(request):
    """Return robots.txt to disallow all crawlers."""
    content = """# Photo Import Sorter - Private Application
# No crawling allowed

User-agent: *
Disallow: /

# Block all known bots explicitly
User-agent: Googlebot
Disallow: /

User-agent: Bingbot
Disallow: /

User-agent: Slurp
Disallow: /

User-agent: DuckDuckBot
Disallow: /

User-agent: Baiduspider
Disallow: /

User-agent: YandexBot
Disallow: /

User-agent: facebookexternalhit
Disallow: /

User-agent: Twitterbot
Disallow: /
"""
    return HttpResponse(content, content_type='text/plain')


@api_view(['GET'])
@permission_classes([AllowAny])
def privacy_policy(request):
    """Return GDPR-compliant privacy policy information."""
    return Response({
        'privacy_policy': {
            'last_updated': '2026-01-14',
            'data_controller': 'Photo Import Sorter Application Owner',
            'cookies': {
                'description': 'We use only essential cookies required for the application to function.',
                'types': [
                    {
                        'name': 'Session Cookie',
                        'purpose': 'Maintains your login session',
                        'duration': '7 days',
                        'essential': True,
                    },
                    {
                        'name': 'CSRF Token',
                        'purpose': 'Protects against cross-site request forgery attacks',
                        'duration': 'Session',
                        'essential': True,
                    },
                    {
                        'name': 'Cookie Consent',
                        'purpose': 'Remembers your cookie preference',
                        'duration': '1 year',
                        'essential': True,
                    },
                ],
            },
            'data_collected': {
                'ip_addresses': {
                    'purpose': 'Upload statistics and security monitoring',
                    'retention': '30 days',
                    'legal_basis': 'Legitimate interest (security)',
                },
                'uploaded_files': {
                    'purpose': 'Photo/video processing and storage in your Nextcloud',
                    'retention': 'Until you delete them from Nextcloud',
                    'legal_basis': 'Contract fulfillment',
                },
            },
            'your_rights': [
                'Right to access your personal data',
                'Right to rectification of inaccurate data',
                'Right to erasure (right to be forgotten)',
                'Right to data portability',
                'Right to object to processing',
            ],
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def set_cookie_consent(request):
    """Record cookie consent preference."""
    consent = request.data.get('consent', 'rejected')

    response = Response({
        'success': True,
        'consent': consent,
    })

    # Set consent cookie for 1 year
    if consent == 'essential':
        response.set_cookie(
            'cookie_consent',
            'essential',
            max_age=365 * 24 * 60 * 60,  # 1 year
            httponly=False,  # Allow JS to read
            samesite='Lax',
            secure=not settings.DEBUG,
        )
    else:
        response.set_cookie(
            'cookie_consent',
            'rejected',
            max_age=365 * 24 * 60 * 60,
            httponly=False,
            samesite='Lax',
            secure=not settings.DEBUG,
        )

    return response
