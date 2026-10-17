"""`aether_cli` 단위 테스트의 공용 fake - HTTP 계층과 cp949 콘솔."""

from __future__ import annotations

import io
import json
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from aether_cli.contract import Endpoint
from aether_cli.main import main
from aether_cli.transport import Transport

API_KEY = "aether_sk_unit_test_secret_0123456789"
RUN_ID = "11111111-1111-1111-1111-111111111111"
AGENT_ID = "22222222-2222-2222-2222-222222222222"


class Cp949Console(io.TextIOWrapper):
    """Windows 한국어 콘솔(cp949)을 흉내 냅니다. `.buffer` 로 UTF-8 을 쓰지 않으면
    em dash 에서 `UnicodeEncodeError` 가 납니다(apps/api/tests/test_cli_stdout_encoding.py)."""

    def __init__(self) -> None:
        self._raw = io.BytesIO()
        super().__init__(self._raw, encoding="cp949", newline="")

    def text(self) -> str:
        self.flush()
        return self._raw.getvalue().decode("utf-8")


@dataclass
class Call:
    method: str
    path: str
    query: dict[str, str] | None
    body: dict[str, Any] | None


def sse_lines(*events: dict[str, Any]) -> list[bytes]:
    """서버(`_format_sse`)와 같은 모양의 SSE 줄들. keep-alive 주석을 앞에 하나 끼웁니다."""
    lines = [b": keep-alive\n", b"\n"]
    for event in events:
        lines.append(f"id: {event['seq']}\n".encode())
        lines.append(f"event: {event['type']}\n".encode())
        lines.append(f"data: {json.dumps(event, ensure_ascii=False)}\n".encode())
        lines.append(b"\n")
    return lines


def event(seq: int, type_: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "v": 1,
        "run_id": RUN_ID,
        "seq": seq,
        "at": "2026-10-17T00:00:00Z",
        "type": type_,
        "payload": payload or {},
    }


@dataclass
class FakeTransport:
    """응답을 `(method, 렌더된 경로)` 로 찾습니다. 없는 경로는 `AssertionError`."""

    responses: dict[tuple[str, str], Any] = field(default_factory=dict)
    stream_factory: Callable[[], Iterator[bytes]] | None = None
    calls: list[Call] = field(default_factory=list)

    def request(
        self,
        endpoint: Endpoint,
        *,
        params: Mapping[str, str] | None = None,
        query: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> Any:
        path = endpoint.render(**(params or {}))
        self.calls.append(
            Call(
                endpoint.method,
                path,
                dict(query) if query is not None else None,
                dict(body) if body is not None else None,
            )
        )
        key = (endpoint.method, path)
        assert key in self.responses, f"unexpected request {key}"
        value = self.responses[key]
        if isinstance(value, list):  # 같은 경로를 여러 번 부르면 차례로
            value = value.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def stream(
        self, endpoint: Endpoint, *, params: Mapping[str, str] | None = None
    ) -> Iterator[bytes]:
        path = endpoint.render(**(params or {}))
        self.calls.append(Call(endpoint.method, path, None, None))
        assert self.stream_factory is not None, "no stream configured"
        return self.stream_factory()


@dataclass
class Result:
    code: int
    out: str
    err: str
    transport: FakeTransport
    factory_calls: list[tuple[str, str]]


def invoke(
    argv: list[str],
    transport: FakeTransport | None = None,
    env: dict[str, str] | None = None,
) -> Result:
    """`main` 을 부릅니다. 기본 환경에는 키가 있고 주소는 비어 있습니다."""
    fake = transport or FakeTransport()
    out, err = Cp949Console(), Cp949Console()
    factory_calls: list[tuple[str, str]] = []

    def factory(url: str, key: str) -> Transport:
        factory_calls.append((url, key))
        return fake

    environment = {"AETHER_API_KEY": API_KEY} if env is None else env
    code = main(argv, env=environment, stdout=out, stderr=err, transport_factory=factory)
    return Result(code, out.text(), err.text(), fake, factory_calls)
