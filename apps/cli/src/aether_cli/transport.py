"""HTTP 계층 - 표준 라이브러리 `urllib` 만 씁니다 (spec 0006 D-1).

명령은 `Transport` 프로토콜에만 기대므로 단위 테스트가 네트워크 없이 fake 를 꽂습니다. API 키는
`UrllibTransport` 안의 `Authorization` 헤더에만 있고 **오류 메시지·출력에 싣지 않습니다**(D-8).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator, Mapping
from typing import Any, Protocol

from aether_cli.contract import Endpoint

REQUEST_TIMEOUT_SECONDS = 30.0
# 서버가 15초마다 keep-alive 주석을 보냅니다. 그 몇 배 동안 아무 바이트도 없으면 끊긴 것입니다.
STREAM_READ_TIMEOUT_SECONDS = 60.0
_DETAIL_LIMIT = 300


class ApiError(Exception):
    """서버가 2xx 가 아닌 응답을 했습니다."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"HTTP {status} {detail}".strip())
        self.status = status
        self.detail = detail


class ConnectionFailed(Exception):
    """서버에 닿지 못했거나 연결이 중간에 끊겼습니다."""


class Transport(Protocol):
    def request(
        self,
        endpoint: Endpoint,
        *,
        params: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> Any:
        """JSON 응답을 디코드해 돌려줍니다. 실패는 `ApiError`·`ConnectionFailed`."""
        ...

    def stream(
        self, endpoint: Endpoint, *, params: Mapping[str, str] | None = None
    ) -> Iterator[bytes]:
        """응답 본문을 **줄 단위 바이트**로 도착하는 대로 내보냅니다. 끊기면 `ConnectionFailed`."""
        ...


def _detail_of(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except ValueError:
        return text[:_DETAIL_LIMIT]
    if isinstance(parsed, dict) and "detail" in parsed:
        parsed = parsed["detail"]
    rendered = parsed if isinstance(parsed, str) else json.dumps(parsed, ensure_ascii=False)
    return rendered[:_DETAIL_LIMIT]


class UrllibTransport:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def _build(
        self,
        endpoint: Endpoint,
        params: Mapping[str, str] | None,
        query: Mapping[str, str] | None,
        body: Mapping[str, Any] | None,
        accept: str,
    ) -> urllib.request.Request:
        url = self._base_url + endpoint.render(**(params or {}))
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self._api_key}", "Accept": accept}
        if data is not None:
            headers["Content-Type"] = "application/json"
        return urllib.request.Request(url, data=data, headers=headers, method=endpoint.method)

    def request(
        self,
        endpoint: Endpoint,
        *,
        params: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> Any:
        req = self._build(endpoint, params, query, body, "application/json")
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ApiError(exc.code, _detail_of(exc.read())) from None
        except (urllib.error.URLError, OSError) as exc:
            raise ConnectionFailed(f"{self._base_url} 에 연결하지 못했습니다: {exc}") from None

    def stream(
        self, endpoint: Endpoint, *, params: Mapping[str, str] | None = None
    ) -> Iterator[bytes]:
        req = self._build(endpoint, params, None, None, "text/event-stream")
        try:
            response = urllib.request.urlopen(req, timeout=STREAM_READ_TIMEOUT_SECONDS)
        except urllib.error.HTTPError as exc:
            raise ApiError(exc.code, _detail_of(exc.read())) from None
        except (urllib.error.URLError, OSError) as exc:
            raise ConnectionFailed(f"{self._base_url} 에 연결하지 못했습니다: {exc}") from None
        return self._lines(response)

    @staticmethod
    def _lines(response: Any) -> Iterator[bytes]:
        try:
            with response:
                while True:
                    line = response.readline()
                    if not line:
                        return
                    yield line
        except OSError as exc:
            raise ConnectionFailed(f"스트림 연결이 끊어졌습니다: {exc}") from None
