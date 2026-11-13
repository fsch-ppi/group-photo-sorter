"""
URL configuration for uploads app.
"""

from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

urlpatterns = [
    path('<str:share_token>/info/', views.folder_info, name='folder_info'),
    path('<str:share_token>/session/<str:session_id>/', views.session_status, name='session_status'),
    path('<str:share_token>/', csrf_exempt(views.upload_file), name='upload_file'),
    path('task/<str:task_id>/', views.task_status, name='task_status'),
]
