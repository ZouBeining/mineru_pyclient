"""Tests for the reusable polling loop."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import pytest

from mineru_pyclient.exceptions import PollTimeoutError, TaskFailedError
from mineru_pyclient.models import AgentResult, BatchResult, TaskResult, TaskState
from mineru_pyclient.polling import poll


def _run(
    sequence: Iterable[Any],
    *,
    interval: float = 1.0,
    timeout: float = 100.0,
    sleep: Callable[[float], None] | None = None,
    clock: Callable[[], float] | None = None,
    on_progress: Callable[[Any], None] | None = None,
) -> Any:
    iterator = iter(sequence)
    return poll(
        lambda: next(iterator),
        is_terminal=lambda result: result.is_terminal,
        is_done=lambda result: result.is_done,
        interval=interval,
        timeout=timeout,
        on_progress=on_progress,
        sleep=sleep if sleep is not None else (lambda _seconds: None),
        clock=clock if clock is not None else (lambda: 0.0),
    )


def test_poll_returns_the_first_done_result() -> None:
    sequence = [TaskResult(state=TaskState.RUNNING), TaskResult(state=TaskState.DONE)]
    result = _run(sequence)
    assert result.is_done


def test_poll_accepts_agent_results() -> None:
    sequence = [AgentResult(state=TaskState.PENDING), AgentResult(state=TaskState.DONE)]
    assert _run(sequence).is_done


def test_poll_invokes_the_progress_callback() -> None:
    seen: list[TaskState] = []
    sequence = [
        TaskResult(state=TaskState.PENDING),
        TaskResult(state=TaskState.RUNNING),
        TaskResult(state=TaskState.DONE),
    ]
    _run(sequence, on_progress=lambda result: seen.append(result.state))
    assert seen == [TaskState.PENDING, TaskState.RUNNING, TaskState.DONE]


def test_poll_sleeps_between_attempts() -> None:
    slept: list[float] = []
    sequence = [TaskResult(state=TaskState.RUNNING), TaskResult(state=TaskState.DONE)]
    _run(sequence, interval=2.5, sleep=slept.append)
    assert slept == [2.5]


def test_poll_raises_on_failure() -> None:
    sequence = [TaskResult(state=TaskState.FAILED, err_msg="broken input")]
    with pytest.raises(TaskFailedError) as excinfo:
        _run(sequence)
    assert "broken input" in str(excinfo.value)


def test_poll_reports_batch_failures() -> None:
    batch = BatchResult.from_raw(
        {
            "batch_id": "b",
            "extract_result": [{"file_name": "a.pdf", "state": "failed", "err_msg": "boom"}],
        }
    )
    with pytest.raises(TaskFailedError) as excinfo:
        _run([batch])
    assert "a.pdf: boom" in str(excinfo.value)


def test_poll_times_out() -> None:
    now = [0.0]

    def clock() -> float:
        return now[0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    sequence = [TaskResult(state=TaskState.RUNNING) for _ in range(10)]
    with pytest.raises(PollTimeoutError) as excinfo:
        _run(sequence, interval=1.0, timeout=2.0, clock=clock, sleep=sleep)
    assert excinfo.value.timeout == 2.0
