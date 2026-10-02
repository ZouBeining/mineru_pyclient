"""Tests for the precise (v4) API client."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import pytest

from fakes import FakeResponse, FakeSession, envelope
from mineru.exceptions import MinerUError, MissingTokenError
from mineru.models import TaskResult, TaskState
from mineru.standard import MinerUClient


def _make_client(responses: list[Any]) -> tuple[MinerUClient, FakeSession]:
    session = FakeSession(responses)
    client = MinerUClient(
        "token-123",
        base_url="https://api.test/api/v4",
        session=session,
    )
    return client, session


def test_client_requires_a_token(no_token: pytest.MonkeyPatch) -> None:
    with pytest.raises(MissingTokenError):
        MinerUClient(session=FakeSession())


def test_client_reads_the_token_from_the_environment(token_env: str) -> None:
    client = MinerUClient(session=FakeSession())
    assert client.token == "env-token"


def test_client_sends_the_bearer_header() -> None:
    client, _ = _make_client([])
    assert client._transport.headers["Authorization"] == "Bearer token-123"
    assert client._transport.headers["Content-Type"] == "application/json"


def test_create_url_task_sends_documented_defaults() -> None:
    client, session = _make_client([FakeResponse(envelope({"task_id": "t-1"}))])
    assert client.create_url_task("https://cdn/doc.pdf") == "t-1"
    call = session.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.test/api/v4/extract/task"
    body = call["json"]
    assert body["url"] == "https://cdn/doc.pdf"
    assert body["model_version"] == "pipeline"
    assert body["language"] == "ch"
    assert body["is_ocr"] is False
    assert body["enable_formula"] is True
    assert body["enable_table"] is True
    assert "data_id" not in body
    assert "extra_formats" not in body
    assert "page_ranges" not in body


def test_create_url_task_overrides_options() -> None:
    client, session = _make_client([FakeResponse(envelope({"task_id": "t-2"}))])
    client.create_url_task(
        "https://cdn/doc.pdf",
        is_ocr=True,
        model_version="vlm",
        page_ranges="2,4-6",
        extra_formats=["docx", "html"],
        data_id="abc",
        cache_tolerance=60,
        no_cache=True,
    )
    body = session.calls[0]["json"]
    assert body["is_ocr"] is True
    assert body["model_version"] == "vlm"
    assert body["page_ranges"] == "2,4-6"
    assert body["extra_formats"] == ["docx", "html"]
    assert body["data_id"] == "abc"
    assert body["cache_tolerance"] == 60
    assert body["no_cache"] is True


def test_create_file_tasks_requests_urls_and_uploads(tmp_path: Path) -> None:
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    first.write_bytes(b"AAA")
    second.write_bytes(b"BB")
    responses = [
        FakeResponse(envelope({"batch_id": "b-1", "file_urls": ["https://up/a", "https://up/b"]})),
        FakeResponse(envelope(None)),
        FakeResponse(envelope(None)),
    ]
    client, session = _make_client(responses)
    assert client.create_file_tasks([first, second], model_version="vlm") == "b-1"

    assert session.calls[0]["url"].endswith("/file-urls/batch")
    assert session.calls[0]["json"]["model_version"] == "vlm"
    assert [entry["name"] for entry in session.calls[0]["json"]["files"]] == [
        "a.pdf",
        "b.pdf",
    ]
    uploads = [call for call in session.calls if call["method"] == "PUT"]
    assert [call["url"] for call in uploads] == ["https://up/a", "https://up/b"]
    assert [call["data"] for call in uploads] == [b"AAA", b"BB"]
    assert all(call["headers"] is None for call in uploads)


def test_create_file_tasks_requires_at_least_one_file() -> None:
    client, _ = _make_client([])
    with pytest.raises(ValueError):
        client.create_file_tasks([])


def test_create_url_tasks_submits_a_batch() -> None:
    client, session = _make_client([FakeResponse(envelope({"batch_id": "b-2"}))])
    assert client.create_url_tasks(["https://a", "https://b"], model_version="vlm") == "b-2"
    assert session.calls[0]["url"].endswith("/extract/task/batch")
    assert [entry["url"] for entry in session.calls[0]["json"]["files"]] == [
        "https://a",
        "https://b",
    ]


def test_get_task_parses_progress() -> None:
    payload = envelope(
        {
            "task_id": "t",
            "state": "running",
            "extract_progress": {
                "extracted_pages": 1,
                "total_pages": 2,
                "start_time": "2025-01-20 11:43:20",
            },
        }
    )
    client, _ = _make_client([FakeResponse(payload)])
    result = client.get_task("t")
    assert result.state is TaskState.RUNNING
    assert result.extract_progress is not None
    assert result.extract_progress.extracted_pages == 1


def test_get_batch_parses_waiting_file_state() -> None:
    payload = envelope(
        {
            "batch_id": "b",
            "extract_result": [{"file_name": "a.pdf", "state": "waiting-file"}],
        }
    )
    client, _ = _make_client([FakeResponse(payload)])
    batch = client.get_batch("b")
    assert batch.files[0].state is TaskState.WAITING_FILE
    assert batch.is_terminal is False


def test_wait_polls_until_done() -> None:
    responses = [
        FakeResponse(envelope({"task_id": "t", "state": "pending"})),
        FakeResponse(envelope({"task_id": "t", "state": "converting"})),
        FakeResponse(
            envelope(
                {
                    "task_id": "t",
                    "state": "done",
                    "full_zip_url": "https://cdn/x.zip",
                }
            )
        ),
    ]
    client, session = _make_client(responses)
    result = client.wait("t", interval=0.0, timeout=100.0)
    assert result.is_done
    assert result.full_zip_url == "https://cdn/x.zip"
    assert len(session.calls) == 3


def test_download_result_extracts_the_archive(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("full.md", "# done")
    client, _ = _make_client([FakeResponse(content=buffer.getvalue())])
    result = TaskResult(task_id="t", state=TaskState.DONE, full_zip_url="https://cdn/x.zip")
    out = client.download_result(result, tmp_path / "out")
    assert (out / "full.md").read_text(encoding="utf-8") == "# done"
    assert not (out / "_result.zip").exists()


def test_download_result_raises_without_an_archive() -> None:
    client, _ = _make_client([])
    with pytest.raises(MinerUError):
        client.download_result(TaskResult(state=TaskState.DONE), "out")
