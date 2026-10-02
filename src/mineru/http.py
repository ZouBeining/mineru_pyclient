"""HTTP transport shared by the API clients.

:class:`Transport` owns everything that is common to every endpoint: building
the request, checking the HTTP status, unwrapping the
``{"code", "msg", "trace_id", "data"}`` envelope and mapping error codes onto
exceptions. The API clients only assemble paths and payloads.
"""

from __future__ import annotations

from typing import Any, Mapping

import requests

from .exceptions import raise_for_code

__all__ = ["Transport"]


class Transport:
    """Thin wrapper around a :class:`requests.Session`.

    Args:
        base_url: root URL the request paths are joined to.
        session: an object exposing ``request``/``put``/``get``, by default a
            fresh :class:`requests.Session`. Injecting a fake session keeps the
            clients fully testable without touching the network.
        headers: default headers sent with every JSON request.
        timeout: per-request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        *,
        session: requests.Session | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session if session is not None else requests.Session()
        self.headers = dict(headers or {})
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
    ) -> Any:
        """Perform a JSON request and return the unwrapped ``data`` field.

        Raises:
            requests.HTTPError: on a non-2xx HTTP status.
            MinerUAPIError: when the envelope reports a non-zero ``code``.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = self.session.request(
            method,
            url,
            json=json,
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return self._unwrap(response)

    def put_bytes(
        self,
        url: str,
        data: bytes,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """Upload raw bytes to ``url``.

        Neither a ``Content-Type`` nor the API token is attached: the MinerU
        upload endpoints expect a bare body and the returned URLs already carry
        their own authorization.
        """
        response = self.session.put(
            url,
            data=data,
            headers=dict(headers) if headers else None,
            timeout=self.timeout,
        )
        response.raise_for_status()

    @staticmethod
    def _unwrap(response: requests.Response) -> Any:
        """Validate the envelope and return its ``data`` field."""
        body = response.json()
        if not isinstance(body, Mapping) or "code" not in body:
            return body
        code = body.get("code")
        if code != 0:
            raise_for_code(code, body.get("msg"), body.get("trace_id"))
        return body.get("data")
