"""
URL configuration for photo_import_sorter project.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.core.urls')),
    path('api/folders/', include('apps.folders.urls')),
    path('api/upload/', include('apps.uploads.urls')),
    path('social/', include('social_django.urls', namespace='social')),
]
