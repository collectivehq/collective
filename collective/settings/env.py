from __future__ import annotations

from pathlib import Path
from typing import cast

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.FileAwareEnv()
env.read_env(BASE_DIR / ".env")


def env_str(name: str, *, default: str = "") -> str:
    return cast(str, env.str(name, default=default)).strip()


def env_non_empty_str(name: str, *, default: str) -> str:
    return env_str(name, default=default) or default


def env_int(name: str, *, default: int) -> int:
    return cast(int, env.int(name, default=default))


def env_bool(name: str, *, default: bool = False) -> bool:
    return cast(bool, env.bool(name, default=default))


def env_list(name: str, *, default: tuple[str, ...] | list[str] = ()) -> list[str]:
    return [value.strip() for value in env.list(name, default=list(default)) if value.strip()]
