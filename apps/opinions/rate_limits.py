from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest


def _request_actor_key(request: HttpRequest) -> str:
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return f"user:{user.pk}"
    remote_addr = request.META.get("REMOTE_ADDR", "unknown")
    return f"ip:{remote_addr}"


def allow_toggle_request(*, request: HttpRequest, action: str, space_id: str) -> bool:
    max_attempts = int(getattr(settings, "TOGGLE_RATE_LIMIT_MAX_ATTEMPTS", 20))
    window_seconds = int(getattr(settings, "TOGGLE_RATE_LIMIT_WINDOW_SECONDS", 60))
    if max_attempts <= 0 or window_seconds <= 0:
        return True

    cache_key = f"toggle-rate:{action}:{space_id}:{_request_actor_key(request)}"
    if cache.add(cache_key, 1, timeout=window_seconds):
        return True

    try:
        attempts = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=window_seconds)
        return True

    return int(attempts) <= max_attempts
