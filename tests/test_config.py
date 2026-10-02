"""Tests for endpoint constants and token resolution."""

from __future__ import annotations

import pytest

from fakes import FakeSession
from mineru.agent import AgentClient
from mineru.config import (
    DEFAULT_AGENT_BASE_URL,
    DEFAULT_STANDARD_BASE_URL,
    TOKEN_ENV_VAR,
    get_version,
    resolve_token,
)
from mineru.exceptions import MissingTokenError


def test_explicit_token_beats_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV_VAR, "env-token")
    assert resolve_token("explicit") == "explicit"


def test_token_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV_VAR, "env-token")
    assert resolve_token() == "env-token"
    assert resolve_token(None) == "env-token"


def test_missing_token_raises(no_token: pytest.MonkeyPatch) -> None:
    with pytest.raises(MissingTokenError):
        resolve_token()


def test_agent_client_needs_no_token(no_token: pytest.MonkeyPatch) -> None:
    client = AgentClient(session=FakeSession())
    assert "Authorization" not in client._transport.headers


def test_default_base_urls() -> None:
    assert DEFAULT_STANDARD_BASE_URL == "https://mineru.net/api/v4"
    assert DEFAULT_AGENT_BASE_URL == "https://mineru.net/api/v1/agent"


def test_get_version_returns_a_string() -> None:
    assert isinstance(get_version(), str)
    assert get_version()
