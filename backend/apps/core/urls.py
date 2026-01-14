"""
Core URL configuration.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('status/', views.AuthStatusView.as_view(), name='auth_status'),
    path('login/', views.login_redirect, name='login'),
    path('callback/', views.auth_callback, name='auth_callback'),
    path('logout/', views.logout, name='logout'),
    path('config/', views.nextcloud_config, name='nextcloud_config'),
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('cookie-consent/', views.set_cookie_consent, name='cookie_consent'),
]
