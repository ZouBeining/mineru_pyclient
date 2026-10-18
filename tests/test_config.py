"""Tests for endpoint constants and token resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from fakes import FakeSession
from mineru_pyclient.agent import AgentClient
from mineru_pyclient.config import (
    DEFAULT_AGENT_BASE_URL,
    DEFAULT_STANDARD_BASE_URL,
    TOKEN_ENV_VAR,
    get_version,
    resolve_token,
)
from mineru_pyclient.exceptions import MissingTokenError


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


def _write_env(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_token_read_from_dotenv_file(tmp_path: Path, no_token: pytest.MonkeyPatch) -> None:
    env_file = _write_env(tmp_path / ".env", "MINERU_TOKEN=file-token\n")
    assert resolve_token(env_file=env_file) == "file-token"


def test_dotenv_quotes_and_comments_are_handled(tmp_path: Path, no_token: pytest.MonkeyPatch) -> None:
    env_file = _write_env(
        tmp_path / ".env",
        "# a comment\n\nMINERU_TOKEN=\"quoted token\"\n",
    )
    assert resolve_token(env_file=env_file) == "quoted token"


def test_environment_beats_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_token: pytest.MonkeyPatch,
) -> None:
    env_file = _write_env(tmp_path / ".env", "MINERU_TOKEN=file-token\n")
    monkeypatch.setenv(TOKEN_ENV_VAR, "env-token")
    assert resolve_token(env_file=env_file) == "env-token"


def test_explicit_token_beats_dotenv(tmp_path: Path, no_token: pytest.MonkeyPatch) -> None:
    env_file = _write_env(tmp_path / ".env", "MINERU_TOKEN=file-token\n")
    assert resolve_token("explicit", env_file=env_file) == "explicit"


def test_dotenv_is_discovered_from_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    _write_env(tmp_path / ".env", "MINERU_TOKEN=discovered\n")
    monkeypatch.chdir(tmp_path)
    assert resolve_token() == "discovered"


def test_dotenv_without_the_key_raises(tmp_path: Path, no_token: pytest.MonkeyPatch) -> None:
    env_file = _write_env(tmp_path / ".env", "OTHER=1\n")
    with pytest.raises(MissingTokenError):
        resolve_token(env_file=env_file)


def test_missing_token_error_mentions_dotenv(no_token: pytest.MonkeyPatch) -> None:
    with pytest.raises(MissingTokenError) as excinfo:
        resolve_token()
    assert ".env" in str(excinfo.value)
