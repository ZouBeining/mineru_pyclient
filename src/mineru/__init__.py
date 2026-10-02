"""Python client and CLI for the MinerU document parsing API.

Two API families are wrapped:

* :class:`~mineru.standard.MinerUClient` — the 精准解析 (precise) API,
  ``/api/v4``; requires a token and supports single files, batches and extra
  export formats.
* :class:`~mineru.agent.AgentClient` — the Agent 轻量解析 (lightweight) API,
  ``/api/v1/agent``; needs no token and returns Markdown only.

The same functionality is exposed on the command line via :func:`main`.
"""

from __future__ import annotations

from .agent import AgentClient
from .cli import main
from .config import get_version
from .exceptions import (
    AuthenticationError,
    FileTooLargeError,
    FileTypeError,
    InvalidParamsError,
    MinerUAPIError,
    MinerUError,
    MissingTokenError,
    PageLimitError,
    PollTimeoutError,
    QueueFullError,
    QuotaExceededError,
    ServerError,
    TaskFailedError,
    TaskNotFoundError,
    TaskPermissionError,
    TokenExpiredError,
    UploadError,
)
from .models import (
    TERMINAL_STATES,
    AgentResult,
    BatchFileResult,
    BatchResult,
    ExtractProgress,
    TaskResult,
    TaskState,
)
from .standard import MinerUClient

__version__ = get_version()

__all__ = [
    "__version__",
    "main",
    "MinerUClient",
    "AgentClient",
    "TaskState",
    "TERMINAL_STATES",
    "TaskResult",
    "BatchFileResult",
    "BatchResult",
    "AgentResult",
    "ExtractProgress",
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
]
