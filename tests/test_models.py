"""Tests for the shared data models."""

from __future__ import annotations

import pytest

from mineru_pyclient.models import (
    AgentResult,
    BatchResult,
    ExtractProgress,
    TaskResult,
    TaskState,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("done", TaskState.DONE),
        ("failed", TaskState.FAILED),
        ("running", TaskState.RUNNING),
        ("converting", TaskState.CONVERTING),
        ("waiting-file", TaskState.WAITING_FILE),
        ("uploading", TaskState.UPLOADING),
        ("pending", TaskState.PENDING),
        ("mystery", TaskState.PENDING),
        (None, TaskState.PENDING),
    ],
)
def test_task_state_from_raw(raw: str | None, expected: TaskState) -> None:
    assert TaskState.from_raw(raw) is expected


@pytest.mark.parametrize(
    ("state", "terminal", "done"),
    [
        (TaskState.DONE, True, True),
        (TaskState.FAILED, True, False),
        (TaskState.PENDING, False, False),
        (TaskState.RUNNING, False, False),
        (TaskState.CONVERTING, False, False),
        (TaskState.WAITING_FILE, False, False),
        (TaskState.UPLOADING, False, False),
    ],
)
def test_task_result_state_flags(state: TaskState, terminal: bool, done: bool) -> None:
    result = TaskResult(state=state)
    assert result.is_terminal is terminal
    assert result.is_done is done


def test_task_result_from_raw_parses_every_field() -> None:
    raw = {
        "task_id": "t1",
        "data_id": "d1",
        "state": "done",
        "full_zip_url": "https://cdn/x.zip",
        "err_msg": "",
        "extract_progress": {
            "extracted_pages": 2,
            "total_pages": 3,
            "start_time": "2025-01-20 11:43:20",
        },
    }
    result = TaskResult.from_raw(raw)
    assert result.task_id == "t1"
    assert result.data_id == "d1"
    assert result.state is TaskState.DONE
    assert result.full_zip_url == "https://cdn/x.zip"
    assert result.err_msg is None  # an empty message is normalised to None
    assert result.extract_progress == ExtractProgress(2, 3, "2025-01-20 11:43:20")
    assert result.raw is raw


def test_task_result_tolerates_missing_fields() -> None:
    result = TaskResult.from_raw({})
    assert result.task_id is None
    assert result.state is TaskState.PENDING
    assert result.extract_progress is None


def test_batch_result_tracks_each_file() -> None:
    batch = BatchResult.from_raw(
        {
            "batch_id": "b1",
            "extract_result": [
                {"file_name": "a.pdf", "state": "done", "full_zip_url": "https://cdn/a.zip"},
                {"file_name": "b.pdf", "state": "running"},
            ],
        }
    )
    assert batch.batch_id == "b1"
    assert [item.file_name for item in batch.files] == ["a.pdf", "b.pdf"]
    assert batch.is_terminal is False
    assert batch.is_done is False


def test_batch_result_is_done_when_all_files_done() -> None:
    batch = BatchResult.from_raw(
        {
            "batch_id": "b1",
            "extract_result": [
                {"file_name": "a.pdf", "state": "done"},
                {"file_name": "b.pdf", "state": "done"},
            ],
        }
    )
    assert batch.is_terminal is True
    assert batch.is_done is True


def test_batch_result_collects_failures() -> None:
    batch = BatchResult.from_raw(
        {
            "batch_id": "b1",
            "extract_result": [
                {"file_name": "a.pdf", "state": "done"},
                {"file_name": "b.pdf", "state": "failed", "err_msg": "boom"},
            ],
        }
    )
    assert batch.is_terminal is True
    assert batch.is_done is False
    assert [item.file_name for item in batch.failed] == ["b.pdf"]


def test_empty_batch_is_not_terminal() -> None:
    assert BatchResult.from_raw({"batch_id": "b"}).is_terminal is False


def test_agent_result_from_raw() -> None:
    result = AgentResult.from_raw(
        {"task_id": "t", "state": "failed", "err_code": -30003, "err_msg": "too many pages"}
    )
    assert result.task_id == "t"
    assert result.state is TaskState.FAILED
    assert result.err_code == -30003
    assert result.err_msg == "too many pages"
    assert result.is_terminal is True
    assert result.is_done is False
