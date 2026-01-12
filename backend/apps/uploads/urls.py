"""
URL configuration for uploads app.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('<str:share_token>/info/', views.folder_info, name='folder_info'),
    path('<str:share_token>/', views.upload_file, name='upload_file'),
    path('task/<str:task_id>/', views.task_status, name='task_status'),
]
