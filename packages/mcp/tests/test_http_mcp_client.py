"""spec 0003 2.2, R-1: `HttpMcpClient` 가 저장소 안 echo 서버(2.3)를 streamable HTTP 로
띄운 것에 붙어 Discovery·호출을 만족하는지 확인합니다. 서버는 127.0.0.1 의 임시 포트로
띄웁니다 — 프로젝트 전역 `pytest-socket` 설정(`--allow-hosts=127.0.0.1,::1`)이 loopback
만 허용하므로 소켓 차단 아래에서도 통과합니다.
"""

from __future__ import annotations

import importlib.util
import socket
import threading
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
import uvicorn
from aether_mcp.adapters.outbound.mcp_client.http import HttpMcpClient
from aether_mcp.domain.tools import McpServerRef

from tests.support.waiting import wait_until

REPO_ROOT = Path(__file__).resolve().parents[3]
ECHO_SERVER_PATH = REPO_ROOT / "tools" / "mcp-servers" / "echo" / "server.py"


def _load_echo_server_module() -> ModuleType:
    """`tools/mcp-servers/echo/server.py` 는 어느 패키지에도 속하지 않으므로 경로로 직접
    로드합니다."""
    spec = importlib.util.spec_from_file_location("aether_echo_test_server", ECHO_SERVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


echo_server_module = _load_echo_server_module()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


@pytest.fixture()
def echo_http_url() -> Iterator[str]:
    port = _free_port()
    app = echo_server_module.server.streamable_http_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    uvicorn_server = uvicorn.Server(config)
    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()
    assert wait_until(lambda: uvicorn_server.started, timeout=5.0), "uvicorn server did not start"
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        uvicorn_server.should_exit = True
        thread.join(timeout=5.0)


def test_discover_returns_echo_and_fail_over_http(echo_http_url: str) -> None:
    client = HttpMcpClient()
    server_ref = McpServerRef(name="echo", transport="http", url=echo_http_url)

    tools = client.discover(server_ref)

    assert {tool.name for tool in tools} == {"echo", "fail"}


def test_call_echo_succeeds_over_http(echo_http_url: str) -> None:
    client = HttpMcpClient()
    server_ref = McpServerRef(name="echo", transport="http", url=echo_http_url)

    result = client.call(server_ref, "echo", {"text": "hello-http"})

    assert result.is_error is False
    assert "hello-http" in result.content


def test_call_fail_returns_error_result_over_http(echo_http_url: str) -> None:
    client = HttpMcpClient()
    server_ref = McpServerRef(name="echo", transport="http", url=echo_http_url)

    result = client.call(server_ref, "fail", {"reason": "boom"})

    assert result.is_error is True
