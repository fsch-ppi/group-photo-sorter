from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'nextcloud_user_id', 'created_at', 'updated_at')
    search_fields = ('user__username', 'nextcloud_user_id')
    readonly_fields = ('created_at', 'updated_at')
