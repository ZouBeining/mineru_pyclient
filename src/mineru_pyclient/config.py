"""Shared configuration: API endpoints, token resolution and version.

The standard API token is looked up in this order: an explicit argument, the
``MINERU_TOKEN`` environment variable, and finally a ``.env`` file.
"""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from dotenv import dotenv_values, find_dotenv

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

#: Environment variable, and key inside ``.env``, holding the token.
TOKEN_ENV_VAR = "MINERU_TOKEN"

_FALLBACK_VERSION = "0.0.0.dev0"


def get_version() -> str:
    """Return the installed package version.

    The version is read from the distribution metadata so that
    ``pyproject.toml`` stays the single source of truth. When the package is
    imported straight from a source checkout it falls back to a placeholder.
    """
    try:
        return version("mineru_pyclient")
    except PackageNotFoundError:  # pragma: no cover - only when not installed
        return _FALLBACK_VERSION


def _find_env_file() -> str:
    """Return the path of the nearest ``.env`` file, or ``""`` when there is none.

    The search starts in the current working directory and walks up towards the
    filesystem root, so ``mineru`` also works from a subdirectory of the
    project.
    """
    return find_dotenv(usecwd=True)


def _read_env_token(env_file: str | Path | None = None) -> str | None:
    """Return the token stored in a ``.env`` file, if any."""
    path = env_file if env_file is not None else _find_env_file()
    if not path:
        return None
    return dotenv_values(path).get(TOKEN_ENV_VAR) or None


def resolve_token(
    token: str | None = None,
    *,
    env_file: str | Path | None = None,
) -> str:
    """Return the API token for the standard API.

    Precedence:

    1. the ``token`` argument,
    2. the ``MINERU_TOKEN`` environment variable,
    3. ``MINERU_TOKEN`` in a ``.env`` file,
    4. otherwise an error is raised.

    Args:
        token: an explicit token, which always wins.
        env_file: path of the ``.env`` file to read. When omitted the nearest
            ``.env`` is discovered from the current working directory upwards.

    Raises:
        MissingTokenError: when no token can be found.
    """
    if token:
        return token
    env_token = os.environ.get(TOKEN_ENV_VAR)
    if env_token:
        return env_token
    file_token = _read_env_token(env_file)
    if file_token:
        return file_token
    raise MissingTokenError(
        f"no API token provided; pass token=..., set ${TOKEN_ENV_VAR}, "
        f"or add {TOKEN_ENV_VAR} to .env"
    )
