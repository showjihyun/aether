"""spec 0005 2.9 개정 2, 2.10, R-6 (P4-2a A): **사슬 하나로** api → 요청 스트림 → 실행기 →
상태 스트림 → 투영 → `GET`.

PR B2 가 `AGENT` 노드의 사슬을 더합니다(아래 `test_agent_node_*`): api 로 `START → AGENT → END` 를
만들어 실행하면 실행기가 자식 Run 의 선언을 요청하고(`aether:workflow:agent_runs:requested`), api 의
선언 소비자가 `control.runs` 에 만들고, worker 의 Agent Run 경로가 실행하고, 종결 통지가 파킹된
Workflow 를 깨워 `succeeded` 에 닿는다 -- 전부 **프로덕션 조립 그대로**(api `lifespan`, worker
`serve()`)이고 모델만 fake 입니다. 중간에 `waiting_run` 과 `waiting_run_id` 가 `GET` 에 보이는 것이
R-13 의 절반입니다.

이 파일이 있는 이유는 **계약이 두 번 구현되기 때문**입니다. `aether:workflow_runs:status` 의
필드를 worker 쪽(`RedisWorkflowStatusNotifier`)과 api 쪽(`WorkflowRunStatusConsumer`)이 서로를
import 하지 않고 각자 만듭니다(AR-7). 그래서 한쪽이 `workflow_run_id` 를 `run_id` 로 쓰거나
시각 형식을 달리 써도 **양쪽 테스트는 전부 통과합니다** — api 쪽 통합 테스트는 스트림 메시지를
손으로 쓰고, worker 쪽은 자기 notifier 의 dict 를 봅니다. 두 구현이 실제로 맞물리는지는 이
사슬만이 판정합니다.

`test_build_production_handler_wires_workflow.py` 는 요청 스트림의 worker 쪽 절반(손으로 쓴
메시지 → `serve()`)을 봅니다. 여기서는 그 메시지를 **api 가** 쓰고, 끝난 뒤의 상태를 **api 가**
투영하는 것까지 봅니다.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from aether_api.adapters.inbound.stream.status_consumer import ensure_group
from aether_api.adapters.inbound.stream.workflow_run_status_consumer import (
    WorkflowRunStatusConsumer,
)
from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore
from aether_api.adapters.outbound.db.workflow_run_declaration_store import (
    PostgresWorkflowRunDeclarationStore,
)
from aether_api.application.usecases.apply_workflow_run_status import (
    ApplyWorkflowRunStatusUseCase,
)
from aether_api.application.usecases.issue_api_key import IssueApiKeyUseCase
from aether_api.main import create_app
from aether_api.settings import Settings as ApiSettings
from aether_worker.application.ports.inbound.handle_run_requested import (
    HandleOutcome,
    RequestedMessage,
)
from aether_worker.main import _build_production_handler, serve
from aether_worker.settings import Settings as WorkerSettings
from fastapi.testclient import TestClient
from redis import Redis

from tests.support.pg import DATA_PASSWORD, DATA_ROLE
from tests.support.redis import stream_entries
from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_STATUS = "aether:workflow_runs:status"
_API_GROUP = "aether-api"
_JOIN_TIMEOUT = 5.0


def _node(node_id: str, kind: str) -> dict[str, Any]:
    return {"id": node_id, "kind": kind, "max_iterations": None}


def test_a_run_started_through_the_api_is_executed_and_projected_back(
    control_database_url: str,
    db_host_port: tuple[str, int],
    redis_url: str,
    redis_client: Redis,
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    host, port = db_host_port
    api_settings = ApiSettings(database_url=control_database_url, redis_url=redis_url)
    worker_settings = WorkerSettings(
        database_url=f"postgresql+psycopg://{DATA_ROLE}:{DATA_PASSWORD}@{host}:{port}/aether",
        worker_consumer=f"test-chain-{uuid4()}",
        worker_heartbeat_seconds=1,
    )
    issued = IssueApiKeyUseCase(PostgresApiKeyStore(control_connection_factory))(
        f"test-workflow-chain-{uuid4()}"
    )
    headers = {"Authorization": f"Bearer {issued.raw_key}"}
    client = TestClient(create_app(api_settings))

    # api 쪽 투영 소비자와 worker 를 띄웁니다 — 둘 다 **프로덕션 조립**입니다.
    ensure_group(redis_client, _STATUS, _API_GROUP)
    projection = WorkflowRunStatusConsumer(
        redis_client,
        ApplyWorkflowRunStatusUseCase(
            PostgresWorkflowRunDeclarationStore(control_connection_factory)
        ),
        stream=_STATUS,
        group=_API_GROUP,
    )
    stop = threading.Event()
    ready = threading.Event()
    projection_thread = threading.Thread(target=projection.run_until, args=(stop,), daemon=True)
    worker_thread = threading.Thread(
        target=lambda: serve(
            worker_settings, stop=stop, make_client=lambda: redis_client, on_ready=ready.set
        ),
        daemon=True,
    )
    projection_thread.start()
    worker_thread.start()
    try:
        assert ready.wait(_JOIN_TIMEOUT), "worker 가 준비되지 않았습니다"

        created = client.post(
            "/workflows",
            json={
                "name": f"chain-{uuid4()}",
                "nodes": [_node("s", "START"), _node("e", "END")],
                "edges": [{"source": "s", "target": "e", "label": None}],
            },
            headers=headers,
        )
        assert created.status_code == 201, created.text
        started = client.post(
            f"/workflows/{created.json()['id']}/runs", json={"input": {"q": "hi"}}, headers=headers
        )
        assert started.status_code == 202, started.text
        workflow_run_id = started.json()["workflow_run_id"]

        def _detail() -> dict[str, Any]:
            response = client.get(f"/workflow-runs/{workflow_run_id}", headers=headers)
            assert response.status_code == 200, response.text
            body: dict[str, Any] = response.json()
            return body

        assert wait_until(lambda: _detail()["status"] == "succeeded", timeout=20.0), (
            f"사슬이 끊겼습니다 — 마지막으로 본 투영: {_detail()}"
        )
        final = _detail()
        assert final["current_node_id"] == "e", final
        assert final["started_at"] is not None, final
        assert final["finished_at"] is not None, final
        assert final["failure_reason"] is None, final
        assert final["waiting_run_id"] is None, final
    finally:
        stop.set()
        worker_thread.join(_JOIN_TIMEOUT * 2)
        projection_thread.join(_JOIN_TIMEOUT * 2)


# --- B2: AGENT 노드 사슬 ----------------------------------------------------------------

_WORKFLOW_REQUESTED = "aether:workflow_runs:requested"
_AGENT_RUN_REQUESTED = "aether:workflow:agent_runs:requested"
_CHAIN_TIMEOUT = 30.0
_DEFAULT_OUTPUT_LIMIT: int = WorkerSettings.model_fields["workflow_node_output_max_bytes"].default


@dataclass
class _Stack:
    client: TestClient
    headers: dict[str, str]
    key_id: UUID
    redis: Redis
    admin: Callable[[], psycopg.Connection]
    release_children: threading.Event
    agent_id: str

    def start_workflow(self) -> tuple[str, UUID]:
        """`START -> AGENT -> END` 를 만들고 실행해 `(workflow_run_id, workflow_version_id)` 를
        돌려준다."""
        created = self.client.post(
            "/workflows",
            json={
                "name": f"chain-agent-{uuid4()}",
                "nodes": [
                    _node("s", "START"),
                    {**_node("a", "AGENT"), "agent_id": self.agent_id, "agent_version": None},
                    _node("e", "END"),
                ],
                "edges": [
                    {"source": "s", "target": "a", "label": None},
                    {"source": "a", "target": "e", "label": None},
                ],
            },
            headers=self.headers,
        )
        assert created.status_code == 201, created.text
        started = self.client.post(
            f"/workflows/{created.json()['id']}/runs",
            json={"input": {"q": "hi"}},
            headers=self.headers,
        )
        assert started.status_code == 202, started.text
        run_id: str = started.json()["workflow_run_id"]
        (version_id,) = {
            UUID(f["workflow_version_id"])
            for _, f in stream_entries(self.redis, _WORKFLOW_REQUESTED)
            if f["workflow_run_id"] == run_id
        }
        return run_id, version_id

    def define_branching(self) -> str:
        """`START -> AGENT -> CONDITION -> END-true / END-false`. 조건은 **노드의 출력**을 가리킨다:
        `nodes.a.text` 가 `"yes"` 를 포함하는가. 모델은 echo fake 라 자식 Run 의 답은 입력의 직렬화
        (`{"q":"..."}`)이고 결정적이다."""
        created = self.client.post(
            "/workflows",
            json={
                "name": f"chain-branch-{uuid4()}",
                "nodes": [
                    _node("s", "START"),
                    {**_node("a", "AGENT"), "agent_id": self.agent_id, "agent_version": None},
                    {
                        **_node("c", "CONDITION"),
                        "condition_path": "nodes.a.text",
                        "condition_operator": "contains",
                        "condition_value": "yes",
                    },
                    _node("end_true", "END"),
                    _node("end_false", "END"),
                ],
                "edges": [
                    {"source": "s", "target": "a", "label": None},
                    {"source": "a", "target": "c", "label": None},
                    {"source": "c", "target": "end_true", "label": "true"},
                    {"source": "c", "target": "end_false", "label": "false"},
                ],
            },
            headers=self.headers,
        )
        assert created.status_code == 201, created.text
        workflow_id: str = created.json()["id"]
        return workflow_id

    def run_to_the_end(self, workflow_id: str, input: dict[str, Any]) -> str:
        """실행을 시작해 `succeeded` 까지 기다리고 `workflow_run_id` 를 돌려준다."""
        started = self.client.post(
            f"/workflows/{workflow_id}/runs", json={"input": input}, headers=self.headers
        )
        assert started.status_code == 202, started.text
        run_id: str = started.json()["workflow_run_id"]
        assert wait_until(
            lambda: self.detail(run_id)["status"] == "succeeded", timeout=_CHAIN_TIMEOUT
        ), f"사슬이 끊겼습니다 -- 마지막으로 본 투영: {self.detail(run_id)}"
        return run_id

    def visited(self, run_id: str) -> list[str]:
        return [
            row[0]
            for row in self.query(
                "SELECT node_id FROM data.workflow_node_executions"
                " WHERE workflow_run_id = %s ORDER BY started_at, node_id",
                run_id,
            )
        ]

    def outputs(self, run_id: str) -> dict[str, tuple[Any, bool]]:
        return {
            row[0]: (row[1], row[2])
            for row in self.query(
                "SELECT node_id, output, output_truncated FROM data.workflow_node_executions"
                " WHERE workflow_run_id = %s",
                run_id,
            )
        }

    def detail(self, run_id: str) -> dict[str, Any]:
        response = self.client.get(f"/workflow-runs/{run_id}", headers=self.headers)
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    def query(self, sql: str, *params: object) -> list[tuple[Any, ...]]:
        conn = self.admin()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        finally:
            conn.close()


@contextmanager
def _stack(
    control_database_url: str,
    db_host_port: tuple[str, int],
    redis_url: str,
    redis_client: Redis,
    control_connection_factory: Callable[[], psycopg.Connection],
    admin_connection_factory: Callable[[], psycopg.Connection],
    output_max_bytes: int | None = None,
) -> Iterator[_Stack]:
    host, port = db_host_port
    api_settings = ApiSettings(database_url=control_database_url, redis_url=redis_url)
    worker_settings = WorkerSettings(
        database_url=f"postgresql+psycopg://{DATA_ROLE}:{DATA_PASSWORD}@{host}:{port}/aether",
        worker_consumer=f"test-chain-agent-{uuid4()}",
        worker_heartbeat_seconds=1,
        workflow_sweep_interval_seconds=1.0,
        workflow_node_output_max_bytes=(
            output_max_bytes if output_max_bytes is not None else _DEFAULT_OUTPUT_LIMIT
        ),
    )
    issued = IssueApiKeyUseCase(PostgresApiKeyStore(control_connection_factory))(
        f"test-workflow-chain-agent-{uuid4()}"
    )
    # Agent Run 은 프로덕션 핸들러가 그대로 실행하되, 테스트가 풀어 줄 때까지 **집지 않게** 문을
    # 닫는다 --
    # 그래야 `waiting_run` 이 관측되는 창이 확정적이다(경쟁 없이 R-13 의 절반을 본다).
    gate = threading.Event()
    inner = _build_production_handler(worker_settings, redis_client)

    def gated(message: RequestedMessage) -> HandleOutcome:
        assert gate.wait(_CHAIN_TIMEOUT), "테스트가 자식 Run 을 풀어 주지 않았습니다"
        return inner(message)

    stop = threading.Event()
    ready = threading.Event()
    worker_thread = threading.Thread(
        target=lambda: serve(
            worker_settings,
            stop=stop,
            make_client=lambda: redis_client,
            on_ready=ready.set,
            handler=gated,
        ),
        daemon=True,
    )
    worker_thread.start()
    try:
        assert ready.wait(_JOIN_TIMEOUT), "worker 가 준비되지 않았습니다"
        with TestClient(create_app(api_settings)) as client:  # lifespan = 프로덕션 소비자 넷
            headers = {"Authorization": f"Bearer {issued.raw_key}"}
            agent = client.post(
                "/agents",
                json={
                    "name": f"chain-agent-{uuid4()}",
                    "definition": {"schema_version": 1, "system_prompt": "You are a helper."},
                },
                headers=headers,
            )
            assert agent.status_code == 201, agent.text
            yield _Stack(
                client=client,
                headers=headers,
                key_id=issued.key.id,
                redis=redis_client,
                admin=admin_connection_factory,
                release_children=gate,
                agent_id=agent.json()["id"],
            )
    finally:
        gate.set()
        stop.set()
        worker_thread.join(_JOIN_TIMEOUT * 2)


def test_agent_node_workflow_parks_then_succeeds_through_the_real_assembly(
    control_database_url: str,
    db_host_port: tuple[str, int],
    redis_url: str,
    redis_client: Redis,
    control_connection_factory: Callable[[], psycopg.Connection],
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """R-13(절반)·R-6: `GET` 이 `waiting_run` 과 기다리는 자식 Run 의 id 를 보여 주고(자식 Run 이
    돌기 전에), 풀어 주면 자식이 끝나 통지가 Workflow 를 깨워 `succeeded` 가 된다. 자식 Run 은
    Workflow
    를 시작한 주체의 것으로 조회된다(`GET /runs/{id}` 가 200 -- 요청자를 비웠다면 500)."""
    with _stack(
        control_database_url,
        db_host_port,
        redis_url,
        redis_client,
        control_connection_factory,
        admin_connection_factory,
    ) as stack:
        run_id, _ = stack.start_workflow()

        assert wait_until(
            lambda: stack.detail(run_id)["status"] == "waiting_run", timeout=_CHAIN_TIMEOUT
        ), f"파킹이 투영되지 않았습니다 -- 마지막으로 본 투영: {stack.detail(run_id)}"
        parked = stack.detail(run_id)
        child = parked["waiting_run_id"]
        assert child is not None, parked
        assert parked["current_node_id"] == "a", parked
        assert stack.query(
            "SELECT agent_run_id FROM data.workflow_node_executions"
            " WHERE workflow_run_id = %s AND node_id = 'a'",
            run_id,
        ) == [(UUID(child),)], "투영이 보여 주는 대기 대상은 실행기가 영속한 자식 id 다"
        assert stack.query(
            "SELECT lease_owner, lease_until FROM data.workflow_run_executions"
            " WHERE workflow_run_id = %s",
            run_id,
        ) == [(None, None)], "대기 중에는 lease 를 쥐지 않는다(R-7)"

        child_view = stack.client.get(f"/runs/{child}", headers=stack.headers)
        assert child_view.status_code == 200, child_view.text
        assert child_view.json()["requested_by"] == str(stack.key_id)

        stack.release_children.set()
        assert wait_until(
            lambda: stack.detail(run_id)["status"] == "succeeded", timeout=_CHAIN_TIMEOUT
        ), f"사슬이 끊겼습니다 -- 마지막으로 본 투영: {stack.detail(run_id)}"
        final = stack.detail(run_id)
        assert final["waiting_run_id"] is None, final
        assert final["current_node_id"] == "e", final
        assert final["failure_reason"] is None, final
        assert wait_until(
            lambda: (
                stack.client.get(f"/runs/{child}", headers=stack.headers).json()["status"]
                == "succeeded"
            ),
            timeout=_CHAIN_TIMEOUT,
        )
        assert stack.query(
            "SELECT node_id, status::text FROM data.workflow_node_executions"
            " WHERE workflow_run_id = %s ORDER BY started_at, node_id",
            run_id,
        ) == [("s", "succeeded"), ("a", "succeeded"), ("e", "succeeded")]


def test_duplicate_requests_in_the_real_assembly_create_one_child_run(
    control_database_url: str,
    db_host_port: tuple[str, int],
    redis_url: str,
    redis_client: Redis,
    control_connection_factory: Callable[[], psycopg.Connection],
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """R-8: 같은 요청 메시지가 (파킹 중에) 두 번 더 와도 자식 Run 은 **1건**, 노드 실행 기록은
    노드당 1행이다 -- 실제 worker 의 소비자가 받아 실제 실행기가 처리한다."""
    with _stack(
        control_database_url,
        db_host_port,
        redis_url,
        redis_client,
        control_connection_factory,
        admin_connection_factory,
    ) as stack:
        run_id, version_id = stack.start_workflow()
        assert wait_until(
            lambda: stack.detail(run_id)["status"] == "waiting_run", timeout=_CHAIN_TIMEOUT
        )
        for _ in range(2):
            redis_client.xadd(
                _WORKFLOW_REQUESTED,
                {
                    "workflow_run_id": run_id,
                    "workflow_version_id": str(version_id),
                    "traceparent": "",
                },
            )
        assert wait_until(
            lambda: (
                redis_client.xpending(_WORKFLOW_REQUESTED, "aether-worker")["pending"] == 0
                and redis_client.xinfo_groups(_WORKFLOW_REQUESTED)[0]["lag"] == 0
            ),
            timeout=_CHAIN_TIMEOUT,
        ), "중복 요청이 처리(ack)되지 않았습니다"

        stack.release_children.set()
        assert wait_until(
            lambda: stack.detail(run_id)["status"] == "succeeded", timeout=_CHAIN_TIMEOUT
        )

        assert len(redis_client.xrange(_AGENT_RUN_REQUESTED, min="-", max="+") or []) == 1
        assert stack.query(
            "SELECT count(*) FROM control.runs r JOIN data.workflow_node_executions n"
            " ON n.agent_run_id = r.id WHERE n.workflow_run_id = %s",
            run_id,
        ) == [(1,)]
        assert stack.query(
            "SELECT node_id, count(*) FROM data.workflow_node_executions"
            " WHERE workflow_run_id = %s GROUP BY node_id ORDER BY node_id",
            run_id,
        ) == [("a", 1), ("e", 1), ("s", 1)]


# --- P4-2b: 노드 출력과 CONDITION ---------------------------------------------------------


def test_the_same_workflow_takes_different_paths_for_different_inputs_through_the_real_assembly(
    control_database_url: str,
    db_host_port: tuple[str, int],
    redis_url: str,
    redis_client: Redis,
    control_connection_factory: Callable[[], psycopg.Connection],
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """R-5: 같은 Workflow 를 두 입력으로 돌리면 서로 다른 경로를 타고 지난 노드 목록이 다르다.
    api -> 요청 스트림 -> 실행기 -> 자식 Agent Run(echo fake 모델) -> `data.run_states` 의 마지막
    assistant 본문 -> 노드 출력 -> `CONDITION` -> 분기 -> 투영 -> `GET`, 프로덕션 조립 그대로.
    분기는 **노드 출력**(`nodes.a.text`)으로 갈린다 -- 입력으로 갈리지 않는다."""
    with _stack(
        control_database_url,
        db_host_port,
        redis_url,
        redis_client,
        control_connection_factory,
        admin_connection_factory,
    ) as stack:
        stack.release_children.set()
        workflow_id = stack.define_branching()

        yes_run = stack.run_to_the_end(workflow_id, {"q": "yes please"})
        no_run = stack.run_to_the_end(workflow_id, {"q": "no thanks"})

        assert stack.visited(yes_run) == ["s", "a", "c", "end_true"]
        assert stack.visited(no_run) == ["s", "a", "c", "end_false"]
        assert stack.visited(yes_run) != stack.visited(no_run)
        assert stack.detail(yes_run)["current_node_id"] == "end_true"
        assert stack.detail(no_run)["current_node_id"] == "end_false"
        assert stack.detail(yes_run)["failure_reason"] is None

        # 출력: AGENT 만 갖는다. 본문은 echo 모델이 돌려준 자식 입력의 직렬화다.
        yes_outputs = stack.outputs(yes_run)
        assert yes_outputs["a"] == ({"text": '{"q":"yes please"}', "status": "succeeded"}, False)
        for node_id in ("s", "c", "end_true"):
            assert yes_outputs[node_id] == (None, False), node_id
        assert stack.outputs(no_run)["a"][0] == {
            "text": '{"q":"no thanks"}',
            "status": "succeeded",
        }


def test_a_reply_over_the_limit_is_stored_truncated_with_the_flag_through_the_real_assembly(
    control_database_url: str,
    db_host_port: tuple[str, int],
    redis_url: str,
    redis_client: Redis,
    control_connection_factory: Callable[[], psycopg.Connection],
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """D-8: 상한(`AETHER_WORKFLOW_NODE_OUTPUT_MAX_BYTES` -> worker `Settings` -> 실행기)을 넘는
    실제 응답은 잘려 저장되고 `output_truncated` 가 함께 참이다. 한국어 경계가 UTF-8 안전하다
    (`jsonb` 가 거부하지 않고 되읽은 본문이 입력의 접두사다). 잘렸어도 분기는 간다."""
    limit = 256
    with _stack(
        control_database_url,
        db_host_port,
        redis_url,
        redis_client,
        control_connection_factory,
        admin_connection_factory,
        output_max_bytes=limit,
    ) as stack:
        stack.release_children.set()
        workflow_id = stack.define_branching()
        question = "yes " + "안녕하세요 " * 200

        run_id = stack.run_to_the_end(workflow_id, {"q": question})

        value, truncated = stack.outputs(run_id)["a"]
        assert truncated is True
        assert value["status"] == "succeeded"
        assert '{"q":"yes 안녕하세요' in value["text"]
        assert len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()) <= limit
        assert ('{"q":"' + question + '"}').startswith(value["text"])
        # 잘린 본문에서도 앞부분의 "yes" 가 남아 `true` 분기로 갔다.
        assert stack.detail(run_id)["current_node_id"] == "end_true"
        assert stack.outputs(run_id)["s"] == (None, False)


def test_a_reply_over_the_default_8_kib_limit_is_stored_truncated(
    control_database_url: str,
    db_host_port: tuple[str, int],
    redis_url: str,
    redis_client: Redis,
    control_connection_factory: Callable[[], psycopg.Connection],
    admin_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    """D-8: **기본 상한(8192)** 을 넘는 실제 응답 1건. echo fake 모델이 15 000 바이트 남짓한 입력을
    그대로 돌려준다 -- 자식 Run 의 마지막 assistant 본문이 8 KiB 를 넘고, 저장된 출력은 상한
    이하이며 잘렸다고 적힌다."""
    with _stack(
        control_database_url,
        db_host_port,
        redis_url,
        redis_client,
        control_connection_factory,
        admin_connection_factory,
    ) as stack:
        stack.release_children.set()
        workflow_id = stack.define_branching()

        run_id = stack.run_to_the_end(workflow_id, {"q": "yes " + "가" * 5000})

        value, truncated = stack.outputs(run_id)["a"]
        assert truncated is True
        size = len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())
        assert 8000 < size <= 8192, size
