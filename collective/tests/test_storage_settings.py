from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from collective.settings import storage as storage_settings
from collective.settings.storage import build_media_storage_config
from django.core.exceptions import ImproperlyConfigured


class TestBuildMediaStorageConfig:
    def test_defaults_to_local_filesystem_storage(self) -> None:
        config = build_media_storage_config({}, Path("/tmp/collective"))

        assert config.use_object_storage is False
        assert config.media_url == "media/"
        assert config.media_root == Path("/tmp/collective/media")
        assert config.default_storage == {"BACKEND": "django.core.files.storage.FileSystemStorage"}
        assert config.extra_csp_sources == ()

    def test_builds_s3_storage_for_garage(self) -> None:
        config = build_media_storage_config(
            {
                "USE_OBJECT_STORAGE": "true",
                "OBJECT_STORAGE_ENDPOINT_URL": "https://garage.example.com",
                "OBJECT_STORAGE_BUCKET_NAME": "collective-media",
                "OBJECT_STORAGE_ACCESS_KEY_ID": "key",
                "OBJECT_STORAGE_SECRET_ACCESS_KEY": "secret",
                "OBJECT_STORAGE_REGION": "garage",
                "OBJECT_STORAGE_ADDRESSING_STYLE": "path",
                "MEDIA_STORAGE_PREFIX": "media",
            },
            Path("/tmp/collective"),
        )

        assert config.use_object_storage is True
        assert config.media_url == "https://garage.example.com/collective-media/media/"
        assert config.default_storage["BACKEND"] == "storages.backends.s3.S3Storage"
        options = cast(dict[str, object], config.default_storage["OPTIONS"])
        assert options == {
            "access_key": "key",
            "secret_key": "secret",
            "bucket_name": "collective-media",
            "custom_domain": "garage.example.com",
            "default_acl": None,
            "endpoint_url": "https://garage.example.com",
            "file_overwrite": False,
            "location": "media",
            "querystring_auth": False,
            "region_name": "garage",
            "signature_version": "s3v4",
            "addressing_style": "path",
            "url_protocol": "https:",
        }
        assert config.extra_csp_sources == ("https://garage.example.com",)

    def test_requires_s3_credentials_when_enabled(self) -> None:
        with pytest.raises(ImproperlyConfigured):
            build_media_storage_config(
                {
                    "USE_OBJECT_STORAGE": "true",
                    "OBJECT_STORAGE_ENDPOINT_URL": "https://garage.example.com",
                    "OBJECT_STORAGE_BUCKET_NAME": "collective-media",
                },
                Path("/tmp/collective"),
            )

    def test_rewrites_docker_host_alias_to_gateway_inside_container(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(storage_settings, "_running_in_container", lambda: True)
        monkeypatch.setattr(storage_settings, "_docker_host_gateway_host", lambda: "172.21.0.1")

        config = build_media_storage_config(
            {
                "USE_OBJECT_STORAGE": "true",
                "OBJECT_STORAGE_ENDPOINT_URL": "http://host.docker.internal:3900",
                "MEDIA_URL": "http://localhost:3900/collective-media/media/",
                "OBJECT_STORAGE_BUCKET_NAME": "collective-media",
                "OBJECT_STORAGE_ACCESS_KEY_ID": "key",
                "OBJECT_STORAGE_SECRET_ACCESS_KEY": "secret",
                "OBJECT_STORAGE_REGION": "garage",
                "OBJECT_STORAGE_ADDRESSING_STYLE": "path",
                "MEDIA_STORAGE_PREFIX": "media",
            },
            Path("/tmp/collective"),
        )

        options = cast(dict[str, object], config.default_storage["OPTIONS"])
        assert options["endpoint_url"] == "http://172.21.0.1:3900"
        assert options["custom_domain"] == "localhost:3900"
        assert options["url_protocol"] == "http:"
        assert config.media_url == "http://localhost:3900/collective-media/media/"
        assert config.extra_csp_sources == ("http://172.21.0.1:3900", "http://localhost:3900")
