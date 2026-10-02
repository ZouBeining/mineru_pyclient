"""Shared configuration: API endpoints, token resolution and version."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version

from .exceptions import MissingTokenError

__all__ = [
    "DEFAULT_STANDARD_BASE_URL",
    "DEFAULT_AGENT_BASE_URL",
    "TOKEN_ENV_VAR",
    "resolve_token",
    "get_version",
]

#: Root of the 精准解析 (precise) API, which requires a token.
DEFAULT_STANDARD_BASE_URL = "https://mineru.net/api/v4"

#: Root of the Agent 轻量解析 (lightweight) API, which needs no token.
DEFAULT_AGENT_BASE_URL = "https://mineru.net/api/v1/agent"

#: Environment variable consulted when no token is passed explicitly.
TOKEN_ENV_VAR = "MINERU_TOKEN"

_FALLBACK_VERSION = "0.0.0.dev0"


def get_version() -> str:
    """Return the installed package version.

    The version is read from the distribution metadata so that
    ``pyproject.toml`` stays the single source of truth. When the package is
    imported straight from a source checkout it falls back to a placeholder.
    """
    try:
        return version("mineru")
    except PackageNotFoundError:  # pragma: no cover - only when not installed
        return _FALLBACK_VERSION


def resolve_token(token: str | None = None) -> str:
    """Return the API token, preferring an explicit value over the environment.

    Precedence: the ``token`` argument, then ``$MINERU_TOKEN``, then an error.

    Raises:
        MissingTokenError: when no token can be found.
    """
    if token:
        return token
    env_token = os.environ.get(TOKEN_ENV_VAR)
    if env_token:
        return env_token
    raise MissingTokenError(
        f"no API token provided; pass token=... or set ${TOKEN_ENV_VAR}"
    )
