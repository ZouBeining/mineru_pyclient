"""Exceptions raised by the MinerU client library.

Both MinerU APIs answer with a JSON envelope of the shape::

    {"code": 0, "msg": "ok", "trace_id": "...", "data": {...}}

A non-zero ``code`` signals a failure. :func:`raise_for_code` maps the codes
documented by MinerU onto a small hierarchy of exceptions so callers can react
to specific failures instead of inspecting raw codes.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "MinerUError",
    "MinerUAPIError",
    "AuthenticationError",
    "TokenExpiredError",
    "MissingTokenError",
    "InvalidParamsError",
    "FileTypeError",
    "FileTooLargeError",
    "PageLimitError",
    "UploadError",
    "QueueFullError",
    "TaskNotFoundError",
    "TaskPermissionError",
    "QuotaExceededError",
    "ServerError",
    "TaskFailedError",
    "PollTimeoutError",
    "raise_for_code",
]


class MinerUError(Exception):
    """Base class for every error raised by this library."""


class MinerUAPIError(MinerUError):
    """The API returned a non-zero ``code``.

    Attributes:
        code: the error code reported by the API, either an ``int`` or a
            string such as ``"A0202"``.
        message: the human readable ``msg`` field.
        trace_id: the request ``trace_id``, useful when contacting support.
    """

    def __init__(
        self,
        code: Any,
        message: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.code = code
        self.message = message or ""
        self.trace_id = trace_id
        detail = f"[{code}] {self.message}".rstrip()
        if trace_id:
            detail = f"{detail} (trace_id={trace_id})"
        super().__init__(detail)


class AuthenticationError(MinerUAPIError):
    """The token is missing, malformed or rejected (code ``A0202``)."""


class TokenExpiredError(AuthenticationError):
    """The token has expired (code ``A0211``)."""


class MissingTokenError(MinerUError):
    """No token was supplied for an API that requires one."""


class InvalidParamsError(MinerUAPIError):
    """The request parameters were rejected (``-500``, ``-10002``, ``-30004``)."""


class FileTypeError(MinerUAPIError):
    """The file type is unsupported (``-60002``, ``-30002``)."""


class FileTooLargeError(MinerUAPIError):
    """The file exceeds the size limit (``-60005``, ``-30001``)."""


class PageLimitError(MinerUAPIError):
    """The file exceeds the page limit (``-60006``, ``-30003``)."""


class UploadError(MinerUAPIError):
    """Applying an upload URL, reading or converting the file failed."""


class QueueFullError(MinerUAPIError):
    """The submission queue is full (``-60009``)."""


class TaskNotFoundError(MinerUAPIError):
    """The task id is unknown (``-60012``)."""


class TaskPermissionError(MinerUAPIError):
    """The task belongs to another account (``-60013``)."""


class QuotaExceededError(MinerUAPIError):
    """A daily quota was exhausted (``-60018``, ``-60019``)."""


class ServerError(MinerUAPIError):
    """A transient server-side failure (``-10001``, ``-60007``, ``-60010``)."""


class TaskFailedError(MinerUError):
    """A task reached the ``failed`` state.

    Attributes:
        message: the ``err_msg`` reported by the API.
        code: an optional numeric error code when the API supplies one.
        task_id: the id of the failed task, when known.
    """

    def __init__(
        self,
        message: str | None = None,
        code: Any | None = None,
        task_id: str | None = None,
    ) -> None:
        self.message = message or "task failed"
        self.code = code
        self.task_id = task_id
        detail = self.message
        if code is not None:
            detail = f"[{code}] {detail}"
        if task_id:
            detail = f"{detail} (task_id={task_id})"
        super().__init__(detail)


class PollTimeoutError(MinerUError):
    """Polling did not reach a terminal state within the timeout."""

    def __init__(self, timeout: float, task_id: str | None = None) -> None:
        self.timeout = timeout
        self.task_id = task_id
        detail = f"polling timed out after {timeout:g}s"
        if task_id:
            detail = f"{detail} (task_id={task_id})"
        super().__init__(detail)


#: Documented MinerU error codes mapped onto the exception raised for them.
_CODE_MAP: dict[Any, type[MinerUAPIError]] = {
    "A0202": AuthenticationError,
    "A0211": TokenExpiredError,
    -500: InvalidParamsError,
    -10001: ServerError,
    -10002: InvalidParamsError,
    -60001: UploadError,
    -60002: FileTypeError,
    -60003: UploadError,
    -60004: UploadError,
    -60005: FileTooLargeError,
    -60006: PageLimitError,
    -60007: ServerError,
    -60008: UploadError,
    -60009: QueueFullError,
    -60010: ServerError,
    -60011: UploadError,
    -60012: TaskNotFoundError,
    -60013: TaskPermissionError,
    -60014: InvalidParamsError,
    -60015: UploadError,
    -60016: UploadError,
    -60017: ServerError,
    -60018: QuotaExceededError,
    -60019: QuotaExceededError,
    -60020: UploadError,
    -60021: UploadError,
    -60022: UploadError,
    -30001: FileTooLargeError,
    -30002: FileTypeError,
    -30003: PageLimitError,
    -30004: InvalidParamsError,
}


def raise_for_code(
    code: Any,
    message: str | None = None,
    trace_id: str | None = None,
) -> None:
    """Raise the exception matching ``code``.

    Unknown codes fall back to the generic :class:`MinerUAPIError`.
    """
    exc_type = _CODE_MAP.get(code, MinerUAPIError)
    raise exc_type(code, message, trace_id)
