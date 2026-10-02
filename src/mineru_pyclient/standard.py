"""Client for the MinerU 精准解析 (precise) API, ``/api/v4``."""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Any, Callable, Sequence

from .config import DEFAULT_STANDARD_BASE_URL, resolve_token
from .exceptions import MinerUError
from .files import download_to, extract_zip
from .http import Transport
from .models import BatchResult, TaskResult
from .polling import poll

__all__ = ["MinerUClient"]

#: Model versions accepted by :class:`MinerUClient`.
MODEL_VERSIONS = ("pipeline", "vlm", "MinerU-HTML")

#: Extra export formats accepted by :class:`MinerUClient`.
EXTRA_FORMATS = ("docx", "html", "latex")


def _drop_none(**values: Any) -> dict[str, Any]:
    """Return ``values`` without the ``None`` entries."""
    return {key: value for key, value in values.items() if value is not None}


class MinerUClient:
    """Precise parsing client for ``https://mineru.net/api/v4``.

    The API is asynchronous: a task is submitted, then polled until it reaches
    ``done`` or ``failed``. This client wraps both halves and can also download
    and extract the resulting archive.

    Args:
        token: API token; falls back to ``$MINERU_TOKEN`` when omitted.
        base_url: override the API root (useful for tests and mirrors).
        session: a ``requests.Session``-like object; inject a fake for tests.
        timeout: per-request timeout in seconds.

    Raises:
        MissingTokenError: when no token can be found.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = DEFAULT_STANDARD_BASE_URL,
        session: Any = None,
        timeout: float = 60.0,
    ) -> None:
        self.token = resolve_token(token)
        self._transport = Transport(
            base_url,
            session=session,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
            timeout=timeout,
        )

    # ------------------------------------------------------------------ create

    def create_url_task(
        self,
        url: str,
        *,
        is_ocr: bool = False,
        enable_formula: bool = True,
        enable_table: bool = True,
        language: str = "ch",
        data_id: str | None = None,
        callback: str | None = None,
        seed: str | None = None,
        extra_formats: Sequence[str] | None = None,
        page_ranges: str | None = None,
        model_version: str = "pipeline",
        no_cache: bool = False,
        cache_tolerance: int | None = None,
    ) -> str:
        """Submit a single document by URL and return its ``task_id``."""
        payload = _drop_none(
            url=url,
            is_ocr=is_ocr,
            enable_formula=enable_formula,
            enable_table=enable_table,
            language=language,
            data_id=data_id,
            callback=callback,
            seed=seed,
            extra_formats=list(extra_formats) if extra_formats is not None else None,
            page_ranges=page_ranges,
            model_version=model_version,
            no_cache=no_cache,
            cache_tolerance=cache_tolerance,
        )
        data = self._transport.request("POST", "/extract/task", json=payload)
        return data["task_id"]

    def create_file_tasks(
        self,
        paths: Sequence[str | PathLike[str]],
        *,
        is_ocr: bool = False,
        enable_formula: bool = True,
        enable_table: bool = True,
        language: str = "ch",
        data_id: str | None = None,
        callback: str | None = None,
        seed: str | None = None,
        extra_formats: Sequence[str] | None = None,
        page_ranges: str | None = None,
        model_version: str = "pipeline",
    ) -> str:
        """Upload local files and return the ``batch_id``.

        Upload URLs are requested for every path, then each file's bytes are
        ``PUT`` to its own URL. The server picks the files up automatically, so
        no extra submission call is needed.
        """
        files = [Path(path) for path in paths]
        if not files:
            raise ValueError("at least one file is required")
        payload = _drop_none(
            files=[self._file_entry(path, is_ocr, data_id, page_ranges) for path in files],
            model_version=model_version,
            enable_formula=enable_formula,
            enable_table=enable_table,
            language=language,
            callback=callback,
            seed=seed,
            extra_formats=list(extra_formats) if extra_formats is not None else None,
        )
        data = self._transport.request("POST", "/file-urls/batch", json=payload)
        for path, upload_url in zip(files, data["file_urls"]):
            self._transport.put_bytes(upload_url, path.read_bytes())
        return data["batch_id"]

    def create_url_tasks(
        self,
        urls: Sequence[str],
        *,
        is_ocr: bool = False,
        enable_formula: bool = True,
        enable_table: bool = True,
        language: str = "ch",
        data_id: str | None = None,
        callback: str | None = None,
        seed: str | None = None,
        extra_formats: Sequence[str] | None = None,
        page_ranges: str | None = None,
        model_version: str = "pipeline",
        no_cache: bool = False,
        cache_tolerance: int | None = None,
    ) -> str:
        """Submit several documents by URL and return the ``batch_id``."""
        if not urls:
            raise ValueError("at least one url is required")
        payload = _drop_none(
            files=[self._url_entry(url, is_ocr, data_id, page_ranges) for url in urls],
            model_version=model_version,
            enable_formula=enable_formula,
            enable_table=enable_table,
            language=language,
            callback=callback,
            seed=seed,
            extra_formats=list(extra_formats) if extra_formats is not None else None,
            no_cache=no_cache,
            cache_tolerance=cache_tolerance,
        )
        data = self._transport.request("POST", "/extract/task/batch", json=payload)
        return data["batch_id"]

    @staticmethod
    def _file_entry(
        path: Path,
        is_ocr: bool,
        data_id: str | None,
        page_ranges: str | None,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {"name": path.name}
        if is_ocr:
            entry["is_ocr"] = is_ocr
        if data_id is not None:
            entry["data_id"] = data_id
        if page_ranges is not None:
            entry["page_ranges"] = page_ranges
        return entry

    @staticmethod
    def _url_entry(
        url: str,
        is_ocr: bool,
        data_id: str | None,
        page_ranges: str | None,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {"url": url}
        if is_ocr:
            entry["is_ocr"] = is_ocr
        if data_id is not None:
            entry["data_id"] = data_id
        if page_ranges is not None:
            entry["page_ranges"] = page_ranges
        return entry

    # ------------------------------------------------------------------ query

    def get_task(self, task_id: str) -> TaskResult:
        """Fetch the current state of a single task."""
        data = self._transport.request("GET", f"/extract/task/{task_id}")
        return TaskResult.from_raw(data or {})

    def get_batch(self, batch_id: str) -> BatchResult:
        """Fetch the current state of a batch."""
        data = self._transport.request("GET", f"/extract-results/batch/{batch_id}")
        return BatchResult.from_raw(data or {})

    # ---------------------------------------------------------------- waiting

    def wait(
        self,
        task_id: str,
        *,
        interval: float = 3.0,
        timeout: float = 600.0,
        on_progress: Callable[[TaskResult], None] | None = None,
    ) -> TaskResult:
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

    def wait_batch(
        self,
        batch_id: str,
        *,
        interval: float = 3.0,
        timeout: float = 600.0,
        on_progress: Callable[[BatchResult], None] | None = None,
    ) -> BatchResult:
        """Poll ``batch_id`` until every file finishes."""
        return poll(
            lambda: self.get_batch(batch_id),
            is_terminal=lambda result: result.is_terminal,
            is_done=lambda result: result.is_done,
            interval=interval,
            timeout=timeout,
            on_progress=on_progress,
            task_id=batch_id,
        )

    # -------------------------------------------------------------- download

    def download_result(self, result: TaskResult, out_dir: str | PathLike[str]) -> Path:
        """Download and extract a finished task's archive into ``out_dir``."""
        if not result.full_zip_url:
            raise MinerUError("the task produced no downloadable archive")
        return self._download_and_extract(result.full_zip_url, Path(out_dir))

    def download_batch_results(
        self,
        batch: BatchResult,
        out_dir: str | PathLike[str],
    ) -> list[Path]:
        """Download and extract every finished file of a batch.

        Each archive is extracted into ``out_dir/<file name>``.
        """
        out_dir = Path(out_dir)
        extracted: list[Path] = []
        for item in batch.files:
            if not item.full_zip_url:
                continue
            name = Path(item.file_name or item.task_id or "result").stem
            extracted.append(self._download_and_extract(item.full_zip_url, out_dir / name))
        return extracted

    def _download_and_extract(self, zip_url: str, dest_dir: Path) -> Path:
        archive = dest_dir / "_result.zip"
        download_to(
            zip_url,
            archive,
            session=self._transport.session,
            timeout=self._transport.timeout,
        )
        return extract_zip(archive, dest_dir, remove_zip=True)

    # ------------------------------------------------------------ convenience

    def extract_url(
        self,
        url: str,
        out_dir: str | PathLike[str],
        *,
        interval: float = 3.0,
        timeout: float = 600.0,
        on_progress: Callable[[TaskResult], None] | None = None,
        **options: Any,
    ) -> Path:
        """Submit, wait for and download a single URL in one call."""
        task_id = self.create_url_task(url, **options)
        result = self.wait(task_id, interval=interval, timeout=timeout, on_progress=on_progress)
        return self.download_result(result, out_dir)

    def extract_files(
        self,
        paths: Sequence[str | PathLike[str]],
        out_dir: str | PathLike[str],
        *,
        interval: float = 3.0,
        timeout: float = 600.0,
        on_progress: Callable[[BatchResult], None] | None = None,
        **options: Any,
    ) -> list[Path]:
        """Submit, wait for and download several local files in one call."""
        batch_id = self.create_file_tasks(paths, **options)
        batch = self.wait_batch(batch_id, interval=interval, timeout=timeout, on_progress=on_progress)
        return self.download_batch_results(batch, out_dir)
