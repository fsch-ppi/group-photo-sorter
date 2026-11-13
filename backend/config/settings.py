"""
Django settings for photo_import_sorter project.
"""

import os
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Security settings
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY',
                       'django-insecure-change-me-in-production')
DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = list(dict.fromkeys(
    [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,kaenguin.de').split(',') if h.strip()]
    + ['localhost', '127.0.0.1', 'kaenguin.de']
))

# Trust X-Forwarded-Host header from Apache/nginx reverse proxy
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Subpath deployment prefix (default: /photosorter)
FORCE_SCRIPT_NAME = os.getenv('FORCE_SCRIPT_NAME', '/photosorter') or None

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'corsheaders',
    'social_django',
    # Local apps
    'apps.core',
    'apps.folders',
    'apps.uploads',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'social_django.middleware.SocialAuthExceptionMiddleware',
    'apps.core.middleware.BotProtectionMiddleware',

]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': Path(os.getenv('SQLITE_DB_PATH', str(BASE_DIR / 'db.sqlite3'))),
        'OPTIONS': {
            'timeout': 30,
            'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;',
        },
    }
}

# Cache configuration (using Redis with connection health checks and retry)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
        'OPTIONS': {
            'socket_connect_timeout': 5,
            'socket_timeout': 5,
            'retry_on_timeout': True,
            'health_check_interval': 30,
        },
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# CORS & Frontend URL settings
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://kaenguin.de/photosorter').rstrip('/')
_parsed_frontend = urlparse(FRONTEND_URL)
_FRONTEND_ORIGIN = (
    f"{_parsed_frontend.scheme}://{_parsed_frontend.netloc}"
    if _parsed_frontend.scheme and _parsed_frontend.netloc
    else 'https://kaenguin.de'
)

CORS_ALLOWED_ORIGINS = list(dict.fromkeys([
    _FRONTEND_ORIGIN,
    'https://kaenguin.de',
    'https://sz-verwaltung.ddns.net:18443',
    'https://sz-verwaltung.ddns.net:8444',
    'http://localhost:5173',
    'http://localhost:18080',
    'http://localhost:18443',
    'https://localhost:18443',
]))
CORS_ALLOW_CREDENTIALS = True

# CSRF settings
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([
    _FRONTEND_ORIGIN,
    'https://kaenguin.de',
    'https://sz-verwaltung.ddns.net:18443',
    'https://sz-verwaltung.ddns.net:8444',
    'http://localhost:5173',
    'http://localhost:18080',
    'http://localhost:18443',
    'https://localhost:18443',
]))
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript to read the cookie
CSRF_COOKIE_SECURE = not DEBUG

# Session settings
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG

# Nextcloud OAuth2 Configuration
NEXTCLOUD_URL = os.getenv('NEXTCLOUD_URL', '').rstrip('/')
SOCIAL_AUTH_NEXTCLOUD_KEY = os.getenv('NEXTCLOUD_CLIENT_ID', '')
SOCIAL_AUTH_NEXTCLOUD_SECRET = os.getenv('NEXTCLOUD_CLIENT_SECRET', '')

# Social Auth settings
AUTHENTICATION_BACKENDS = [
    'apps.core.backends.NextcloudOAuth2',
    'django.contrib.auth.backends.ModelBackend',
]

_SCRIPT_PREFIX = (FORCE_SCRIPT_NAME or '').rstrip('/')
SOCIAL_AUTH_URL_NAMESPACE = 'social'
SOCIAL_AUTH_REQUIRE_POST = False
SOCIAL_AUTH_REDIRECT_IS_HTTPS = not DEBUG
SOCIAL_AUTH_LOGIN_REDIRECT_URL = f'{_SCRIPT_PREFIX}/api/auth/callback/'
SOCIAL_AUTH_LOGIN_ERROR_URL = f'{_SCRIPT_PREFIX}/login/error/'
SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
    'apps.core.pipeline.save_nextcloud_tokens',
)

# Celery Configuration
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 7200,
    'health_check_interval': 30,
    'retry_on_timeout': True,
}
CELERY_REDIS_BACKEND_HEALTH_CHECK_INTERVAL = 30
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Task result persistence for session recovery
CELERY_RESULT_EXPIRES = 7 * 24 * 60 * 60  # 7 days

# Worker prefetch - only grab 1 task at a time for better buffering
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Rate limiting for Nextcloud API (NextcloudClient also handles 429 Retry-After backoff)
CELERY_TASK_ANNOTATIONS = {
    'apps.uploads.tasks.process_uploaded_file': {
        'rate_limit': '60/m',
    },
    'apps.uploads.tasks.flush_image_batch': {
        'rate_limit': '12/m',
    },
}

# Acknowledgment settings - only ack after task completes
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# Priority queues: photos processed before videos
CELERY_TASK_QUEUES = {
    'high': {'exchange': 'high', 'routing_key': 'high'},
    'default': {'exchange': 'default', 'routing_key': 'default'},
    'low': {'exchange': 'low', 'routing_key': 'low'},
}
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_ROUTES = {
    'apps.uploads.tasks.process_image_for_batch': {
        'queue': 'high',  # Image conversion on high priority
    },
    'apps.uploads.tasks.flush_image_batch': {
        'queue': 'default',  # Batch upload on default
    },
}

# Celery Beat schedule for periodic tasks
CELERY_BEAT_SCHEDULE = {
    'cleanup-temp-files': {
        'task': 'apps.uploads.tasks.cleanup_temp_files',
        'schedule': 3600.0,  # Every hour
    },
    'anonymize-old-ip-addresses': {
        'task': 'apps.uploads.tasks.anonymize_old_ip_addresses',
        'schedule': 86400.0,  # Every 24 hours (GDPR compliance)
    },
}

# File upload settings
MAX_UPLOAD_SIZE_MB = int(os.getenv('MAX_UPLOAD_SIZE_MB', '5120'))
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024  # Convert to bytes
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE
TEMP_UPLOAD_DIR = Path(
    os.getenv('TEMP_UPLOAD_DIR', '/tmp/photo_import_uploads'))
# Ensure the temp upload directory exists
TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
TEMP_FILE_MAX_AGE_HOURS = int(os.getenv('TEMP_FILE_MAX_AGE_HOURS', '24'))

# Conversion settings
JPEG_QUALITY = int(os.getenv('JPEG_QUALITY', '90'))
VIDEO_CRF = int(os.getenv('VIDEO_CRF', '23'))

# Supported file formats
SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.heic', '.heif', '.tiff',
                              '.tif', '.cr2', '.nef', '.arw', '.dng', '.raw', '.webp', '.bmp', '.gif'}
SUPPORTED_VIDEO_EXTENSIONS = {'.mov', '.avi', '.mkv',
                              '.mp4', '.m4v', '.wmv', '.flv', '.webm', '.hevc', '.3gp'}

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'social_core': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'social_django': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Security settings for production
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
