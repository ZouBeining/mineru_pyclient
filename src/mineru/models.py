"""Data models shared by both MinerU APIs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

__all__ = [
    "TaskState",
    "TERMINAL_STATES",
    "ExtractProgress",
    "TaskResult",
    "BatchFileResult",
    "BatchResult",
    "AgentResult",
]


class TaskState(str, Enum):
    """Lifecycle states reported for parsing tasks.

    Not every state applies to every API. Inheriting from :class:`str` keeps
    the values JSON-friendly and comparable with plain strings.
    """

    WAITING_FILE = "waiting-file"
    UPLOADING = "uploading"
    PENDING = "pending"
    RUNNING = "running"
    CONVERTING = "converting"
    DONE = "done"
    FAILED = "failed"

    @classmethod
    def from_raw(cls, value: str | None) -> TaskState:
        """Coerce a raw API value into a state, defaulting to ``pending``."""
        if value is None:
            return cls.PENDING
        try:
            return cls(value)
        except ValueError:
            return cls.PENDING


#: States after which the API will not change the task any further.
TERMINAL_STATES = frozenset({TaskState.DONE, TaskState.FAILED})


@dataclass(frozen=True)
class ExtractProgress:
    """Progress information reported while a task is ``running``."""

    extracted_pages: int | None = None
    total_pages: int | None = None
    start_time: str | None = None

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any] | None) -> ExtractProgress | None:
        if not raw:
            return None
        return cls(
            extracted_pages=raw.get("extracted_pages"),
            total_pages=raw.get("total_pages"),
            start_time=raw.get("start_time"),
        )


@dataclass(frozen=True)
class TaskResult:
    """Result of a single (non-batch) parsing task."""

    task_id: str | None = None
    data_id: str | None = None
    state: TaskState = TaskState.PENDING
    full_zip_url: str | None = None
    err_msg: str | None = None
    extract_progress: ExtractProgress | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_terminal(self) -> bool:
        """Whether the task will not change state any further."""
        return self.state in TERMINAL_STATES

    @property
    def is_done(self) -> bool:
        """Whether the task finished successfully."""
        return self.state is TaskState.DONE

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> TaskResult:
        """Build a result from the ``data`` field of an API response."""
        return cls(
            task_id=raw.get("task_id"),
            data_id=raw.get("data_id"),
            state=TaskState.from_raw(raw.get("state")),
            full_zip_url=raw.get("full_zip_url"),
            err_msg=raw.get("err_msg") or None,
            extract_progress=ExtractProgress.from_raw(raw.get("extract_progress")),
            raw=raw,
        )


@dataclass(frozen=True)
class BatchFileResult(TaskResult):
    """Result of a single file inside a batch."""

    file_name: str | None = None

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> BatchFileResult:
        base = TaskResult.from_raw(raw)
        return cls(
            task_id=base.task_id,
            data_id=base.data_id,
            state=base.state,
            full_zip_url=base.full_zip_url,
            err_msg=base.err_msg,
            extract_progress=base.extract_progress,
            raw=raw,
            file_name=raw.get("file_name"),
        )


@dataclass(frozen=True)
class BatchResult:
    """Result of a batch parsing task."""

    batch_id: str
    files: list[BatchFileResult] = field(default_factory=list)
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_terminal(self) -> bool:
        """Whether every file in the batch reached a terminal state."""
        return bool(self.files) and all(item.is_terminal for item in self.files)

    @property
    def is_done(self) -> bool:
        """Whether every file in the batch finished successfully."""
        return bool(self.files) and all(item.is_done for item in self.files)

    @property
    def failed(self) -> list[BatchFileResult]:
        """The files that reached the ``failed`` state."""
        return [item for item in self.files if item.state is TaskState.FAILED]

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> BatchResult:
        """Build a batch result from the ``data`` field of an API response."""
        items = raw.get("extract_result") or []
        return cls(
            batch_id=raw.get("batch_id", ""),
            files=[BatchFileResult.from_raw(item) for item in items],
            raw=raw,
        )


@dataclass(frozen=True)
class AgentResult:
    """Result of an Agent lightweight parsing task."""

    task_id: str | None = None
    state: TaskState = TaskState.PENDING
    markdown_url: str | None = None
    err_msg: str | None = None
    err_code: int | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_terminal(self) -> bool:
        """Whether the task will not change state any further."""
        return self.state in TERMINAL_STATES

    @property
    def is_done(self) -> bool:
        """Whether the task finished successfully."""
        return self.state is TaskState.DONE

    @classmethod
    def from_raw(cls, raw: Mapping[str, Any]) -> AgentResult:
        """Build a result from the ``data`` field of an API response."""
        return cls(
            task_id=raw.get("task_id"),
            state=TaskState.from_raw(raw.get("state")),
            markdown_url=raw.get("markdown_url"),
            err_msg=raw.get("err_msg") or None,
            err_code=raw.get("err_code"),
            raw=raw,
        )
