from django.contrib import admin
from .models import PhotoFolder, UploadStatistics


@admin.register(PhotoFolder)
class PhotoFolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'event_name', 'is_active', 'created_at')
    list_filter = ('is_active', 'naming_format', 'created_at')
    search_fields = ('name', 'event_name', 'owner__username')
    readonly_fields = ('share_token', 'created_at', 'updated_at')


@admin.register(UploadStatistics)
class UploadStatisticsAdmin(admin.ModelAdmin):
    list_display = ('filename_original', 'folder',
                    'uploader_ip', 'file_type', 'uploaded_at')
    list_filter = ('file_type', 'uploaded_at', 'folder')
    search_fields = ('filename_original', 'filename_converted', 'uploader_ip')
    readonly_fields = ('uploaded_at',)
