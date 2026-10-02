"""Client for the MinerU Agent 轻量解析 (lightweight) API, ``/api/v1/agent``."""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Any, Callable

from .config import DEFAULT_AGENT_BASE_URL
from .exceptions import MinerUError
from .files import download_to
from .http import Transport
from .models import AgentResult
from .polling import poll

__all__ = ["AgentClient"]


def _drop_none(**values: Any) -> dict[str, Any]:
    """Return ``values`` without the ``None`` entries."""
    return {key: value for key, value in values.items() if value is not None}


class AgentClient:
    """Lightweight parsing client for ``https://mineru.net/api/v1/agent``.

    This API needs no token and returns Markdown only. It accepts one file per
    request and is limited to 10 MB / 20 pages.

    Args:
        base_url: override the API root (useful for tests and mirrors).
        session: a ``requests.Session``-like object; inject a fake for tests.
        timeout: per-request timeout in seconds.
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_AGENT_BASE_URL,
        session: Any = None,
        timeout: float = 60.0,
    ) -> None:
        self._transport = Transport(
            base_url,
            session=session,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )

    # ------------------------------------------------------------------ create

    def create_url_task(
        self,
        url: str,
        *,
        file_name: str | None = None,
        language: str | None = None,
        enable_table: bool | None = None,
        is_ocr: bool | None = None,
        enable_formula: bool | None = None,
        page_range: str | None = None,
    ) -> str:
        """Submit a remote document by URL and return its ``task_id``."""
        payload = _drop_none(
            url=url,
            file_name=file_name,
            language=language,
            enable_table=enable_table,
            is_ocr=is_ocr,
            enable_formula=enable_formula,
            page_range=page_range,
        )
        data = self._transport.request("POST", "/parse/url", json=payload)
        return data["task_id"]

    def create_file_task(
        self,
        path: str | PathLike[str],
        *,
        file_name: str | None = None,
        language: str | None = None,
        enable_table: bool | None = None,
        is_ocr: bool | None = None,
        enable_formula: bool | None = None,
        page_range: str | None = None,
    ) -> str:
        """Request a signed upload URL, upload the file and return ``task_id``."""
        path = Path(path)
        payload = _drop_none(
            file_name=file_name or path.name,
            language=language,
            enable_table=enable_table,
            is_ocr=is_ocr,
            enable_formula=enable_formula,
            page_range=page_range,
        )
        data = self._transport.request("POST", "/parse/file", json=payload)
        self._transport.put_bytes(data["file_url"], path.read_bytes())
        return data["task_id"]

    # ------------------------------------------------------------------ query

    def get_task(self, task_id: str) -> AgentResult:
        """Fetch the current state of a task."""
        data = self._transport.request("GET", f"/parse/{task_id}")
        return AgentResult.from_raw(data or {})

    def wait(
        self,
        task_id: str,
        *,
        interval: float = 3.0,
        timeout: float = 600.0,
        on_progress: Callable[[AgentResult], None] | None = None,
    ) -> AgentResult:
        """Poll ``task_id`` until it finishes and return the final result."""
        return poll(
            lambda: self.get_task(task_id),
            is_terminal=lambda result: result.is_terminal,
            is_done=lambda result: result.is_done,
            interval=interval,
            timeout=timeout,
            on_progress=on_progress,
            task_id=task_id,
        )

    # ------------------------------------------------------------ convenience

    def parse_url(
        self,
        url: str,
        out_dir: str | PathLike[str] | None = None,
        *,
        interval: float = 3.0,
        timeout: float = 600.0,
        on_progress: Callable[[AgentResult], None] | None = None,
        **options: Any,
    ) -> AgentResult | Path:
        """Submit and wait for a URL.

        Returns the :class:`AgentResult` when ``out_dir`` is ``None``,
        otherwise downloads the Markdown into ``out_dir`` and returns its path.
        """
        task_id = self.create_url_task(url, **options)
        result = self.wait(task_id, interval=interval, timeout=timeout, on_progress=on_progress)
        if out_dir is None:
            return result
        return self._save_markdown(result, Path(out_dir), options.get("file_name") or url)

    def parse_file(
        self,
        path: str | PathLike[str],
        out_dir: str | PathLike[str] | None = None,
        *,
        interval: float = 3.0,
        timeout: float = 600.0,
        on_progress: Callable[[AgentResult], None] | None = None,
        **options: Any,
    ) -> AgentResult | Path:
        """Upload and wait for a local file.

        Returns the :class:`AgentResult` when ``out_dir`` is ``None``,
        otherwise downloads the Markdown into ``out_dir`` and returns its path.
        """
        path = Path(path)
        task_id = self.create_file_task(path, **options)
        result = self.wait(task_id, interval=interval, timeout=timeout, on_progress=on_progress)
        if out_dir is None:
            return result
        name = options.get("file_name") or path.name
        return self._save_markdown(result, Path(out_dir), name)

    def _save_markdown(
        self,
        result: AgentResult,
        out_dir: Path,
        name_hint: str | None = None,
    ) -> Path:
        if not result.markdown_url:
            raise MinerUError("the task produced no downloadable markdown")
        stem = Path(name_hint).stem if name_hint else ""
        if not stem:
            stem = result.task_id or "result"
        dest = out_dir / f"{stem}.md"
        download_to(
            result.markdown_url,
            dest,
            session=self._transport.session,
            timeout=self._transport.timeout,
        )
        return dest
