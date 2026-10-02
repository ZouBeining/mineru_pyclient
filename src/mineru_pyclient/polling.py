"""Reusable polling loop shared by both API clients."""

from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

from .exceptions import PollTimeoutError, TaskFailedError

__all__ = ["poll"]

T = TypeVar("T")


def _describe_failure(result: Any) -> tuple[str | None, Any | None]:
    """Extract an error message and code from a task or batch result."""
    message = getattr(result, "err_msg", None)
    code = getattr(result, "err_code", None)
    if message is None:
        # Batch results carry the error messages on their individual files.
        files = getattr(result, "files", None) or []
        parts = [f"{item.file_name}: {item.err_msg}" for item in files if item.err_msg]
        if parts:
            message = "; ".join(parts)
    return message, code


def poll(
    fetch: Callable[[], T],
    *,
    is_terminal: Callable[[T], bool],
    is_done: Callable[[T], bool],
    interval: float = 3.0,
    timeout: float = 600.0,
    backoff: float = 1.0,
    max_interval: float = 30.0,
    on_progress: Callable[[T], None] | None = None,
    task_id: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> T:
    """Call ``fetch`` until it reports a terminal state.

    Args:
        fetch: zero-argument callable returning the latest task result.
        is_terminal: predicate telling whether a result is final.
        is_done: predicate telling whether a terminal result succeeded.
        interval: delay between polls, in seconds.
        timeout: overall budget for the wait, in seconds.
        backoff: multiplier applied to the delay after each poll; ``1.0``
            keeps a constant interval.
        max_interval: upper bound for the back-off delay.
        on_progress: optional callback invoked with every fetched result.
        task_id: task identifier used in raised errors, when known.
        sleep, clock: injectable timing hooks so tests run without waiting.

    Returns:
        The terminal, successful result.

    Raises:
        TaskFailedError: the task reached ``failed``.
        PollTimeoutError: the timeout elapsed before a terminal state.
    """
    start = clock()
    delay = interval
    while True:
        result = fetch()
        if on_progress is not None:
            on_progress(result)
        if is_terminal(result):
            if is_done(result):
                return result
            message, code = _describe_failure(result)
            raise TaskFailedError(
                message=message,
                code=code,
                task_id=task_id or getattr(result, "task_id", None),
            )
        if clock() - start >= timeout:
            raise PollTimeoutError(timeout, task_id=task_id)
        sleep(delay)
        if backoff > 1.0:
            delay = min(delay * backoff, max_interval)
