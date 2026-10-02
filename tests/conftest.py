"""Shared pytest fixtures for the MinerU test suite."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from fakes import FakeResponse, FakeSession, envelope


@pytest.fixture
def make_envelope() -> Callable[..., dict[str, Any]]:
    """Return the envelope builder used across the tests."""
    return envelope


@pytest.fixture
def no_token(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Ensure no token leaks in from the environment."""
    monkeypatch.delenv("MINERU_TOKEN", raising=False)
    return monkeypatch


@pytest.fixture
def token_env(monkeypatch: pytest.MonkeyPatch) -> str:
    """Provide a token through the environment variable."""
    monkeypatch.setenv("MINERU_TOKEN", "env-token")
    return "env-token"


__all__ = ["FakeResponse", "FakeSession", "envelope"]
