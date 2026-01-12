"""
Pipeline functions for Social Auth.
"""


def save_nextcloud_tokens(strategy, details, user=None, response=None, *args, **kwargs):
    """
    Save Nextcloud access token to user profile for later API calls.
    """
    if user and response:
        # Store access token in session for API calls
        access_token = response.get('access_token')
        refresh_token = response.get('refresh_token')

        if access_token:
            # Get or create UserProfile
            from apps.core.models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.nextcloud_access_token = access_token
            profile.nextcloud_refresh_token = refresh_token or ''
            profile.save()

    return {}
