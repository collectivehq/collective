from __future__ import annotations

import os

from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

from .env import BASE_DIR, env_bool, env_int, env_non_empty_str, env_str
from .storage import build_media_storage_config

MEDIA_STORAGE = build_media_storage_config(os.environ, BASE_DIR)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.postgres",
    "storages",
    "allauth",
    "allauth.account",
    "treebeard",
    "tinymce",
    # Local apps ordered by dependency direction.
    "apps.core",
    "apps.users",
    "apps.pages",
    "apps.spaces",
    "apps.invitations",
    "apps.discussions",
    "apps.posts",
    "apps.opinions",
    "apps.reactions",
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
                "apps.subscriptions.context_processors.notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "collective.wsgi.application"
ASGI_APPLICATION = "collective.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("POSTGRES_DB", default="collective"),
        "USER": env_str("POSTGRES_USER", default="collective"),
        "PASSWORD": env_str("POSTGRES_PASSWORD", default="collective"),
        "HOST": env_str("POSTGRES_HOST", default="172.21.0.3"),
        "PORT": env_str("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": env_int("DJANGO_CONN_MAX_AGE", default=60),
    }
}

AUTH_USER_MODEL = "users.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1
SITE_NAME = env_non_empty_str("DJANGO_SITE_NAME", default="Collective")
SITE_DOMAIN = env_non_empty_str("DJANGO_SITE_DOMAIN", default="localhost")

ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_EMAIL_VERIFICATION = env_str("ACCOUNT_EMAIL_VERIFICATION", default="optional").lower()
if ACCOUNT_EMAIL_VERIFICATION not in {"mandatory", "optional", "none"}:
    raise ImproperlyConfigured("ACCOUNT_EMAIL_VERIFICATION must be one of: mandatory, optional, none.")
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = env_bool("ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED", default=False)
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS = env_int(
    "ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS",
    default=3,
)
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT = env_int("ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT", default=900)
ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_CHANGE = env_bool(
    "ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_CHANGE",
    default=ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED,
)
ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND = env_bool(
    "ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND",
    default=ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED,
)
if ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED and ACCOUNT_EMAIL_VERIFICATION != "mandatory":
    raise ImproperlyConfigured(
        "ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED requires ACCOUNT_EMAIL_VERIFICATION=mandatory."
    )
if ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS <= 0:
    raise ImproperlyConfigured("ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS must be greater than 0.")
if ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT <= 0:
    raise ImproperlyConfigured("ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT must be greater than 0.")
ACCOUNT_CHANGE_EMAIL = True
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

USE_OBJECT_STORAGE = MEDIA_STORAGE.use_object_storage
MEDIA_URL = MEDIA_STORAGE.media_url
MEDIA_ROOT = MEDIA_STORAGE.media_root
STORAGES = {
    "default": MEDIA_STORAGE.default_storage,
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

TOGGLE_RATE_LIMIT_MAX_ATTEMPTS = 20
TOGGLE_RATE_LIMIT_WINDOW_SECONDS = 60
INVITE_DEFAULT_EXPIRY_DAYS = env_int("INVITE_DEFAULT_EXPIRY_DAYS", default=7)

if INVITE_DEFAULT_EXPIRY_DAYS <= 0:
    raise ImproperlyConfigured("INVITE_DEFAULT_EXPIRY_DAYS must be greater than 0.")

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
    "img-src": [CSP.SELF, "data:", "blob:", *MEDIA_STORAGE.extra_csp_sources],
    "font-src": [CSP.SELF, "https://cdn.tiny.cloud", "https://cdn.jsdelivr.net"],
    "connect-src": [CSP.SELF, *MEDIA_STORAGE.extra_csp_sources],
    "object-src": ["'none'"],
    "base-uri": [CSP.SELF],
}

URLIZE_ASSUME_HTTPS = True

_LOG_LEVEL = env_str("DJANGO_LOG_LEVEL", default="INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": _LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": _LOG_LEVEL,
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": _LOG_LEVEL,
            "propagate": False,
        },
    },
}
