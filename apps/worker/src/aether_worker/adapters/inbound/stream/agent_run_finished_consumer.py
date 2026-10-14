"""spec 0005 2.5 개정 3 (P4-2a B2): `AgentRunFinishedConsumer` - 파킹된 Workflow Run 을 깨우는
**빠른
경로**. `aether:runs:status` 를 Workflow 전용 consumer group `aether-workflow` 로 읽습니다.

`run.finished` 이벤트가 아닌 종결 **상태 통지**를 읽는 이유는 spec 2.5 개정 3 에 있습니다 - 이벤트는
run 마다 키가 다른 스트림이라 group 으로 받을 수 없고, 거기서 읽으려면 "지금 파킹된 Run 목록" 을
먼저
DB 에서 구해야 해서 빠른 경로가 스위퍼와 같은 장치가 됩니다. **Agent Run 의 api 쪽 투영 group
(`aether-api`)을 건드리지 않습니다** - 같은 스트림을 다른 group 이름으로 읽을 뿐이라 각 group 이
같은 메시지를 따로 한 번씩 받습니다.

읽는 순서는 자기 PEL 먼저(`XREADGROUP … 0`) -> `XREADGROUP ">"` 입니다. `XAUTOCLAIM` 은 없습니다 -
이 신호는 유실돼도 스위퍼가 구하므로 다른 consumer 가 두고 간 메시지를 적극적으로 가로챌 이유가
없습니다.

- 종결 상태(`succeeded`·`failed`·`cancelled`·`timed_out`)면 `ResumeParkedWorkflows.
  on_agent_run_finished` 를 부르고 ack. 대부분의 메시지는 평범한 Agent Run 이라 아무 Workflow 도
  기다리지 않고, 그 경우 유스케이스는 아무 일도 하지 않습니다.
- 미종결 상태·파싱 실패(필드 누락·형식 오류)는 독약이 아니라 **관심 밖** 이므로 WARNING 없이/있이
  즉시 ack 합니다(파싱 실패만 WARNING).
- 유스케이스가 예외를 내면(DB·Redis 장애) **ack 하지 않고 ERROR 로그를 남긴 뒤 계속 돕니다.**
스레드가
  죽으면 그 뒤의 신호가 전부 소리 없이 사라집니다(`2026-10-11-001`). ack 되지 않은 메시지는 PEL 에
  남아
  재시작 때 다시 시도되고, 그 전에는 스위퍼가 구합니다.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from threading import Event
from typing import Any
from uuid import UUID

from aether_runtime.domain.run import RunStatus, is_terminal
from redis import Redis

from aether_worker.application.ports.inbound.resume_parked_workflows import ResumeParkedWorkflows

logger = logging.getLogger(__name__)

_StreamEntry = tuple[str, Mapping[str, str]]


class AgentRunFinishedConsumer:
    def __init__(
        self,
        client: Redis,
        *,
        stream: str,
        group: str,
        consumer: str,
        resume: ResumeParkedWorkflows,
        block_ms: int = 1000,
    ) -> None:
        self._client = client
        self._stream = stream
        self._group = group
        self._consumer = consumer
        self._resume = resume
        self._block_ms = block_ms

    def run_until(self, stop: Event) -> None:
        """`stop` 이 set 될 때까지 자기 PEL -> `XREADGROUP(">")` 순서로 돕니다."""
        self._drain_own_pel()
        while not stop.is_set():
            entry = self._read_one()
            if entry is not None:
                self._handle(*entry)

    def _drain_own_pel(self) -> None:
        """자기 PEL 을 한 번 훑습니다. 실패해 ack 하지 못한 메시지가 있으면 `0` 에서 다시 같은
        메시지를
        돌려주므로, 처리 여부와 무관하게 **한 메시지는 한 번만** 시도하고 id 를 넘겨 앞으로
        나아갑니다."""
        last_id = "0"
        while True:
            response: Any = self._client.xreadgroup(
                groupname=self._group,
                consumername=self._consumer,
                streams={self._stream: last_id},
                count=1,
            )
            entries = _entries(response)
            if not entries:
                return
            message_id, fields = entries[0]
            last_id = message_id
            self._handle(message_id, fields)

    def _read_one(self) -> _StreamEntry | None:
        response: Any = self._client.xreadgroup(
            groupname=self._group,
            consumername=self._consumer,
            streams={self._stream: ">"},
            count=1,
            block=self._block_ms,
        )
        entries = _entries(response)
        return entries[0] if entries else None

    def _handle(self, message_id: str, fields: Mapping[str, str]) -> None:
        parsed = _parse(fields)
        if parsed is None:
            logger.warning(
                "worker.agent_run_finished_consumer.malformed_message",
                extra={"message_id": message_id, "fields": dict(fields)},
            )
            self._client.xack(self._stream, self._group, message_id)
            return
        run_id, terminal = parsed
        if terminal:
            try:
                self._resume.on_agent_run_finished(run_id)
            except Exception:  # noqa: BLE001 - 스레드는 죽지 않는다, ack 하지 않고 스위퍼에 맡긴다
                logger.exception(
                    "worker.agent_run_finished_consumer.resume_failed",
                    extra={"message_id": message_id, "run_id": str(run_id)},
                )
                return
        self._client.xack(self._stream, self._group, message_id)


def _parse(fields: Mapping[str, str]) -> tuple[UUID, bool] | None:
    """`(run_id, 종결 여부)`. 읽을 수 없으면 `None`."""
    try:
        run_id = UUID(fields["run_id"])
        status = RunStatus(fields["status"])
    except (KeyError, ValueError):
        return None
    return run_id, is_terminal(status)


def _entries(response: Any) -> list[_StreamEntry]:
    if not response:
        return []
    _stream_name, messages = response[0]
    return list(messages)
