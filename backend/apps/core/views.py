"""
Core API views for authentication.
"""

from django.conf import settings
from django.shortcuts import redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
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
    """Redirect directly to Nextcloud OAuth authorize URL."""
    from social_django.views import auth as social_auth_begin
    return social_auth_begin(request._request, 'nextcloud')


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
    """Return GDPR-compliant privacy policy as HTML page."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Privacy Policy - Photo Import Sorter</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem 1rem;
            background: #f9fafb;
        }
        h1 { color: #1f2937; margin-bottom: 0.5rem; }
        h2 { color: #374151; margin: 2rem 0 1rem; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }
        h3 { color: #4b5563; margin: 1.5rem 0 0.75rem; }
        p { margin-bottom: 1rem; }
        ul, ol { margin: 1rem 0 1rem 1.5rem; }
        li { margin-bottom: 0.5rem; }
        .last-updated { color: #6b7280; font-size: 0.9rem; margin-bottom: 2rem; }
        .highlight { background: #fef3c7; padding: 1rem; border-radius: 8px; margin: 1rem 0; }
        table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
        th, td { border: 1px solid #e5e7eb; padding: 0.75rem; text-align: left; }
        th { background: #f3f4f6; }
        .badge { 
            display: inline-block; 
            padding: 0.25rem 0.5rem; 
            border-radius: 4px; 
            font-size: 0.8rem; 
            font-weight: 500;
        }
        .essential { background: #d1fae5; color: #065f46; }
        footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 0.9rem; }
        a { color: #2563eb; }
    </style>
</head>
<body>
    <h1>🔒 Privacy Policy</h1>
    <p class="last-updated">Last updated: January 14, 2026</p>

    <div class="highlight">
        <strong>Summary:</strong> We only collect what's necessary to provide the service. 
        Your photos are stored in YOUR Nextcloud. IP addresses are automatically deleted after 30 days. 
        We use no tracking or advertising.
    </div>

    <h2>1. Data Controller</h2>
    <p>
        This application ("Photo Import Sorter") is operated by the application owner/administrator.
        For questions about this privacy policy or your data, please contact your system administrator.
    </p>

    <h2>2. What Data We Collect</h2>
    
    <h3>2.1 Uploaded Files</h3>
    <p>
        When you upload photos or videos through this application, they are:
    </p>
    <ul>
        <li>Temporarily stored on our server during processing (conversion to JPEG/MP4)</li>
        <li>Transferred to the folder owner's Nextcloud account</li>
        <li>Deleted from our server immediately after successful transfer</li>
    </ul>
    <p>
        <strong>Legal basis:</strong> Contract fulfillment (providing the upload service)<br>
        <strong>Retention:</strong> Temporary files are deleted within 24 hours maximum
    </p>

    <h3>2.2 IP Addresses</h3>
    <p>
        We collect your IP address when you upload files for:
    </p>
    <ul>
        <li>Security monitoring and abuse prevention</li>
        <li>Upload statistics for folder owners</li>
    </ul>
    <p>
        <strong>Legal basis:</strong> Legitimate interest (security)<br>
        <strong>Retention:</strong> <span class="badge essential">Automatically anonymized after 30 days</span>
    </p>

    <h3>2.3 Account Information</h3>
    <p>
        If you log in via Nextcloud OAuth, we receive:
    </p>
    <ul>
        <li>Your Nextcloud username and email</li>
        <li>An access token to manage files in your Nextcloud</li>
    </ul>
    <p>
        <strong>Legal basis:</strong> Contract fulfillment<br>
        <strong>Retention:</strong> Until you delete your account or revoke access
    </p>

    <h2>3. Cookies We Use</h2>
    <p>We use <strong>only essential cookies</strong> required for the application to function. No tracking or advertising cookies.</p>
    
    <table>
        <thead>
            <tr>
                <th>Cookie</th>
                <th>Purpose</th>
                <th>Duration</th>
                <th>Type</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>sessionid</td>
                <td>Maintains your login session</td>
                <td>7 days</td>
                <td><span class="badge essential">Essential</span></td>
            </tr>
            <tr>
                <td>csrftoken</td>
                <td>Protects against cross-site request forgery attacks</td>
                <td>Session</td>
                <td><span class="badge essential">Essential</span></td>
            </tr>
            <tr>
                <td>cookie_consent</td>
                <td>Remembers your cookie preference</td>
                <td>1 year</td>
                <td><span class="badge essential">Essential</span></td>
            </tr>
            <tr>
                <td>photo_upload_session_*</td>
                <td>Tracks your upload progress (allows resuming)</td>
                <td>7 days</td>
                <td><span class="badge essential">Essential</span></td>
            </tr>
        </tbody>
    </table>

    <h2>4. Data Sharing</h2>
    <p>
        <strong>We do not share your data with third parties.</strong>
    </p>
    <ul>
        <li>Uploaded files go directly to the folder owner's Nextcloud</li>
        <li>No analytics services (Google Analytics, etc.)</li>
        <li>No advertising networks</li>
        <li>No social media tracking</li>
    </ul>

    <h2>5. Data Security</h2>
    <p>We protect your data through:</p>
    <ul>
        <li>HTTPS encryption for all data in transit</li>
        <li>Secure session tokens (JWT with cryptographic signing)</li>
        <li>Rate limiting to prevent abuse</li>
        <li>Automatic cleanup of temporary files</li>
        <li>Bot protection and IP blocking for suspicious activity</li>
    </ul>

    <h2>6. Your Rights (GDPR)</h2>
    <p>Under the General Data Protection Regulation, you have the right to:</p>
    <ul>
        <li><strong>Access</strong> – Request a copy of your personal data</li>
        <li><strong>Rectification</strong> – Correct inaccurate personal data</li>
        <li><strong>Erasure</strong> – Request deletion of your personal data ("right to be forgotten")</li>
        <li><strong>Restriction</strong> – Request limited processing of your data</li>
        <li><strong>Portability</strong> – Receive your data in a machine-readable format</li>
        <li><strong>Object</strong> – Object to processing based on legitimate interests</li>
        <li><strong>Withdraw consent</strong> – Withdraw consent at any time (for consent-based processing)</li>
    </ul>
    <p>To exercise these rights, contact your system administrator.</p>

    <h2>7. Data Retention Summary</h2>
    <table>
        <thead>
            <tr>
                <th>Data Type</th>
                <th>Retention Period</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Temporary upload files</td>
                <td>Deleted immediately after processing (max 24 hours)</td>
            </tr>
            <tr>
                <td>IP addresses in statistics</td>
                <td>Anonymized after 30 days</td>
            </tr>
            <tr>
                <td>Upload statistics (anonymized)</td>
                <td>Indefinite (no personal data)</td>
            </tr>
            <tr>
                <td>Account data</td>
                <td>Until account deletion</td>
            </tr>
            <tr>
                <td>Photos in Nextcloud</td>
                <td>Controlled by folder owner</td>
            </tr>
        </tbody>
    </table>

    <h2>8. Changes to This Policy</h2>
    <p>
        We may update this privacy policy from time to time. The "Last updated" date at the top 
        indicates when the policy was last revised. Continued use of the service after changes 
        constitutes acceptance of the updated policy.
    </p>

    <h2>9. Contact</h2>
    <p>
        For privacy-related inquiries, please contact your system administrator who operates 
        this Photo Import Sorter instance.
    </p>

    <footer>
        <p>Photo Import Sorter – Privacy-focused photo sharing</p>
        <p><a href="/">← Back to application</a></p>
    </footer>
</body>
</html>"""
    return HttpResponse(html_content, content_type='text/html')


@csrf_exempt
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
