"""Command line interface: ``mineru <command> [options]``.

Options may be given either before or after the command::

    mineru --api agent --out-dir out url https://example.com/file.pdf
    mineru url https://example.com/file.pdf --api agent --out-dir out
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .agent import AgentClient
from .config import DEFAULT_AGENT_BASE_URL, DEFAULT_STANDARD_BASE_URL, get_version
from .exceptions import MinerUError
from .standard import EXTRA_FORMATS, MODEL_VERSIONS, MinerUClient

__all__ = ["build_parser", "main"]

#: Standard-API-only options, mapped to the flag used in error messages.
_STANDARD_ONLY_FLAGS = {
    "model_version": "--model-version",
    "page_ranges": "--page-ranges",
    "extra_formats": "--extra-formats",
    "data_id": "--data-id",
    "callback": "--callback",
    "seed": "--seed",
    "no_cache": "--no-cache",
    "cache_tolerance": "--cache-tolerance",
}

#: Options accepted by ``create_file_tasks`` only (the local-upload endpoint).
_FILE_TASK_DROP = ("no_cache", "cache_tolerance")


def _add_bool_flag(
    parser: argparse.ArgumentParser,
    name: str,
    dest: str,
    help_text: str,
    default: Any,
) -> None:
    """Add a ``--x`` / ``--no-x`` pair sharing one tri-state destination.

    The default is left as ``None`` so that "unset" stays distinguishable from
    an explicit ``False``.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument(f"--{name}", dest=dest, action="store_true", default=default, help=help_text)
    group.add_argument(f"--no-{name}", dest=dest, action="store_false", default=default, help=f"disable {name}")


def _add_shared_options(parser: argparse.ArgumentParser, *, suppress_defaults: bool) -> None:
    """Add every option that is common to all commands.

    With ``suppress_defaults`` the defaults become ``argparse.SUPPRESS`` so that
    a subparser does not overwrite values already parsed before the command.
    """
    suppress = argparse.SUPPRESS
    none_default = suppress if suppress_defaults else None
    flag_default = suppress if suppress_defaults else False

    parser.add_argument(
        "--api",
        choices=("standard", "agent"),
        default=suppress if suppress_defaults else "standard",
        help="which API family to call (default: standard)",
    )
    parser.add_argument("--token", default=none_default, help="API token for the standard API (default: $MINERU_TOKEN)")
    parser.add_argument("--base-url", default=none_default, help="override the API base URL")
    parser.add_argument(
        "--out-dir",
        default=suppress if suppress_defaults else "./output",
        help="directory for results (default: ./output)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=suppress if suppress_defaults else 3.0,
        help="polling interval in seconds (default: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=suppress if suppress_defaults else 600.0,
        help="polling timeout in seconds (default: 600)",
    )
    parser.add_argument("--no-wait", action="store_true", default=flag_default, help="submit and print the task id without waiting")
    parser.add_argument("--json", action="store_true", default=flag_default, help="print raw JSON instead of a summary")
    parser.add_argument("-v", "--verbose", action="store_true", default=flag_default, help="report progress while polling")

    parser.add_argument("--language", default=none_default, help="document language (default: ch)")
    _add_bool_flag(parser, "ocr", "is_ocr", "enable OCR (default: off)", none_default)
    _add_bool_flag(parser, "formula", "enable_formula", "enable formula recognition (default: on)", none_default)
    _add_bool_flag(parser, "table", "enable_table", "enable table recognition (default: on)", none_default)

    parser.add_argument("--model-version", choices=MODEL_VERSIONS, default=none_default, help="model version (standard API only)")
    parser.add_argument("--page-ranges", default=none_default, help="page selection such as '2,4-6' (standard API only)")
    parser.add_argument(
        "--extra-formats",
        action="append",
        choices=EXTRA_FORMATS,
        default=none_default,
        help="extra export format, repeatable (standard API only)",
    )
    parser.add_argument("--data-id", default=none_default, help="business data id (standard API only)")
    parser.add_argument("--callback", default=none_default, help="callback URL (standard API only)")
    parser.add_argument("--seed", default=none_default, help="callback signature seed (standard API only)")
    parser.add_argument("--no-cache", dest="no_cache", action="store_true", default=none_default, help="bypass the URL cache (standard API only)")
    parser.add_argument("--cache-tolerance", type=int, default=none_default, help="cache tolerance in seconds (standard API only)")

    parser.add_argument("--file-name", default=none_default, help="file name hint (agent API only)")
    parser.add_argument("--page-range", default=none_default, help="page selection such as '1-10' (agent API only)")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``mineru`` command."""
    parser = argparse.ArgumentParser(
        prog="mineru",
        description="Parse documents with the MinerU API.",
        epilog="Options may be placed before or after the command.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {get_version()}")
    _add_shared_options(parser, suppress_defaults=False)

    # The same options are attached to every subcommand so they also work when
    # written after the command; SUPPRESS defaults keep the earlier value.
    common = argparse.ArgumentParser(add_help=False)
    _add_shared_options(common, suppress_defaults=True)

    subcommands = parser.add_subparsers(dest="command", required=True)
    url_parser = subcommands.add_parser("url", parents=[common], help="parse a document by URL")
    url_parser.add_argument("url")
    file_parser = subcommands.add_parser("file", parents=[common], help="parse one or more local files")
    file_parser.add_argument("paths", nargs="+")
    status_parser = subcommands.add_parser("status", parents=[common], help="query a task or batch by id")
    status_parser.add_argument("id")
    status_parser.add_argument("--batch", action="store_true", help="treat the id as a batch id")
    return parser


def _standard_options(args: argparse.Namespace, *, drop: Sequence[str] = ()) -> dict[str, Any]:
    """Collect the parsing options for the standard API, dropping unset ones."""
    values = {
        "language": args.language,
        "is_ocr": args.is_ocr,
        "enable_formula": args.enable_formula,
        "enable_table": args.enable_table,
        "page_ranges": args.page_ranges,
        "model_version": args.model_version,
        "data_id": args.data_id,
        "callback": args.callback,
        "seed": args.seed,
        "no_cache": args.no_cache,
        "cache_tolerance": args.cache_tolerance,
        "extra_formats": args.extra_formats,
    }
    return {
        key: value
        for key, value in values.items()
        if value is not None and key not in drop
    }


def _agent_options(args: argparse.Namespace) -> dict[str, Any]:
    """Collect the parsing options for the agent API, dropping unset ones."""
    values = {
        "language": args.language,
        "is_ocr": args.is_ocr,
        "enable_formula": args.enable_formula,
        "enable_table": args.enable_table,
        "file_name": args.file_name,
        "page_range": args.page_range,
    }
    return {key: value for key, value in values.items() if value is not None}


def _validate_agent_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Reject options the agent API cannot honour."""
    used = [flag for key, flag in _STANDARD_ONLY_FLAGS.items() if getattr(args, key, None)]
    if used:
        parser.error("the agent API does not support: " + ", ".join(used))
    if args.page_range and "," in args.page_range:
        parser.error("the agent API only supports 'from-to' or a single page in --page-range")
    if args.command == "file" and len(args.paths) > 1:
        parser.error("the agent API accepts a single file per request")


def _progress(args: argparse.Namespace):
    """Return a progress callback when verbose output is requested."""
    if not args.verbose:
        return None

    def report(result: Any) -> None:
        state = getattr(result, "state", None)
        print(f"  ... {getattr(state, 'value', state)}", file=sys.stderr)

    return report


def _print(args: argparse.Namespace, result: Any, *, path: Path | None = None, paths: Sequence[Path] = ()) -> None:
    """Print a human readable summary, or the raw payload with ``--json``."""
    if args.json:
        print(json.dumps(getattr(result, "raw", {}), ensure_ascii=False, indent=2))
        return
    state = getattr(result, "state", None)
    print(f"state: {getattr(state, 'value', state)}")
    for label in ("task_id", "batch_id"):
        value = getattr(result, label, None)
        if value:
            print(f"{label}: {value}")
    remote = getattr(result, "full_zip_url", None) or getattr(result, "markdown_url", None)
    if remote:
        print(f"result: {remote}")
    if path is not None:
        print(f"saved to: {path}")
    for saved in paths:
        print(f"saved to: {saved}")


def _status(args: argparse.Namespace, client: Any) -> int:
    if args.api == "standard" and args.batch:
        result = client.get_batch(args.id)
    else:
        result = client.get_task(args.id)
    _print(args, result)
    if getattr(result, "is_terminal", False) and not getattr(result, "is_done", False):
        return 1
    return 0


def _parse_url(args: argparse.Namespace, client: Any) -> int:
    if args.api == "agent":
        if args.no_wait:
            print(client.create_url_task(args.url, **_agent_options(args)))
            return 0
        result = client.parse_url(
            args.url,
            args.out_dir,
            interval=args.interval,
            timeout=args.timeout,
            on_progress=_progress(args),
            **_agent_options(args),
        )
        _print(args, result, path=result if isinstance(result, Path) else None)
        return 0
    task_id = client.create_url_task(args.url, **_standard_options(args))
    if args.no_wait:
        print(task_id)
        return 0
    result = client.wait(task_id, interval=args.interval, timeout=args.timeout, on_progress=_progress(args))
    saved = client.download_result(result, args.out_dir)
    _print(args, result, path=saved)
    return 0


def _parse_files(args: argparse.Namespace, client: Any) -> int:
    if args.api == "agent":
        source = args.paths[0]
        if args.no_wait:
            print(client.create_file_task(source, **_agent_options(args)))
            return 0
        result = client.parse_file(
            source,
            args.out_dir,
            interval=args.interval,
            timeout=args.timeout,
            on_progress=_progress(args),
            **_agent_options(args),
        )
        _print(args, result, path=result if isinstance(result, Path) else None)
        return 0
    batch_id = client.create_file_tasks(args.paths, **_standard_options(args, drop=_FILE_TASK_DROP))
    if args.no_wait:
        print(batch_id)
        return 0
    batch = client.wait_batch(batch_id, interval=args.interval, timeout=args.timeout, on_progress=_progress(args))
    saved = client.download_batch_results(batch, args.out_dir)
    _print(args, batch, paths=saved)
    return 0


def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.api == "agent":
        _validate_agent_args(args, parser)
        client: Any = AgentClient(base_url=args.base_url or DEFAULT_AGENT_BASE_URL)
    else:
        client = MinerUClient(args.token, base_url=args.base_url or DEFAULT_STANDARD_BASE_URL)

    if args.command == "status":
        return _status(args, client)
    if args.command == "url":
        return _parse_url(args, client)
    return _parse_files(args, client)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``mineru`` console script."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args, parser)
    except MinerUError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("interrupted", file=sys.stderr)
        return 130
