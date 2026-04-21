"""
Django settings for collective project.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-in-production",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.postgres",
    # Third-party
    "allauth",
    "allauth.account",
    "treebeard",
    "tinymce",
    # Local apps
    "apps.users",
    "apps.spaces",
    "apps.nodes",
    "apps.opinions",
    "apps.subscriptions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
]

ROOT_URLCONF = "collective.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csp",
            ],
        },
    },
]

WSGI_APPLICATION = "collective.wsgi.application"

# Database

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "collective"),
        "USER": os.environ.get("POSTGRES_USER", "collective"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "collective"),
        "HOST": os.environ.get("POSTGRES_HOST", "172.21.0.3"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# Auth

AUTH_USER_MODEL = "users.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1

ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_CHANGE_EMAIL = True
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Cache

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# TinyMCE configuration

TINYMCE_DEFAULT_CONFIG = {
    "height": 300,
    "menubar": False,
    "plugins": "autolink lists link image code codesample table",
    "toolbar": (
        "bold italic underline strikethrough | bullist numlist"
        " | blockquote codesample code | link image table | removeformat"
    ),
    "content_css": "default",
    "branding": False,
    "promotion": False,
    "license_key": "gpl",
}

# Security — Django 6 CSP

from django.utils.csp import CSP  # noqa: E402

SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [
        CSP.SELF,
        CSP.NONCE,
        CSP.UNSAFE_EVAL,
        "https://cdn.tailwindcss.com",
        "https://unpkg.com",
        "https://cdn.jsdelivr.net",
        "https://cdn.tiny.cloud",
        "blob:",
    ],
    "style-src": [
        CSP.SELF,
        CSP.UNSAFE_INLINE,
        "https://cdn.jsdelivr.net",
        "https://unpkg.com",
        "https://cdn.tiny.cloud",
    ],
    "img-src": [CSP.SELF, "data:", "blob:"],
    "font-src": [CSP.SELF, "https://cdn.tiny.cloud"],
    "connect-src": [CSP.SELF],
}

URLIZE_ASSUME_HTTPS = True
