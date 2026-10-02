"""Tests for the shared HTTP transport."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from fakes import FakeResponse, FakeSession, envelope
from mineru_pyclient.exceptions import (
    AuthenticationError,
    FileTooLargeError,
    FileTypeError,
    InvalidParamsError,
    MinerUAPIError,
    PageLimitError,
    QuotaExceededError,
    ServerError,
    TaskNotFoundError,
    TokenExpiredError,
    raise_for_code,
)
from mineru_pyclient.http import Transport


def _transport(responses: list[Any]) -> tuple[Transport, FakeSession]:
    session = FakeSession(responses)
    transport = Transport(
        "https://api.test/api/v4",
        session=session,
        headers={"Authorization": "Bearer t"},
        timeout=5.0,
    )
    return transport, session


def test_request_unwraps_the_data_field() -> None:
    transport, session = _transport([FakeResponse(envelope({"task_id": "abc"}))])
    data = transport.request("POST", "/extract/task", json={"url": "u"})
    assert data == {"task_id": "abc"}
    call = session.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.test/api/v4/extract/task"
    assert call["json"] == {"url": "u"}
    assert call["headers"] == {"Authorization": "Bearer t"}
    assert call["timeout"] == 5.0


def test_request_returns_none_data() -> None:
    transport, _ = _transport([FakeResponse(envelope(None))])
    assert transport.request("GET", "/x") is None


def test_request_joins_base_and_path_without_extra_slashes() -> None:
    transport, session = _transport([FakeResponse(envelope({}))])
    transport.request("GET", "extract/task/1")
    assert session.calls[0]["url"] == "https://api.test/api/v4/extract/task/1"


def test_non_envelope_body_is_returned_unchanged() -> None:
    transport, _ = _transport([FakeResponse({"unexpected": True})])
    assert transport.request("GET", "/x") == {"unexpected": True}


def test_error_code_raises_mapped_exception() -> None:
    transport, _ = _transport(
        [FakeResponse(envelope(None, code=-60012, msg="not found", trace_id="tr-9"))]
    )
    with pytest.raises(TaskNotFoundError) as excinfo:
        transport.request("GET", "/x")
    assert excinfo.value.code == -60012
    assert excinfo.value.message == "not found"
    assert excinfo.value.trace_id == "tr-9"


def test_http_error_propagates() -> None:
    transport, _ = _transport([FakeResponse(envelope(None), status_code=500)])
    with pytest.raises(requests.HTTPError):
        transport.request("GET", "/x")


def test_put_bytes_sends_a_bare_body_without_content_type() -> None:
    transport, session = _transport([FakeResponse(envelope(None))])
    transport.put_bytes("https://upload.test/file", b"payload")
    call = session.calls[0]
    assert call["method"] == "PUT"
    assert call["url"] == "https://upload.test/file"
    assert call["data"] == b"payload"
    assert call["headers"] is None


def test_put_bytes_forwards_explicit_headers() -> None:
    transport, session = _transport([FakeResponse(envelope(None))])
    transport.put_bytes("https://upload.test/file", b"x", headers={"X-Test": "1"})
    assert session.calls[0]["headers"] == {"X-Test": "1"}


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("A0202", AuthenticationError),
        ("A0211", TokenExpiredError),
        (-500, InvalidParamsError),
        (-10001, ServerError),
        (-10002, InvalidParamsError),
        (-60002, FileTypeError),
        (-60005, FileTooLargeError),
        (-60006, PageLimitError),
        (-60012, TaskNotFoundError),
        (-60018, QuotaExceededError),
        (-30001, FileTooLargeError),
        (-30002, FileTypeError),
        (-30003, PageLimitError),
        (-30004, InvalidParamsError),
        (999999, MinerUAPIError),
    ],
)
def test_raise_for_code_maps_known_codes(code: Any, expected: type[MinerUAPIError]) -> None:
    with pytest.raises(expected):
        raise_for_code(code, "message", "trace")
