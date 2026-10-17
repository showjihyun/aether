"""`UrllibTransport` - 127.0.0.1 의 임시 서버로 실제 `urllib` 경로를 확인한다(컨테이너 없음).

pytest-socket 이 127.0.0.1 만 허용하므로 외부 네트워크는 닿지 않는다.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from aether_cli.contract import CREATE_AGENT, RUN_EVENTS
from aether_cli.sse import parse_sse
from aether_cli.transport import ApiError, ConnectionFailed, UrllibTransport

KEY = "aether_sk_loopback_secret"
SEEN: list[dict[str, Any]] = []


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _record(self, body: bytes) -> None:
        SEEN.append(
            {
                "method": self.command,
                "path": self.path,
                "auth": self.headers.get("Authorization"),
                "body": json.loads(body) if body else None,
            }
        )

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self._record(self.rfile.read(length))
        if self.headers.get("Authorization") != f"Bearer {KEY}":
            payload = json.dumps({"detail": "unauthorized"}).encode()
            self.send_response(401)
        else:
            payload = json.dumps({"id": "abc"}).encode()
            self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        self._record(b"")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        # 서버가 한 이벤트를 쓰고 flush 한 뒤 **닫기 전에** 클라이언트가 그것을 읽어야 한다.
        self.wfile.write(
            b': keep-alive\n\nid: 1\nevent: run.status\ndata: {"a": "\xea\xb0\x80"}\n\n'
        )
        self.wfile.flush()
        # 끊김: finished 없이 연결을 닫는다.


@contextmanager
def _server() -> Iterator[str]:
    SEEN.clear()
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_request_sends_bearer_key_and_json_body_and_decodes_the_reply() -> None:
    """D-1·D-8: urllib 로 `Authorization: Bearer` 와 JSON 본문을 보낸다."""
    with _server() as base:
        reply = UrllibTransport(base, KEY).request(CREATE_AGENT, body={"name": "가"})

    assert reply == {"id": "abc"}
    assert SEEN[0]["method"] == "POST" and SEEN[0]["path"] == "/agents"
    assert SEEN[0]["auth"] == f"Bearer {KEY}"
    assert SEEN[0]["body"] == {"name": "가"}


def test_http_error_becomes_api_error_without_the_key() -> None:
    """401 은 `ApiError` 로, 메시지에 키가 없다."""
    with _server() as base, pytest.raises(ApiError) as caught:
        UrllibTransport(base, "wrong-key").request(CREATE_AGENT, body={})

    assert caught.value.status == 401
    assert "unauthorized" in str(caught.value)
    assert "wrong-key" not in str(caught.value)


def test_unreachable_server_becomes_connection_failed_without_the_key() -> None:
    """닫힌 포트는 `ConnectionFailed`, 메시지에 키가 없다."""
    with _server() as base:
        pass  # 서버를 닫은 뒤의 주소
    with pytest.raises(ConnectionFailed) as caught:
        UrllibTransport(base, KEY).request(CREATE_AGENT, body={})

    assert KEY not in str(caught.value)


def test_stream_yields_lines_that_parse_to_events_and_ends_when_the_server_closes() -> None:
    """요구 6: SSE 를 줄 단위로 읽어 파싱한다. keep-alive 주석은 이벤트가 아니다."""
    with _server() as base:
        lines = UrllibTransport(base, KEY).stream(RUN_EVENTS, params={"run_id": "r1"})
        events = list(parse_sse(lines))

    assert SEEN[0]["path"] == "/runs/r1/events"
    assert SEEN[0]["auth"] == f"Bearer {KEY}"
    assert [(e.event, e.id) for e in events] == [("run.status", "1")]
    assert json.loads(events[0].data) == {"a": "가"}
