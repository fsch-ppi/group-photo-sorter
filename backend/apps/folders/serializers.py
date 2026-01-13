"""
Serializers for folder models.
"""

from rest_framework import serializers
from .models import PhotoFolder, UploadStatistics, NamingFormat


class PhotoFolderListSerializer(serializers.ModelSerializer):
    """Serializer for listing folders."""

    upload_url = serializers.ReadOnlyField()
    nextcloud_share_url = serializers.ReadOnlyField()
    upload_count = serializers.SerializerMethodField()

    class Meta:
        model = PhotoFolder
        fields = [
            'id', 'name', 'event_name', 'nextcloud_folder_path',
            'is_active', 'naming_format', 'upload_url', 'nextcloud_share_url',
            'upload_count', 'storage_limit_mb', 'created_at', 'updated_at'
        ]

    def get_upload_count(self, obj):
        return obj.statistics.count()


class PhotoFolderDetailSerializer(serializers.ModelSerializer):
    """Serializer for folder details including share token."""

    upload_url = serializers.ReadOnlyField()
    nextcloud_share_url = serializers.ReadOnlyField()

    class Meta:
        model = PhotoFolder
        fields = [
            'id', 'name', 'event_name', 'nextcloud_folder_path',
            'nextcloud_share_token', 'share_token', 'is_active',
            'naming_format', 'jpeg_quality', 'readme_message',
            'storage_limit_mb', 'upload_url', 'nextcloud_share_url',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'share_token', 'created_at', 'updated_at']


class PhotoFolderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating folders."""

    class Meta:
        model = PhotoFolder
        fields = [
            'name', 'event_name', 'nextcloud_folder_path',
            'naming_format', 'jpeg_quality', 'readme_message',
            'storage_limit_mb'
        ]

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class UploadStatisticsSerializer(serializers.ModelSerializer):
    """Serializer for upload statistics."""

    class Meta:
        model = UploadStatistics
        fields = [
            'id', 'uploader_ip', 'filename_original', 'filename_converted',
            'file_size_original', 'file_size_converted', 'file_type',
            'conversion_time_seconds', 'uploaded_at'
        ]


class NamingFormatChoicesSerializer(serializers.Serializer):
    """Serializer for available naming formats."""

    value = serializers.CharField()
    label = serializers.CharField()

    @staticmethod
    def get_choices():
        return [
            {'value': choice[0], 'label': choice[1]}
            for choice in NamingFormat.choices
        ]
