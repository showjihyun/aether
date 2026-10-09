"""spec 0004 2.4, D-4: 상태 스트림 왕복(worker→api) — 실제 PostgreSQL + Redis.

`RedisKnowledgeIngestionStatusNotifier`(worker 쪽, `aether_worker.adapters.outbound.
redis.ingestion_status_notifier`)가 내보내는 것과 **같은 필드 모양**으로 직접
`XADD` 합니다 — `aether_api` 는 `aether_worker` 를 import 하지 않습니다(AR-7),
그래서 와이어 계약만 복제하고 실제 모듈은 참조하지 않습니다.

`IngestionStatusConsumer` + `ApplyIngestionStatusUseCase` + `PostgresKnowledgeDeclarationStore`
를 모두 실제로 연결해, 선언된 `control.knowledge_ingestions` 행이 Redis 메시지 하나로
`queued` → `succeeded` 로 투영되는 것을 확인합니다. 2026-10-09 리뷰 반려(변이 증거
8번)가 지적한 공백 — "worker 가 상태를 발행하지 않으면 실패하는 테스트가 있는가"
— 를 end-to-end 로 채웁니다.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
import pytest
from aether_api.adapters.inbound.stream.ingestion_status_consumer import (
    IngestionStatusConsumer,
    ensure_group,
)
from aether_api.adapters.outbound.db.knowledge_declaration_store import (
    PostgresKnowledgeDeclarationStore,
)
from aether_api.application.usecases.apply_ingestion_status import ApplyIngestionStatusUseCase
from redis import Redis

from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_STREAM = "aether:knowledge:ingestions:status"
_GROUP = "aether-api"
_JOIN_TIMEOUT = 5.0


def test_worker_status_notification_updates_control_knowledge_ingestions(
    control_connection_factory: Callable[[], psycopg.Connection],
    redis_client: Redis,
) -> None:
    store = PostgresKnowledgeDeclarationStore(control_connection_factory)
    knowledge_set = store.create_set(f"set-{uuid4()}")
    ingestion = store.create_ingestion(knowledge_set.id, "/srv/docs")
    assert ingestion.status == "queued"

    ensure_group(redis_client, _STREAM, _GROUP)
    apply_status = ApplyIngestionStatusUseCase(store)
    stop = threading.Event()
    consumer = IngestionStatusConsumer(
        redis_client, apply_status, stream=_STREAM, group=_GROUP, consumer="api-rt", block_ms=200
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()
    try:
        finished_at = datetime.now(UTC)
        # worker 의 `RedisKnowledgeIngestionStatusNotifier.notify(...)` 와 같은 필드 모양.
        redis_client.xadd(
            _STREAM,
            {
                "ingestion_id": str(ingestion.id),
                "status": "succeeded",
                "at": finished_at.isoformat(),
                "finished_at": finished_at.isoformat(),
            },
        )

        def _projected() -> bool:
            current = store.get_ingestion(ingestion.id)
            return current is not None and current.status == "succeeded"

        done = wait_until(_projected, timeout=_JOIN_TIMEOUT)
        assert done, "5초 안에 control.knowledge_ingestions 에 상태가 투영되지 않았습니다"
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    final = store.get_ingestion(ingestion.id)
    assert final is not None
    assert final.status == "succeeded"
    assert final.finished_at is not None
