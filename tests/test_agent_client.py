"""Tests for the Agent lightweight (v1) API client."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fakes import FakeResponse, FakeSession, envelope
from mineru_pyclient.agent import AgentClient
from mineru_pyclient.models import TaskState


def _make_client(responses: list[Any]) -> tuple[AgentClient, FakeSession]:
    session = FakeSession(responses)
    client = AgentClient(base_url="https://api.test/api/v1/agent", session=session)
    return client, session


def test_client_sends_no_authorization_header() -> None:
    client, _ = _make_client([])
    assert "Authorization" not in client._transport.headers
    assert client._transport.headers["Content-Type"] == "application/json"


def test_create_url_task_omits_unset_options() -> None:
    client, session = _make_client([FakeResponse(envelope({"task_id": "t"}))])
    assert client.create_url_task("https://cdn/doc.pdf", language="en") == "t"
    call = session.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.test/api/v1/agent/parse/url"
    assert call["json"] == {"url": "https://cdn/doc.pdf", "language": "en"}


def test_create_file_task_requests_url_then_uploads(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(b"PDF")
    responses = [
        FakeResponse(envelope({"task_id": "t-2", "file_url": "https://up/signed"})),
        FakeResponse(envelope(None)),
    ]
    client, session = _make_client(responses)
    assert client.create_file_task(path, page_range="1-10", is_ocr=True) == "t-2"

    request_body = session.calls[0]["json"]
    assert request_body["file_name"] == "doc.pdf"
    assert request_body["page_range"] == "1-10"
    assert request_body["is_ocr"] is True

    upload = session.calls[1]
    assert upload["method"] == "PUT"
    assert upload["url"] == "https://up/signed"
    assert upload["data"] == b"PDF"
    assert upload["headers"] is None


def test_get_task_reports_failure_details() -> None:
    payload = envelope(
        {"task_id": "t", "state": "failed", "err_code": -30003, "err_msg": "too many pages"}
    )
    client, _ = _make_client([FakeResponse(payload)])
    result = client.get_task("t")
    assert result.state is TaskState.FAILED
    assert result.err_code == -30003
    assert result.err_msg == "too many pages"


def test_parse_url_downloads_markdown(tmp_path: Path) -> None:
    responses = [
        FakeResponse(envelope({"task_id": "t"})),
        FakeResponse(
            envelope({"task_id": "t", "state": "done", "markdown_url": "https://cdn/full.md"})
        ),
        FakeResponse(content=b"# hello"),
    ]
    client, _ = _make_client(responses)
    saved = client.parse_url("https://cdn/example.pdf", tmp_path, interval=0.0, timeout=100.0)
    assert isinstance(saved, Path)
    assert saved.name == "example.md"
    assert saved.read_text(encoding="utf-8") == "# hello"


def test_parse_url_returns_the_result_without_out_dir() -> None:
    responses = [
        FakeResponse(envelope({"task_id": "t"})),
        FakeResponse(
            envelope({"task_id": "t", "state": "done", "markdown_url": "https://cdn/full.md"})
        ),
    ]
    client, _ = _make_client(responses)
    result = client.parse_url("https://cdn/example.pdf", interval=0.0, timeout=100.0)
    assert result.state is TaskState.DONE
    assert result.markdown_url == "https://cdn/full.md"


def test_parse_file_returns_the_result_without_out_dir(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(b"PDF")
    responses = [
        FakeResponse(envelope({"task_id": "t", "file_url": "https://up"})),
        FakeResponse(envelope(None)),
        FakeResponse(
            envelope({"task_id": "t", "state": "done", "markdown_url": "https://cdn/full.md"})
        ),
    ]
    client, _ = _make_client(responses)
    result = client.parse_file(path, interval=0.0, timeout=100.0)
    assert result.state is TaskState.DONE


def test_parse_file_saves_markdown_using_the_file_name(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(b"PDF")
    responses = [
        FakeResponse(envelope({"task_id": "t", "file_url": "https://up"})),
        FakeResponse(envelope(None)),
        FakeResponse(
            envelope({"task_id": "t", "state": "done", "markdown_url": "https://cdn/full.md"})
        ),
        FakeResponse(content=b"# doc"),
    ]
    client, _ = _make_client(responses)
    saved = client.parse_file(path, tmp_path / "out", interval=0.0, timeout=100.0)
    assert saved.name == "doc.md"
    assert saved.read_text(encoding="utf-8") == "# doc"
