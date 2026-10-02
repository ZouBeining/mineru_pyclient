"""Tests for downloading and safely extracting results."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from fakes import FakeResponse, FakeSession
from mineru_pyclient.files import download_to, extract_zip


def _write_zip(path: Path, members: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)


def test_extract_zip_writes_members(tmp_path: Path) -> None:
    archive = tmp_path / "result.zip"
    _write_zip(archive, {"full.md": "# hi", "sub/data.json": "{}"})
    out = extract_zip(archive, tmp_path / "out")
    assert (out / "full.md").read_text(encoding="utf-8") == "# hi"
    assert (out / "sub" / "data.json").read_text(encoding="utf-8") == "{}"
    assert archive.exists()


def test_extract_zip_can_remove_the_archive(tmp_path: Path) -> None:
    archive = tmp_path / "result.zip"
    _write_zip(archive, {"full.md": "x"})
    extract_zip(archive, tmp_path / "out", remove_zip=True)
    assert not archive.exists()


def test_extract_zip_rejects_zip_slip(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    _write_zip(archive, {"../escape.txt": "nope"})
    with pytest.raises(ValueError):
        extract_zip(archive, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_download_to_writes_bytes_and_creates_parents(tmp_path: Path) -> None:
    session = FakeSession([FakeResponse(content=b"hello")])
    dest = download_to("https://cdn.test/f.md", tmp_path / "nested" / "f.md", session=session)
    assert dest.read_bytes() == b"hello"
    assert dest.parent.is_dir()
    assert session.calls[0]["url"] == "https://cdn.test/f.md"
