"""Downloading parsing results and extracting archives safely."""

from __future__ import annotations

import zipfile
from os import PathLike
from pathlib import Path
from typing import Any, Mapping

import requests

__all__ = ["download_bytes", "download_to", "extract_zip"]


def download_bytes(
    url: str,
    *,
    session: Any = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 60.0,
) -> bytes:
    """Download ``url`` and return its raw body."""
    client = session if session is not None else requests
    response = client.get(
        url,
        headers=dict(headers) if headers else None,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.content


def download_to(
    url: str,
    dest: str | PathLike[str],
    *,
    session: Any = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 60.0,
) -> Path:
    """Download ``url`` to ``dest``, creating parent directories as needed."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(download_bytes(url, session=session, headers=headers, timeout=timeout))
    return dest


def extract_zip(
    zip_path: str | PathLike[str],
    out_dir: str | PathLike[str],
    *,
    remove_zip: bool = False,
) -> Path:
    """Extract ``zip_path`` into ``out_dir`` and return the directory.

    Every member is validated to stay inside ``out_dir`` first, so a malicious
    archive cannot escape via ``..`` segments or absolute paths (zip-slip).

    Raises:
        ValueError: when an archive member points outside ``out_dir``.
    """
    zip_path = Path(zip_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    root = out_dir.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (out_dir / member.filename).resolve()
            if target != root and not target.is_relative_to(root):
                raise ValueError(f"unsafe path in archive: {member.filename!r}")
        archive.extractall(out_dir)
    if remove_zip:
        zip_path.unlink(missing_ok=True)
    return out_dir
