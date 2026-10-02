"""Test doubles for the MinerU clients.

These fakes stand in for ``requests.Session`` so the suite never touches the
network. They record every call and replay a queued list of responses.
"""

from __future__ import annotations

from typing import Any

import requests


class FakeResponse:
    """Minimal stand-in for :class:`requests.Response`."""

    def __init__(
        self,
        payload: Any = None,
        *,
        status_code: int = 200,
        content: bytes = b"",
        json_error: bool = False,
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.content = content
        self._json_error = json_error
        self.headers: dict[str, str] = {}

    def json(self) -> Any:
        if self._json_error:
            raise ValueError("response body is not JSON")
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class FakeSession:
    """Records calls and replays queued responses in order."""

    def __init__(self, responses: list[Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._queue: list[Any] = list(responses or [])

    def _next(self) -> FakeResponse:
        if not self._queue:
            raise AssertionError("FakeSession ran out of queued responses")
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._next()

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": "GET", "url": url, **kwargs})
        return self._next()

    def put(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": "PUT", "url": url, **kwargs})
        return self._next()


def envelope(
    data: Any = None,
    *,
    code: Any = 0,
    msg: str = "ok",
    trace_id: str = "trace-1",
) -> dict[str, Any]:
    """Build a MinerU response envelope."""
    return {"code": code, "msg": msg, "trace_id": trace_id, "data": data}
