"""
Folder models for managing photo import folders.
"""

import secrets
import string
from django.db import models
from django.contrib.auth.models import User


def generate_share_token():
    """Generate a cryptographically secure random share token."""
    # 32 characters = ~190 bits of entropy, more than enough to be unguessable
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))


class NamingFormat(models.TextChoices):
    """Available naming formats for uploaded files."""
    DATE_EVENT = 'date_event', 'Date + Event Name (e.g., 2026-01-12_wedding.jpg)'
    EVENT_DATE = 'event_date', 'Event Name + Date (e.g., wedding_2026-01-12.jpg)'
    DATE_ONLY = 'date_only', 'Date Only (e.g., 2026-01-12.jpg)'
    ORIGINAL = 'original', 'Keep Original Name'


class PhotoFolder(models.Model):
    """
    Represents a photo import folder linked to a Nextcloud folder.
    """

    # Owner and basic info
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='photo_folders')
    name = models.CharField(
        max_length=255, help_text='Display name for this folder')
    event_name = models.CharField(
        max_length=100, help_text='Event name used in file naming')

    # Nextcloud folder info
    nextcloud_folder_path = models.CharField(
        max_length=1024, help_text='Path in Nextcloud')
    nextcloud_share_token = models.CharField(
        max_length=255, blank=True, help_text='Nextcloud public share token')

    # Upload configuration
    share_token = models.CharField(
        max_length=32,
        unique=True,
        default=generate_share_token,
        help_text='Secret token for upload access'
    )
    is_active = models.BooleanField(
        default=True, help_text='Whether uploads are enabled')

    # File naming configuration
    naming_format = models.CharField(
        max_length=20,
        choices=NamingFormat.choices,
        default=NamingFormat.DATE_EVENT
    )

    # Conversion settings
    jpeg_quality = models.IntegerField(
        default=90, help_text='JPEG quality (1-100)')

    # README message
    readme_message = models.TextField(
        blank=True,
        default='',
        help_text='Message to include in README.md in the folder'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Photo Folder'
        verbose_name_plural = 'Photo Folders'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.owner.username})"

    def regenerate_share_token(self):
        """Generate a new share token, invalidating the old one."""
        self.share_token = generate_share_token()
        self.save(update_fields=['share_token', 'updated_at'])
        return self.share_token

    @property
    def upload_url(self):
        """Get the upload URL for this folder."""
        from django.conf import settings
        return f"{settings.FRONTEND_URL}/upload/{self.share_token}"

    @property
    def nextcloud_share_url(self):
        """Get the Nextcloud share URL if available."""
        if self.nextcloud_share_token:
            from django.conf import settings
            return f"{settings.NEXTCLOUD_URL}/s/{self.nextcloud_share_token}"
        return None


class UploadStatistics(models.Model):
    """
    Track upload statistics for a folder.
    """

    folder = models.ForeignKey(
        PhotoFolder, on_delete=models.CASCADE, related_name='statistics')
    uploader_ip = models.GenericIPAddressField()
    filename_original = models.CharField(max_length=512)
    filename_converted = models.CharField(max_length=512)
    file_size_original = models.BigIntegerField(
        help_text='Original file size in bytes')
    file_size_converted = models.BigIntegerField(
        help_text='Converted file size in bytes')
    file_type = models.CharField(max_length=20, help_text='image or video')
    conversion_time_seconds = models.FloatField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Upload Statistic'
        verbose_name_plural = 'Upload Statistics'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.filename_original} -> {self.filename_converted}"
