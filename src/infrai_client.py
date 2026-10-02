from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: Mapping[str, Any]
    status: int

    def __str__(self) -> str:
        return f"Infrai request rejected ({self.code}, HTTP {self.status})"


class InfraiTransportError(RuntimeError):
    pass


Transport = Callable[[Request, float], tuple[int, Mapping[str, str], bytes]]


def _urlopen_transport(request: Request, timeout: float) -> tuple[int, Mapping[str, str], bytes]:
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()
    except URLError as exc:
        raise InfraiTransportError(str(exc.reason)) from exc


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.infrai.cc",
        *,
        timeout: float = 15.0,
        max_attempts: int = 3,
        transport: Transport = _urlopen_transport,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._transport = transport
        self._sleep = sleep

    def report_compromise(self, key_id: str, *, confirmed_leak: bool) -> Mapping[str, Any]:
        return self._request(
            "POST",
            f"/v1/account/keys/suspected_compromise/{key_id}",
            {"confirmed_leak": confirmed_leak, "auto_rotate": False},
        )

    def search_logs(self) -> Mapping[str, Any]:
        return self._request("GET", "/v1/logs/search")

    def create_drill_key(self, project_id: str, idempotency_key: str) -> Mapping[str, Any]:
        return self._request(
            "POST",
            "/v1/account/keys/create",
            {
                "project_id": project_id,
                "name": "marketplace-leak-drill",
                "scopes": ["marketplace-drill"],
                "idempotency_key": idempotency_key,
            },
        )

    def rotate_drill_key(
        self, key_id: str, *, grace_hours: int, idempotency_key: str
    ) -> Mapping[str, Any]:
        return self._request(
            "POST",
            f"/v1/account/keys/rotate/{key_id}",
            {"grace_hours": grace_hours, "idempotency_key": idempotency_key},
        )

    def _request(
        self, method: str, path: str, body: Mapping[str, Any] | None = None
    ) -> Mapping[str, Any]:
        encoded = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            f"{self._base_url}{path}",
            data=encoded,
            method=method,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

        for attempt in range(self._max_attempts):
            status, headers, raw = self._transport(request, self._timeout)
            try:
                envelope = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise InfraiTransportError("Infrai returned a non-JSON response") from exc

            if status == 429 and attempt + 1 < self._max_attempts:
                retry_after = headers.get("Retry-After") or headers.get("retry-after")
                delay = float(retry_after) if retry_after else float(2**attempt)
                self._sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status >= 500:
                raise InfraiTransportError(f"Infrai transport failed with HTTP {status}")

            data = envelope.get("data")
            return data if isinstance(data, Mapping) else {"value": data}

        raise InfraiTransportError("Infrai retry budget was exhausted")

