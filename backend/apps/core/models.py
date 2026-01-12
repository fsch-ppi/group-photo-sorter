"""
Core models - User profile for storing Nextcloud tokens.
"""

from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Extended user profile for storing Nextcloud-related data."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile')
    nextcloud_access_token = models.TextField(blank=True, default='')
    nextcloud_refresh_token = models.TextField(blank=True, default='')
    nextcloud_user_id = models.CharField(
        max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"Profile for {self.user.username}"
