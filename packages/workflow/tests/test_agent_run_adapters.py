"""spec 0005 2.5 개정 3, 2.9 개정 2 (P4-2a B2): `PostgresAgentRunReader` 와 `RedisAgentRunLauncher`
-- 실제
PostgreSQL(`aether_data` 역할)과 실제 Redis.

증명하는 것: 리더가 worker 역할의 SELECT 만으로 `data.run_executions` 의 상태와
`control.agent_versions` 의 Version 을 읽는다(새 권한을 요구하지 않는다) / `version` 이 없으면 최대
version / 런처는 B1 의 스트림 계약 필드 이름을 그대로 싣는다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import psycopg
import pytest
from aether_runtime.domain.run import Message, RunState, RunStatus
from aether_workflow.adapters.outbound.db.agent_run_reader import PostgresAgentRunReader
from aether_workflow.adapters.outbound.redis.agent_run_launcher import RedisAgentRunLauncher
from aether_workflow.application.ports.outbound.agent_run_launcher import AgentRunLaunch
from redis import Redis

from tests.support.redis import stream_entries

pytestmark = pytest.mark.integration

_Factory = Callable[[], psycopg.Connection]
_STREAM = "aether:workflow:agent_runs:requested"


def _agent_with_versions(admin: _Factory, count: int) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """관리자 권한으로 Agent 와 Version 1..count 를 심는다(`control` 쓰기는 api 의 일이다)."""
    conn = admin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.agents (name, current_version) VALUES (%s, %s) RETURNING id",
                (f"reader-{uuid.uuid4()}", count),
            )
            row = cur.fetchone()
            assert row is not None
            agent_id: uuid.UUID = row[0]
            version_ids: list[uuid.UUID] = []
            for number in range(1, count + 1):
                cur.execute(
                    "INSERT INTO control.agent_versions (agent_id, version, definition) "
                    "VALUES (%s, %s, '{\"schema_version\": 1}') RETURNING id",
                    (agent_id, number),
                )
                version = cur.fetchone()
                assert version is not None
                version_ids.append(version[0])
        conn.commit()
    finally:
        conn.close()
    return agent_id, version_ids


def test_version_for_without_a_number_is_the_highest_version(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """`control.agents.current_version` 은 worker 가 읽을 수 없다. Version 은 append-only 이므로
    최대
    version 이 곧 현재 version 이다."""
    agent_id, version_ids = _agent_with_versions(admin_connection_factory, 3)
    reader = PostgresAgentRunReader(data_connection_factory)

    latest = reader.version_for(agent_id, None)
    pinned = reader.version_for(agent_id, 2)

    assert latest is not None and pinned is not None
    assert (latest.version, latest.agent_version_id) == (3, version_ids[2])
    assert (pinned.version, pinned.agent_version_id) == (2, version_ids[1])


def test_version_for_unknown_agent_or_number_is_none(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    agent_id, _ = _agent_with_versions(admin_connection_factory, 1)
    reader = PostgresAgentRunReader(data_connection_factory)

    assert reader.version_for(uuid.uuid4(), None) is None
    assert reader.version_for(uuid.uuid4(), 1) is None
    assert reader.version_for(agent_id, 7) is None


@pytest.mark.parametrize("status", list(RunStatus))
def test_status_reads_every_run_status_from_the_data_plane(
    status: RunStatus,
    admin_connection_factory: _Factory,
    data_connection_factory: _Factory,
) -> None:
    """자식의 상태 정본은 worker 가 소유하는 `data.run_executions` 다 -- `control.runs` 의 투영을
    기다리지 않는다. 일곱 값 전부 왕복한다."""
    _, version_ids = _agent_with_versions(admin_connection_factory, 1)
    run_id = uuid.uuid4()
    admin = admin_connection_factory()
    try:
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO control.runs (id, agent_version_id, input) VALUES (%s, %s, 'x')",
                (run_id, version_ids[0]),
            )
            cur.execute(
                "INSERT INTO data.run_executions (run_id, status) VALUES (%s, %s)",
                (run_id, status.value),
            )
        admin.commit()
    finally:
        admin.close()

    assert PostgresAgentRunReader(data_connection_factory).status(run_id) is status


def test_status_is_none_until_a_worker_has_picked_the_run_up(
    data_connection_factory: _Factory,
) -> None:
    assert PostgresAgentRunReader(data_connection_factory).status(uuid.uuid4()) is None


def test_launcher_writes_the_b1_contract_fields_verbatim(redis_client: Redis) -> None:
    """B1 의 스트림 계약: `agent_run_id`·`agent_version_id`·`input`·`traceparent` + B2 의
    `requested_by`. 필드 이름이 계약이다 -- api 쪽 소비자가 이 이름으로 읽는다."""
    launch = AgentRunLaunch(
        agent_run_id=uuid.uuid4(),
        agent_version_id=uuid.uuid4(),
        input='{"q":"안녕"}',
        requested_by=uuid.uuid4(),
        traceparent="00-" + "a" * 32 + "-" + "b" * 16 + "-01",
    )

    RedisAgentRunLauncher(redis_client).launch(launch)

    entries = stream_entries(redis_client, _STREAM)
    fields = [f for _, f in entries if f.get("agent_run_id") == str(launch.agent_run_id)]
    assert fields == [
        {
            "agent_run_id": str(launch.agent_run_id),
            "agent_version_id": str(launch.agent_version_id),
            "input": '{"q":"안녕"}',
            "requested_by": str(launch.requested_by),
            "traceparent": launch.traceparent,
        }
    ]


def test_launcher_sends_an_empty_string_for_a_missing_traceparent(redis_client: Redis) -> None:
    """`RedisRunNotifier` 와 같은 규칙: 없으면 필드를 빼지 않고 빈 문자열."""
    launch = AgentRunLaunch(
        agent_run_id=uuid.uuid4(),
        agent_version_id=uuid.uuid4(),
        input="",
        requested_by=uuid.uuid4(),
        traceparent=None,
    )

    RedisAgentRunLauncher(redis_client).launch(launch)

    entries = stream_entries(redis_client, _STREAM)
    (fields,) = [f for _, f in entries if f.get("agent_run_id") == str(launch.agent_run_id)]
    assert fields["traceparent"] == ""
    assert fields["input"] == ""


def _seed_state(admin: _Factory, messages: list[Message] | None) -> uuid.UUID:
    """`control.runs` 한 행과(`messages` 가 있으면) `data.run_states` 의 스냅숏 한 행을 심는다."""
    _, version_ids = _agent_with_versions(admin, 1)
    run_id = uuid.uuid4()
    conn = admin()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO control.runs (id, agent_version_id, input) VALUES (%s, %s, 'x')",
                (run_id, version_ids[0]),
            )
            if messages is not None:
                state = RunState(run_id=run_id, messages=messages, status=RunStatus.SUCCEEDED)
                cur.execute(
                    "INSERT INTO data.run_states (run_id, state) VALUES (%s, %s)",
                    (run_id, state.model_dump_json()),
                )
        conn.commit()
    finally:
        conn.close()
    return run_id


def test_last_assistant_text_is_the_final_assistant_message_of_the_snapshot(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    """spec 0005 2.4 개정 4 (4): 본문은 worker 가 소유하는 `data.run_states` 에서 읽는다(새 권한
    없이). 마지막 assistant 이후에 도구 메시지가 와도 그 assistant 본문이다. 한국어가
    그대로 온다."""
    run_id = _seed_state(
        admin_connection_factory,
        [
            Message.user("질문"),
            Message.assistant("첫 번째 답"),
            Message.tool(tool_call_id="t1", content="도구 결과"),
            Message.assistant("마지막 답변입니다"),
            Message.tool(tool_call_id="t2", content="뒤따른 도구 결과"),
        ],
    )

    reader = PostgresAgentRunReader(data_connection_factory)
    assert reader.last_assistant_text(run_id) == "마지막 답변입니다"


def test_last_assistant_text_is_none_without_an_assistant_message_or_a_snapshot(
    admin_connection_factory: _Factory, data_connection_factory: _Factory
) -> None:
    reader = PostgresAgentRunReader(data_connection_factory)
    only_user = _seed_state(admin_connection_factory, [Message.user("질문")])
    no_snapshot = _seed_state(admin_connection_factory, None)

    assert reader.last_assistant_text(only_user) is None
    assert reader.last_assistant_text(no_snapshot) is None
    assert reader.last_assistant_text(uuid.uuid4()) is None
