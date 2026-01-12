"""
Nextcloud OAuth2 Backend for Python Social Auth.
"""

import base64
from social_core.backends.oauth import BaseOAuth2
from django.conf import settings


class NextcloudOAuth2(BaseOAuth2):
    """Nextcloud OAuth2 authentication backend."""

    name = 'nextcloud'

    @property
    def BASE_URL(self):
        return settings.NEXTCLOUD_URL.rstrip('/')

    @property
    def AUTHORIZATION_URL(self):
        return f'{self.BASE_URL}/index.php/apps/oauth2/authorize'

    @property
    def ACCESS_TOKEN_URL(self):
        return f'{self.BASE_URL}/index.php/apps/oauth2/api/v1/token'

    ACCESS_TOKEN_METHOD = 'POST'
    REDIRECT_STATE = False

    def auth_complete_credentials(self):
        """Return credentials for token exchange - empty since we use Basic Auth header."""
        return {}

    def get_key_and_secret(self):
        """Return tuple of client_id and client_secret."""
        return self.setting('KEY'), self.setting('SECRET')

    def request_access_token(self, *args, **kwargs):
        """Override to send client credentials via Basic Auth header (required by Nextcloud)."""
        # Build Basic Auth header
        client_id, client_secret = self.get_key_and_secret()
        credentials = f"{client_id}:{client_secret}"
        basic_auth = base64.b64encode(credentials.encode()).decode()

        # Add Authorization header
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Basic {basic_auth}'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        kwargs['headers'] = headers

        return super().request_access_token(*args, **kwargs)

    def auth_complete_params(self, state=None):
        """Return params for token exchange."""
        return {
            'grant_type': 'authorization_code',
            'code': self.data.get('code', ''),
            'redirect_uri': self.get_redirect_uri(state),
        }

    def get_user_details(self, response):
        """Return user details from Nextcloud account."""
        return {
            'username': response.get('id', response.get('ocs', {}).get('data', {}).get('id', '')),
            'email': response.get('email', response.get('ocs', {}).get('data', {}).get('email', '')),
            'fullname': response.get('displayname', response.get('ocs', {}).get('data', {}).get('displayname', '')),
            'first_name': response.get('displayname', response.get('ocs', {}).get('data', {}).get('displayname', '')).split(' ')[0] if response.get('displayname') else '',
        }

    def user_data(self, access_token, *args, **kwargs):
        """Fetch user data from Nextcloud OCS API."""
        url = f'{self.BASE_URL}/ocs/v2.php/cloud/user'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'OCS-APIRequest': 'true',
            'Accept': 'application/json',
        }
        response = self.request(url, headers=headers)
        try:
            data = response.json()
            return data.get('ocs', {}).get('data', {})
        except (ValueError, KeyError):
            return {}

    def get_user_id(self, details, response):
        """Return the user ID from Nextcloud."""
        return response.get('id', details.get('username', ''))
