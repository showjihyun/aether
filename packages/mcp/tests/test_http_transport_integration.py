"""spec 0003 R-8(HTTP 절반), 2.2, 2.9 개정 5: HTTP 전송으로 실제 서버 프로세스에
Discovery + 호출 1회. `test_http_mcp_client.py`(P2-1)는 같은 프로세스 안에서
uvicorn 을 스레드로 띄워 R-1 을 판정했지만, 이 테스트는 **별도 서브프로세스**로
띄운 서버에 붙습니다 — R-8 이 요구하는 "실제 서버" 에 더 가깝고, worker 가 실제로
조립하는 `_TransportRoutingMcpClient`(P2-5 2단계, `aether_worker.main`)가 http
전송을 고르는 경로와 같은 모양입니다. loopback(127.0.0.1)만 씁니다.

**참조 Fetch 서버를 먼저 실측했습니다** — `@modelcontextprotocol/server-fetch` 라는
npm 패키지는 존재하지 않습니다(2026-09-29 registry.npmjs.org 404 확인). 참조
"Fetch" 서버는 PyPI `mcp-server-fetch`(Python)이고, 그 `__init__.py`/`server.py`
는 `mcp.server.stdio.stdio_server()` 를 하드코딩해서 부릅니다 — HTTP/streamable
전송 옵션이 아예 없습니다(휠 내용 직접 확인). 그래서 spec 0003 2.3 의 "HTTP(Fetch)"
참조 서버 문구는 이번 실측으로 갱신이 필요합니다(구현자 보고의 "보고할 불일치").

대신 이 저장소의 최소 HTTP MCP 서버로 판정합니다 — 이미 `tools/mcp-servers/echo`
가 `--http` 플래그로 streamable HTTP 전송을 내므로(P2-1, `server.run(transport=
"streamable-http", ...)`), 새 디렉터리를 만들지 않고 이것을 그대로 씁니다.
"""

from __future__ import annotations

import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from aether_mcp.adapters.outbound.mcp_client.http import HttpMcpClient
from aether_mcp.domain.tools import McpServerRef

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]
ECHO_SERVER_PATH = REPO_ROOT / "tools" / "mcp-servers" / "echo" / "server.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        try:
            sock.connect(("127.0.0.1", port))
        except OSError:
            return False
        return True


@pytest.fixture()
def echo_http_process_url() -> Iterator[str]:
    """echo 서버를 **서브프로세스**로 `--http` 모드로 띄웁니다(127.0.0.1 고정 포트)."""
    port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            str(ECHO_SERVER_PATH),
            "--http",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
    )
    try:
        assert wait_until(lambda: _port_is_open(port), timeout=10.0), (
            "echo --http subprocess did not open its port in time"
        )
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        process.terminate()
        process.wait(timeout=5.0)


def test_discover_over_http_against_a_real_subprocess(echo_http_process_url: str) -> None:
    client = HttpMcpClient()
    server_ref = McpServerRef(name="echo", transport="http", url=echo_http_process_url)

    tools = client.discover(server_ref)

    assert {tool.name for tool in tools} == {"echo", "fail"}


def test_call_over_http_against_a_real_subprocess(echo_http_process_url: str) -> None:
    client = HttpMcpClient()
    server_ref = McpServerRef(name="echo", transport="http", url=echo_http_process_url)

    result = client.call(server_ref, "echo", {"text": "hello-http-subprocess"})

    assert result.is_error is False
    assert "hello-http-subprocess" in result.content
