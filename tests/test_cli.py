"""Tests for the command line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import mineru_pyclient.cli as cli
from mineru_pyclient.models import AgentResult, BatchResult, TaskResult, TaskState


class FakeStandardClient:
    """Records the calls the CLI makes and returns canned results."""

    last: "FakeStandardClient | None" = None

    def __init__(self, token: str | None = None, *, base_url: str | None = None, **_: Any) -> None:
        self.token = token
        self.base_url = base_url
        self.calls: list[tuple[Any, ...]] = []
        FakeStandardClient.last = self

    def create_url_task(self, url: str, **options: Any) -> str:
        self.calls.append(("create_url_task", url, options))
        return "task-1"

    def wait(self, task_id: str, **_: Any) -> TaskResult:
        self.calls.append(("wait", task_id))
        return TaskResult(task_id=task_id, state=TaskState.DONE, full_zip_url="https://cdn/x.zip")

    def download_result(self, result: TaskResult, out_dir: str) -> Path:
        self.calls.append(("download_result", str(out_dir)))
        return Path(out_dir)

    def create_file_tasks(self, paths: list[str], **options: Any) -> str:
        self.calls.append(("create_file_tasks", list(paths), options))
        return "batch-1"

    def wait_batch(self, batch_id: str, **_: Any) -> BatchResult:
        return BatchResult.from_raw(
            {
                "batch_id": batch_id,
                "extract_result": [{"file_name": "a.pdf", "state": "done"}],
            }
        )

    def download_batch_results(self, batch: BatchResult, out_dir: str) -> list[Path]:
        return [Path(out_dir) / "a"]

    def get_task(self, task_id: str) -> TaskResult:
        return TaskResult(task_id=task_id, state=TaskState.DONE)

    def get_batch(self, batch_id: str) -> BatchResult:
        return BatchResult.from_raw({"batch_id": batch_id, "extract_result": []})


class FakeAgentClient:
    """Minimal stand-in for :class:`~mineru_pyclient.agent.AgentClient`."""

    def __init__(self, *, base_url: str | None = None, **_: Any) -> None:
        self.base_url = base_url

    def create_url_task(self, url: str, **_: Any) -> str:
        return "agent-task"

    def create_file_task(self, path: str, **_: Any) -> str:
        return "agent-file-task"

    def parse_url(self, url: str, out_dir: str | None = None, **_: Any) -> Path:
        return Path(out_dir or ".") / "file.md"

    def parse_file(self, path: str, out_dir: str | None = None, **_: Any) -> Path:
        return Path(out_dir or ".") / "file.md"

    def get_task(self, task_id: str) -> AgentResult:
        return AgentResult(task_id=task_id, state=TaskState.DONE)


@pytest.fixture
def standard(monkeypatch: pytest.MonkeyPatch) -> type[FakeStandardClient]:
    monkeypatch.setattr(cli, "MinerUClient", FakeStandardClient)
    monkeypatch.setenv("MINERU_TOKEN", "token")
    return FakeStandardClient


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch) -> type[FakeAgentClient]:
    monkeypatch.setattr(cli, "AgentClient", FakeAgentClient)
    return FakeAgentClient


def test_parser_defaults() -> None:
    args = cli.build_parser().parse_args(["url", "https://x"])
    assert args.api == "standard"
    assert args.out_dir == "./output"
    assert args.is_ocr is None
    assert args.extra_formats is None


def test_parser_collects_repeated_extra_formats() -> None:
    args = cli.build_parser().parse_args(
        ["--extra-formats", "docx", "--extra-formats", "html", "url", "https://x"]
    )
    assert args.extra_formats == ["docx", "html"]


def test_parser_tristate_bool_flags() -> None:
    parser = cli.build_parser()
    assert parser.parse_args(["url", "https://x"]).is_ocr is None
    assert parser.parse_args(["--ocr", "url", "https://x"]).is_ocr is True
    assert parser.parse_args(["--no-ocr", "url", "https://x"]).is_ocr is False


def test_version_flag_exits_zero() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0


def test_url_no_wait_prints_the_task_id(standard: type[FakeStandardClient], capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["url", "https://x/doc.pdf", "--no-wait"]) == 0
    assert capsys.readouterr().out.strip() == "task-1"


def test_url_waits_and_reports(standard: type[FakeStandardClient], capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    assert cli.main(["--out-dir", str(tmp_path), "url", "https://x/doc.pdf"]) == 0
    out = capsys.readouterr().out
    assert "state: done" in out
    assert "saved to:" in out


def test_file_command_uploads_and_reports_batch(
    standard: type[FakeStandardClient], capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    source = tmp_path / "a.pdf"
    source.write_text("x", encoding="utf-8")
    assert cli.main(["--out-dir", str(tmp_path / "out"), "file", str(source)]) == 0
    assert "batch_id: batch-1" in capsys.readouterr().out


def test_file_command_drops_url_only_options(
    standard: type[FakeStandardClient], tmp_path: Path
) -> None:
    source = tmp_path / "a.pdf"
    source.write_text("x", encoding="utf-8")
    cli.main(["--no-cache", "file", str(source)])
    assert FakeStandardClient.last is not None
    _, _, options = FakeStandardClient.last.calls[0]
    assert "no_cache" not in options


def test_status_batch(standard: type[FakeStandardClient], capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["status", "batch-1", "--batch"]) == 0
    assert "batch_id: batch-1" in capsys.readouterr().out


def test_json_output(standard: type[FakeStandardClient], capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--json", "status", "t"]) == 0
    assert capsys.readouterr().out.strip().startswith("{")


def test_missing_token_is_reported(
    no_token: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["status", "t"]) == 1
    assert "error:" in capsys.readouterr().err


def test_agent_accepts_url_and_saves_markdown(
    agent: type[FakeAgentClient], capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    assert cli.main(["--api", "agent", "--out-dir", str(tmp_path), "url", "https://x/doc.pdf"]) == 0
    assert "saved to:" in capsys.readouterr().out


def test_agent_rejects_standard_only_options(agent: type[FakeAgentClient]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--api", "agent", "--model-version", "vlm", "url", "https://x"])


def test_agent_rejects_multiple_files(agent: type[FakeAgentClient], tmp_path: Path) -> None:
    first = tmp_path / "a.pdf"
    second = tmp_path / "b.pdf"
    first.write_text("x", encoding="utf-8")
    second.write_text("y", encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.main(["--api", "agent", "file", str(first), str(second)])


def test_agent_rejects_comma_separated_page_range(agent: type[FakeAgentClient]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--api", "agent", "--page-range", "1,2", "url", "https://x"])


def test_options_may_follow_the_command(
    standard: type[FakeStandardClient], capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    assert cli.main(["--out-dir", str(tmp_path), "url", "https://x/doc.pdf", "--no-wait"]) == 0
    assert capsys.readouterr().out.strip() == "task-1"


def test_api_selection_after_the_command(
    agent: type[FakeAgentClient], capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code = cli.main(["url", "https://x/doc.pdf", "--api", "agent", "--out-dir", str(tmp_path)])
    assert code == 0
    assert "saved to:" in capsys.readouterr().out
