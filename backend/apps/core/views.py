"""
Core API views for authentication.
"""

from django.conf import settings
from django.shortcuts import redirect
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class AuthStatusView(APIView):
    """Check if user is authenticated. Also ensures CSRF cookie is set."""
    permission_classes = [AllowAny]

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        if request.user.is_authenticated:
            return Response({
                'authenticated': True,
                'user': {
                    'id': request.user.id,
                    'username': request.user.username,
                    'email': request.user.email,
                    'first_name': request.user.first_name,
                    'last_name': request.user.last_name,
                }
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
