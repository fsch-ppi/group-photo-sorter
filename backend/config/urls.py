"""
URL configuration for photo_import_sorter project.
"""

from django.contrib import admin
from django.urls import path, include
from apps.core.views import robots_txt

urlpatterns = [
    path('robots.txt', robots_txt, name='robots_txt'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.core.urls')),
    path('api/folders/', include('apps.folders.urls')),
    path('api/upload/', include('apps.uploads.urls')),
    # Also support /api/v1/ prefix for backwards compatibility
    path('api/v1/auth/', include('apps.core.urls')),
    path('api/v1/folders/', include('apps.folders.urls')),
    path('api/v1/upload/', include('apps.uploads.urls')),
    path('social/', include('social_django.urls', namespace='social')),
]
