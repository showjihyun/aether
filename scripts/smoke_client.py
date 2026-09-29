"""spec 0002 2.11, 2.13 (P1-9): smoke 시나리오와 성능 측정용 HTTP 클라이언트.

표준 라이브러리만 씁니다(`urllib`) — 이 파일은 `docker compose exec -T api python -
<cmd> < scripts/smoke_client.py` 로 **stdin 을 통해** api 컨테이너 안에서 실행되므로
이미지에 무엇이 설치돼 있는지에 기대지 않습니다. `SMOKE_API_KEY` 환경변수로 인증하고
`http://localhost:8000`(같은 컨테이너 안의 api)를 부릅니다.

명령:
  scenario      -- 임시 agent 생성 -> run 요청 -> `succeeded` 폴링 -> `{run_id, trace_id,
                   status}` 한 줄 JSON.
  scenario_tool -- spec 0003 R-7, plan 0003 P2-5: Filesystem MCP Server 에 바인딩된
                   agent 를 만들고 `read_text_file` 을 허용(이 컨테이너 안의
                   `aether-api permissions allow` CLI 를 그대로 부릅니다 — 기본값
                   deny, D-14) 한 뒤 `FakeModelGateway.echo()` 의 `TOOL_CALL` 마커
                   (plan 0003 P2-5)로 실제 도구 호출을 일으켜 `succeeded` 까지
                   폴링합니다. `{run_id, agent_id, agent_version, status}` 한 줄 JSON.
  bench         -- 같은 agent 에 순차 200 회 run 요청, 처음 20 회(워밍업) 제외 180 회의
                   응답 지연으로 `{p50_ms, p95_ms, max_ms, n, warmup}` 한 줄 JSON.

`percentile`/`summarize_bench` 는 인자 없이 순수하고, `tests/scripts/test_smoke_client.py`
가 컨테이너 없이 이 둘만 검증합니다.
"""

from __future__ import annotations

import json
import math
import os
import random
import string
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

API_BASE_URL = "http://localhost:8000"
SCENARIO_POLL_INTERVAL_SECONDS = 1.0
SCENARIO_TIMEOUT_SECONDS = 60.0
BENCH_RUNS = 200
BENCH_WARMUP = 20
REQUEST_TIMEOUT_SECONDS = 10.0

# spec 0003 R-7, D-8: worker.Dockerfile 이 빌드 시점에 만들어 두는 고정 파일(smoke
# 전용) — Filesystem MCP Server(허용 디렉터리 `/srv/mcp-filesystem`)로 읽습니다.
SMOKE_TOOL_FIXTURE_PATH = "/srv/mcp-filesystem/smoke.txt"
MCP_FILESYSTEM_SERVER_NAME = "filesystem"
MCP_FILESYSTEM_TOOL_NAME = "read_text_file"


def percentile(values: list[float], p: float) -> float:
    """nearest-rank 백분위(spec 0002 2.13) — 보간하지 않습니다.

    `rank = ceil(p/100 * n)` 을 `[1, n]` 으로 clamp 한 뒤 정렬된 값의 그 순위를
    돌려줍니다. 빈 입력은 `ValueError`.
    """
    if not values:
        raise ValueError("percentile of an empty sequence is undefined")
    ordered = sorted(values)
    n = len(ordered)
    rank = math.ceil(p / 100 * n)
    rank = min(max(rank, 1), n)
    return ordered[rank - 1]


def summarize_bench(
    durations_ms: list[float], *, warmup: int = BENCH_WARMUP
) -> dict[str, float | int]:
    """워밍업을 제외한 뒤 p50/p95/max 를 계산합니다(spec 0002 2.13).

    워밍업 뒤 표본이 하나도 없으면 `ValueError`.
    """
    measured = durations_ms[warmup:]
    if not measured:
        raise ValueError("no samples remain after excluding warmup")
    return {
        "p50_ms": percentile(measured, 50),
        "p95_ms": percentile(measured, 95),
        "max_ms": percentile(measured, 100),
        "n": len(measured),
        "warmup": warmup,
    }


def _require_api_key() -> str:
    api_key = os.environ.get("SMOKE_API_KEY")
    if not api_key:
        raise RuntimeError("SMOKE_API_KEY is not set")
    return api_key


def _request(url: str, method: str, api_key: str, body: dict[str, Any] | None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        payload: Any = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected response body from {url}: {payload!r}")
    return payload


def _random_suffix(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=length))  # noqa: S311 -- 시험용 이름, 보안 무관


def create_smoke_agent(api_key: str) -> str:
    """최소 유효 `AgentDefinition`(spec 0002 2.3)으로 이름이 겹치지 않는 agent 를 만듭니다."""
    body = {
        "name": f"smoke-{_random_suffix()}",
        "definition": {
            "schema_version": 1,
            "system_prompt": "You are a smoke-test agent.",
            "tools": [],
        },
    }
    response = _request(f"{API_BASE_URL}/agents", "POST", api_key, body)
    return str(response["id"])


def request_run(api_key: str, agent_id: str) -> dict[str, Any]:
    return _request(f"{API_BASE_URL}/agents/{agent_id}/run", "POST", api_key, {"input": "smoke"})


def get_run(api_key: str, run_id: str) -> dict[str, Any]:
    return _request(f"{API_BASE_URL}/runs/{run_id}", "GET", api_key, None)


def wait_for_succeeded(api_key: str, run_id: str, timeout_seconds: float) -> dict[str, Any]:
    """`GET /runs/{id}` 를 `succeeded` 가 될 때까지 폴링합니다(spec 0002 2.11).

    스크립트이므로 폴링에 `time.sleep` 을 씁니다(implementer.md 금지 목록은 테스트에만
    해당 — 이 모듈은 `tests/**` 밖입니다).
    """
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = get_run(api_key, run_id)
        if last.get("status") == "succeeded":
            return last
        time.sleep(SCENARIO_POLL_INTERVAL_SECONDS)
    raise TimeoutError(
        f"run {run_id} did not reach succeeded within {timeout_seconds}s "
        f"(last status={last.get('status')!r})"
    )


_FAILED_TERMINAL_STATUSES = {"failed", "timed_out", "cancelled"}


def wait_for_terminal(api_key: str, run_id: str, timeout_seconds: float) -> dict[str, Any]:
    """spec 0003 R-7: `wait_for_succeeded` 와 같은 폴링이지만, 실패로 끝나는 상태를
    만나면 타임아웃까지 기다리지 않고 바로 `RuntimeError` 로 실패 사유를 드러냅니다
    — `TOOL_CALL` 시나리오가 배선 문제(예: 권한 미허용)로 죽었을 때 디버깅을
    빠르게 하기 위해서입니다."""
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = get_run(api_key, run_id)
        status_value = last.get("status")
        if status_value == "succeeded":
            return last
        if status_value in _FAILED_TERMINAL_STATUSES:
            raise RuntimeError(
                f"run {run_id} ended as {status_value!r} "
                f"(failure_reason={last.get('failure_reason')!r})"
            )
        time.sleep(SCENARIO_POLL_INTERVAL_SECONDS)
    raise TimeoutError(
        f"run {run_id} did not reach a terminal status within {timeout_seconds}s "
        f"(last status={last.get('status')!r})"
    )


def create_smoke_agent_with_filesystem_tool(api_key: str) -> tuple[str, int]:
    """spec 0003 R-7, 2.6: Filesystem MCP Server(`ref="filesystem"`, compose 의
    `AETHER_MCP_SERVERS` 기본값과 같은 이름, D-8)에 바인딩되고 `read_text_file` 을
    선언한 agent 를 만듭니다. `(agent_id, current_version)` 을 돌려줍니다 — 버전은
    `permissions allow` CLI(spec 2.14, D-14)가 필요로 합니다."""
    body = {
        "name": f"smoke-tool-{_random_suffix()}",
        "definition": {
            "schema_version": 1,
            "system_prompt": "You are a smoke-test agent that reads a file.",
            "tools": [MCP_FILESYSTEM_TOOL_NAME],
            "mcp_servers": [
                {"name": MCP_FILESYSTEM_SERVER_NAME, "transport": "stdio", "ref": "filesystem"}
            ],
        },
    }
    response = _request(f"{API_BASE_URL}/agents", "POST", api_key, body)
    return str(response["id"]), int(response["current_version"])


def allow_tool_permission(agent_id: str, version: int, server: str, tool: str) -> None:
    """spec 0003 2.14, D-14: 이 컨테이너 안의 🔒 `aether-api permissions allow` CLI 를
    그대로 부릅니다 — 기본값이 deny(허용 목록)이므로 이 호출 없이는 R-7 의 도구
    호출이 반드시 거부됩니다(plan 0003 리뷰 F-1)."""
    result = subprocess.run(
        [
            "aether-api",
            "permissions",
            "allow",
            "--agent-id",
            agent_id,
            "--version",
            str(version),
            "--server",
            server,
            "--tool",
            tool,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"aether-api permissions allow failed (exit={result.returncode}): {result.stderr}"
        )


def request_tool_run(api_key: str, agent_id: str, fixture_path: str) -> dict[str, Any]:
    """spec 0003 R-7, plan 0003 P2-5: `FakeModelGateway.echo()` 의 `TOOL_CALL` 마커로
    `read_text_file` 호출을 결정적으로 일으킵니다(compose 는 실제 모델을 부르지
    않음, `AETHER_MODEL_ADAPTER=fake`)."""
    tool_input = f'TOOL_CALL {MCP_FILESYSTEM_TOOL_NAME} {{"path": "{fixture_path}"}}'
    return _request(f"{API_BASE_URL}/agents/{agent_id}/run", "POST", api_key, {"input": tool_input})


def scenario_tool() -> dict[str, Any]:
    """spec 0003 R-7: agent 생성 -> allow 선언 -> `TOOL_CALL` 로 실제 Filesystem 도구
    호출 -> `succeeded` 확인까지 한 번에 합니다."""
    api_key = _require_api_key()
    agent_id, version = create_smoke_agent_with_filesystem_tool(api_key)
    allow_tool_permission(agent_id, version, MCP_FILESYSTEM_SERVER_NAME, MCP_FILESYSTEM_TOOL_NAME)
    run = request_tool_run(api_key, agent_id, SMOKE_TOOL_FIXTURE_PATH)
    result = wait_for_terminal(api_key, str(run["run_id"]), SCENARIO_TIMEOUT_SECONDS)
    return {
        "run_id": result["run_id"],
        "agent_id": agent_id,
        "agent_version": version,
        "status": result["status"],
    }


def scenario() -> dict[str, Any]:
    api_key = _require_api_key()
    agent_id = create_smoke_agent(api_key)
    run = request_run(api_key, agent_id)
    result = wait_for_succeeded(api_key, str(run["run_id"]), SCENARIO_TIMEOUT_SECONDS)
    return {
        "run_id": result["run_id"],
        "trace_id": result.get("trace_id"),
        "status": result["status"],
    }


def bench() -> dict[str, float | int]:
    api_key = _require_api_key()
    agent_id = create_smoke_agent(api_key)
    durations_ms: list[float] = []
    for _ in range(BENCH_RUNS):
        started = time.perf_counter()
        request_run(api_key, agent_id)
        durations_ms.append((time.perf_counter() - started) * 1000)
    return summarize_bench(durations_ms)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write("usage: smoke_client.py <scenario|scenario_tool|bench>\n")
        return 2
    command = argv[1]
    try:
        if command == "scenario":
            result: dict[str, Any] = scenario()
        elif command == "scenario_tool":
            result = scenario_tool()
        elif command == "bench":
            result = bench()
        else:
            sys.stderr.write(f"unknown command: {command}\n")
            return 2
    except (TimeoutError, RuntimeError, urllib.error.URLError) as exc:
        sys.stderr.write(f"smoke_client error: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
