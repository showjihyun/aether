"""Redis Streams 소비자.

스트림을 읽어 시스템을 움직이는 쪽이므로 inbound 어댑터입니다(architecture.md 3.1).
Phase 0 에서는 consumer group 을 만들고 블록 읽기로 대기만 합니다 — 메시지가 와도
로그만 하고 처리·ack 하지 않습니다(ack 은 Phase 1). `application`·`main` 을 import
하지 않습니다(AR-11, AR-12).
"""

from __future__ import annotations

import logging
from threading import Event
from typing import Any

from redis import Redis
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)

_BUSYGROUP = "BUSYGROUP"


def ensure_group(client: Redis, stream: str, group: str) -> None:
    """`stream` 에 `group` consumer group 을 만듭니다(`XGROUP CREATE ... MKSTREAM`).

    스트림이 없으면 `mkstream=True` 가 빈 스트림을 함께 만듭니다. group 이 이미 있으면
    Redis 가 `BUSYGROUP` 오류를 내는데, 그것은 원하는 상태(멱등)이므로 무시합니다.
    """
    try:
        client.xgroup_create(name=stream, groupname=group, id="0", mkstream=True)
    except ResponseError as exc:
        if _BUSYGROUP not in str(exc):
            raise


def consume_until(
    client: Redis,
    stream: str,
    group: str,
    consumer: str,
    stop: Event,
    block_ms: int = 1000,
) -> None:
    """`stop` 이 set 될 때까지 `XREADGROUP` 으로 블록 읽기만 합니다.

    받은 메시지는 로그만 남기고 처리하지 않으며 **ack 하지 않습니다** — 메시지는
    consumer group 의 pending entries list 에 남아 Phase 1 의 처리·ack·재시도를
    기다립니다(spec 2.3: 메시지는 선언이 아니라 통지이고, 내구적 선언은
    `control.runs` 에 있습니다).

    `block_ms` 는 1초 이하로 둡니다 — 그래야 이 루프가 `stop` 을 자주 확인해
    SIGTERM 뒤 5초 안에 종료할 수 있습니다.
    """
    while not stop.is_set():
        response: Any = client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=10,
            block=block_ms,
        )
        if not response:
            continue

        for stream_name, messages in response:
            for message_id, fields in messages:
                logger.info(
                    "worker.stream.received",
                    extra={
                        "stream": stream_name,
                        "message_id": message_id,
                        "fields": fields,
                    },
                )
