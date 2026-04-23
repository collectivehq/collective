from __future__ import annotations

import importlib
import os
from types import ModuleType

import pytest
from django.core.exceptions import ImproperlyConfigured


def _load_production_settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> ModuleType:
    monkeypatch.setenv("DJANGO_SECRET_KEY", "test-secret")
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "example.com")

    email_env_vars = (
        "EMAIL_HOST",
        "EMAIL_PORT",
        "EMAIL_HOST_USER",
        "EMAIL_HOST_PASSWORD",
        "EMAIL_USE_TLS",
        "EMAIL_USE_SSL",
        "EMAIL_TIMEOUT",
        "DEFAULT_FROM_EMAIL",
        "SERVER_EMAIL",
    )
    for key in email_env_vars:
        monkeypatch.delenv(key, raising=False)

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "collective.settings.test")
    module = importlib.import_module("collective.settings.production")
    return importlib.reload(module)


class TestProductionEmailSettings:
    def test_reads_smtp_settings_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings_module = _load_production_settings(
            monkeypatch,
            EMAIL_HOST="smtp.example.com",
            EMAIL_PORT="587",
            EMAIL_HOST_USER="mailer",
            EMAIL_HOST_PASSWORD="secret",
            EMAIL_USE_TLS="true",
            EMAIL_TIMEOUT="30",
            DEFAULT_FROM_EMAIL="Collective <hello@example.com>",
        )

        assert settings_module.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
        assert settings_module.EMAIL_HOST == "smtp.example.com"
        assert settings_module.EMAIL_PORT == 587
        assert settings_module.EMAIL_HOST_USER == "mailer"
        assert settings_module.EMAIL_HOST_PASSWORD == "secret"
        assert settings_module.EMAIL_USE_TLS is True
        assert settings_module.EMAIL_USE_SSL is False
        assert settings_module.EMAIL_TIMEOUT == 30
        assert settings_module.DEFAULT_FROM_EMAIL == "Collective <hello@example.com>"
        assert settings_module.SERVER_EMAIL == "Collective <hello@example.com>"

    def test_server_email_defaults_to_explicit_value_when_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings_module = _load_production_settings(
            monkeypatch,
            DEFAULT_FROM_EMAIL="Collective <hello@example.com>",
            SERVER_EMAIL="errors@example.com",
        )

        assert settings_module.SERVER_EMAIL == "errors@example.com"

    def test_rejects_tls_and_ssl_being_enabled_together(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with pytest.raises(ImproperlyConfigured, match="cannot both be enabled"):
            _load_production_settings(
                monkeypatch,
                EMAIL_USE_TLS="true",
                EMAIL_USE_SSL="true",
            )
