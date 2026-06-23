"""
Django base settings for CMS project.
Shared across all environments.
"""

from pathlib import Path
from datetime import timedelta
from decouple import config, Csv

# =============================================================
# PATH CONFIGURATION
# =============================================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# =============================================================
# SECURITY
# =============================================================
SECRET_KEY = config('SECRET_KEY')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# =============================================================
# APPLICATION DEFINITION
# =============================================================
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',
    'corsheaders',
    'drf_spectacular',
]

LOCAL_APPS = [
    'apps.core',
    'apps.accounts',
    'apps.academics',
    'apps.students',
    'apps.faculty',
    'apps.attendance',
    'apps.exams',
    'apps.fees',
    # Add more apps here as you create them, e.g.:
    # 'apps.students',
    # 'apps.faculty',
    # 'apps.attendance',
    # 'apps.exams',
    # 'apps.fees',
    # 'apps.notifications',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# =============================================================
# MIDDLEWARE
# =============================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS — must be before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# =============================================================
# URL CONFIGURATION
# =============================================================
ROOT_URLCONF = 'config.urls'

# =============================================================
# TEMPLATES
# =============================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# =============================================================
# WSGI / ASGI
# =============================================================
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# =============================================================
# DATABASE — PostgreSQL
# =============================================================
'''DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='cms_db'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 5,
        },
    }
}'''

import dj_database_url
from decouple import config

DATABASES = {
    "default": dj_database_url.parse(config("DATABASE_URL"))
}

# =============================================================
# PASSWORD HASHING
# Argon2 first: ~10-20x faster to verify than Django's PBKDF2 default
# while being more resistant to GPU attacks (memory-hard). PBKDF2 stays
# listed so existing hashes still verify; Django transparently re-hashes
# them to Argon2 on each user's next successful login.
# =============================================================
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.ScryptPasswordHasher',
]

# =============================================================
# PASSWORD VALIDATION
# =============================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# =============================================================
# CUSTOM USER MODEL
# =============================================================
AUTH_USER_MODEL = 'accounts.CustomUser'

# =============================================================
# INTERNATIONALIZATION
# =============================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kathmandu'
USE_I18N = True
USE_TZ = True

# =============================================================
# STATIC & MEDIA FILES
# =============================================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# =============================================================
# DEFAULT PRIMARY KEY
# =============================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================
# DJANGO REST FRAMEWORK
# =============================================================
REST_FRAMEWORK = {
    # Authentication
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    # Permissions
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    # Filtering
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    # Pagination
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # Schema
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Rendering
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    # Date/Time
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S%z',
    'DATE_FORMAT': '%Y-%m-%d',
}

# =============================================================
# SIMPLE JWT
# =============================================================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_OBTAIN_SERIALIZER': 'rest_framework_simplejwt.serializers.TokenObtainPairSerializer',
}

# =============================================================
# CORS CONFIGURATION
# =============================================================
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://localhost:3000',
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

# =============================================================
# DRF SPECTACULAR — API Documentation
# =============================================================
SPECTACULAR_SETTINGS = {
    'TITLE': 'College Management System API',
    'DESCRIPTION': 'Production-grade API for managing academic, administrative, examination, attendance, and financial operations.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': r'/api/',
}