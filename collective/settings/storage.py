from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

_TRUE_VALUES = {"1", "true", "yes", "on"}
_DOCKER_HOST_ALIASES = {"host.docker.internal", "gateway.docker.internal", "docker.for.mac.host.internal"}


@dataclass(frozen=True, slots=True)
class MediaStorageConfig:
    use_object_storage: bool
    media_url: str
    media_root: Path
    default_storage: dict[str, object]
    extra_csp_sources: tuple[str, ...]


def env_bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    value = env.get(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"{name} must be set when object storage is enabled.")
    return value


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ImproperlyConfigured(f"Invalid absolute URL: {url}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _normalise_custom_domain(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    if stripped.startswith(("http://", "https://")):
        return stripped
    return f"https://{stripped}"


def _running_in_container() -> bool:
    return Path("/.dockerenv").exists()


@lru_cache(maxsize=1)
def _docker_host_gateway_host() -> str | None:
    route_path = Path("/proc/net/route")
    if not route_path.exists():
        return None

    for line in route_path.read_text(encoding="utf-8").splitlines()[1:]:
        fields = line.split()
        if len(fields) < 3 or fields[1] != "00000000":
            continue
        gateway_hex = fields[2]
        try:
            return ".".join(str(part) for part in bytes.fromhex(gateway_hex)[::-1])
        except ValueError:
            return None
    return None


def _normalise_endpoint_url(endpoint_url: str) -> str:
    parsed = urlparse(endpoint_url)
    if not _running_in_container() or parsed.hostname not in _DOCKER_HOST_ALIASES:
        return endpoint_url

    gateway_host = _docker_host_gateway_host()
    if not gateway_host:
        return endpoint_url

    netloc = gateway_host
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return parsed._replace(netloc=netloc).geturl()


def _build_object_storage_media_url(
    *,
    endpoint_url: str,
    bucket_name: str,
    location: str,
    custom_domain: str,
    addressing_style: str,
) -> str:
    location_prefix = f"{location.strip('/')}/" if location.strip("/") else ""
    if custom_domain:
        return f"{custom_domain.rstrip('/')}/{location_prefix}"

    endpoint_origin = _origin(endpoint_url)
    parsed = urlparse(endpoint_origin)
    if addressing_style == "virtual":
        return f"{parsed.scheme}://{bucket_name}.{parsed.netloc}/{location_prefix}"
    return f"{endpoint_origin.rstrip('/')}/{bucket_name}/{location_prefix}"


def _storage_custom_domain(*, media_url: str, explicit_custom_domain: str) -> tuple[str, str | None]:
    public_origin = explicit_custom_domain
    parsed_media_url = urlparse(media_url)
    if not public_origin and parsed_media_url.scheme and parsed_media_url.netloc:
        public_origin = _origin(media_url)

    if not public_origin:
        return "", None

    parsed_public_origin = urlparse(public_origin)
    return parsed_public_origin.netloc, f"{parsed_public_origin.scheme}:"


def build_media_storage_config(env: Mapping[str, str], base_dir: Path) -> MediaStorageConfig:
    media_root = base_dir / env.get("MEDIA_ROOT", "media")
    use_object_storage = env_bool(env, "USE_OBJECT_STORAGE", default=False)
    if not use_object_storage:
        media_url = env.get("MEDIA_URL", "media/")
        return MediaStorageConfig(
            use_object_storage=False,
            media_url=media_url,
            media_root=media_root,
            default_storage={"BACKEND": "django.core.files.storage.FileSystemStorage"},
            extra_csp_sources=(),
        )

    endpoint_url = _normalise_endpoint_url(_required(env, "OBJECT_STORAGE_ENDPOINT_URL"))
    bucket_name = _required(env, "OBJECT_STORAGE_BUCKET_NAME")
    access_key = _required(env, "OBJECT_STORAGE_ACCESS_KEY_ID")
    secret_key = _required(env, "OBJECT_STORAGE_SECRET_ACCESS_KEY")
    region_name = env.get("OBJECT_STORAGE_REGION", "garage").strip() or "garage"
    location = env.get("MEDIA_STORAGE_PREFIX", "media").strip("/")
    custom_domain = _normalise_custom_domain(env.get("MEDIA_CUSTOM_DOMAIN", ""))
    addressing_style = env.get("OBJECT_STORAGE_ADDRESSING_STYLE", "path").strip() or "path"
    signature_version = env.get("OBJECT_STORAGE_SIGNATURE_VERSION", "s3v4").strip() or "s3v4"
    media_url = env.get("MEDIA_URL", "").strip() or _build_object_storage_media_url(
        endpoint_url=endpoint_url,
        bucket_name=bucket_name,
        location=location,
        custom_domain=custom_domain,
        addressing_style=addressing_style,
    )
    storage_custom_domain, url_protocol = _storage_custom_domain(
        media_url=media_url,
        explicit_custom_domain=custom_domain,
    )
    storage_options: dict[str, object] = {
        "access_key": access_key,
        "secret_key": secret_key,
        "bucket_name": bucket_name,
        "default_acl": None,
        "endpoint_url": endpoint_url,
        "file_overwrite": False,
        "location": location,
        "querystring_auth": False,
        "region_name": region_name,
        "signature_version": signature_version,
        "addressing_style": addressing_style,
    }
    if storage_custom_domain:
        storage_options["custom_domain"] = storage_custom_domain
    if url_protocol is not None:
        storage_options["url_protocol"] = url_protocol

    extra_sources = tuple(dict.fromkeys([_origin(endpoint_url), _origin(media_url)]))
    return MediaStorageConfig(
        use_object_storage=True,
        media_url=media_url,
        media_root=media_root,
        default_storage={
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": storage_options,
        },
        extra_csp_sources=extra_sources,
    )
