from __future__ import annotations

import importlib
import os
from types import ModuleType

import pytest
from django.core.exceptions import ImproperlyConfigured


def _load_production_settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> ModuleType:
    managed_env_vars = (
        "DJANGO_ALLOWED_HOSTS",
        "EMAIL_HOST",
        "EMAIL_PORT",
        "EMAIL_HOST_USER",
        "EMAIL_HOST_PASSWORD",
        "EMAIL_USE_TLS",
        "EMAIL_USE_SSL",
        "EMAIL_TIMEOUT",
        "DEFAULT_FROM_EMAIL",
        "SERVER_EMAIL",
        "ACCOUNT_EMAIL_VERIFICATION",
        "ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED",
        "ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS",
        "ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT",
        "ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_CHANGE",
        "ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND",
        "DJANGO_SITE_NAME",
        "DJANGO_SITE_DOMAIN",
        "USE_X_FORWARDED_HOST",
        "USE_X_FORWARDED_PROTO",
    )
    for key in managed_env_vars:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("DJANGO_SECRET_KEY", "test-secret")
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "example.com")
    monkeypatch.setenv("ACCOUNT_EMAIL_VERIFICATION", "optional")
    monkeypatch.setenv("ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED", "false")
    monkeypatch.setenv("ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT", "900")
    monkeypatch.setenv("DJANGO_SITE_NAME", "Collective")
    monkeypatch.setenv("DJANGO_SITE_DOMAIN", "")

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "collective.settings.test")
    base_module = importlib.import_module("collective.settings.base")
    importlib.reload(base_module)
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

    def test_uses_first_allowed_host_as_default_site_domain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings_module = _load_production_settings(
            monkeypatch,
            DJANGO_ALLOWED_HOSTS="collective.example.com,www.collective.example.com",
        )

        assert settings_module.SITE_NAME == "Collective"
        assert settings_module.SITE_DOMAIN == "collective.example.com"

    def test_reads_explicit_site_metadata_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings_module = _load_production_settings(
            monkeypatch,
            DJANGO_SITE_NAME="Collective Platform",
            DJANGO_SITE_DOMAIN="collective.edfab.org",
        )

        assert settings_module.SITE_NAME == "Collective Platform"
        assert settings_module.SITE_DOMAIN == "collective.edfab.org"

    def test_reads_email_verification_mode_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings_module = _load_production_settings(
            monkeypatch,
            ACCOUNT_EMAIL_VERIFICATION="mandatory",
        )

        assert settings_module.ACCOUNT_EMAIL_VERIFICATION == "mandatory"

    def test_rejects_invalid_email_verification_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with pytest.raises(ImproperlyConfigured, match="ACCOUNT_EMAIL_VERIFICATION must be one of"):
            _load_production_settings(
                monkeypatch,
                ACCOUNT_EMAIL_VERIFICATION="sometimes",
            )

    def test_reads_email_verification_by_code_settings_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings_module = _load_production_settings(
            monkeypatch,
            ACCOUNT_EMAIL_VERIFICATION="mandatory",
            ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED="true",
            ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS="5",
            ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT="600",
        )

        assert settings_module.ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED is True
        assert settings_module.ACCOUNT_EMAIL_VERIFICATION_BY_CODE_MAX_ATTEMPTS == 5
        assert settings_module.ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT == 600
        assert settings_module.ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_CHANGE is True
        assert settings_module.ACCOUNT_EMAIL_VERIFICATION_SUPPORTS_RESEND is True

    def test_rejects_code_verification_without_mandatory_email_verification(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(
            ImproperlyConfigured,
            match="ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED requires ACCOUNT_EMAIL_VERIFICATION=mandatory",
        ):
            _load_production_settings(
                monkeypatch,
                ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED="true",
            )


class TestProductionProxySettings:
    def test_trusts_forwarded_proto_and_host_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings_module = _load_production_settings(monkeypatch)

        assert settings_module.USE_X_FORWARDED_HOST is True
        assert settings_module.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")

    def test_can_disable_forwarded_proto_trust(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings_module = _load_production_settings(
            monkeypatch,
            USE_X_FORWARDED_PROTO="false",
            USE_X_FORWARDED_HOST="false",
        )

        assert settings_module.USE_X_FORWARDED_HOST is False
        assert settings_module.SECURE_PROXY_SSL_HEADER is None
