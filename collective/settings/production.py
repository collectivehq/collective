from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .env import env, env_bool, env_int, env_list, env_non_empty_str, env_str

DEBUG = False
SECRET_KEY = env.str("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
SITE_NAME = env_non_empty_str("DJANGO_SITE_NAME", default="Collective")
SITE_DOMAIN = env_str("DJANGO_SITE_DOMAIN") or (ALLOWED_HOSTS[0] if ALLOWED_HOSTS else "localhost")
SECURE_SSL_REDIRECT = True
USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", default=True)
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if env_bool(
        "USE_X_FORWARDED_PROTO",
        default=True,
    )
    else None
)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env_str("EMAIL_HOST", default="localhost")
EMAIL_PORT = env_int("EMAIL_PORT", default=25)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=False)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env_non_empty_str("DEFAULT_FROM_EMAIL", default="no-reply@collective.local")
SERVER_EMAIL = env_str("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL) or DEFAULT_FROM_EMAIL

if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured("EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be enabled.")

STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
