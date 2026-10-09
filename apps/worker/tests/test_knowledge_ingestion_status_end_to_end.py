"""spec 0004 2.4, D-4: 상태 스트림 왕복 end-to-end — worker 의 실제
`RedisKnowledgeIngestionStatusNotifier` 가 쓰고, api 의 실제 `IngestionStatusConsumer`
+ `ApplyIngestionStatusUseCase` + `PostgresKnowledgeDeclarationStore` 가 읽어
`control.knowledge_ingestions` 에 투영하는 전체 경로. 실제 PostgreSQL + Redis.

이 파일은 `aether_api` 를 import 합니다 — AR-7 은 `aether_api` 가 `aether_worker` 를
import 하는 것만 금지합니다(반대 방향은 제약이 없고, 이 파일은 테스트이지 제품
코드가 아닙니다). 2026-10-09 리뷰 반려(변이 증거 8번)가 지적한 공백 — "worker 가
상태를 발행하지 않으면 실패하는 테스트가 있는가" — 를 실제 worker 어댑터
(`RedisKnowledgeIngestionStatusNotifier`)까지 포함해 채웁니다. `test_knowledge_
ingestion_status_roundtrip.py`(apps/api)는 worker 의 와이어 계약만 **복제**했고
실제 worker 코드를 부르지 않았습니다 — 이 파일이 그 마지막 틈을 닫습니다.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
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
from aether_worker.adapters.outbound.redis.ingestion_status_notifier import (
    RedisKnowledgeIngestionStatusNotifier,
)
from aether_worker.application.ports.inbound.handle_ingestion_requested import (
    IngestionRequestedMessage,
)
from aether_worker.application.usecases.handle_ingestion_requested import (
    HandleIngestionRequestedUseCase,
)
from redis import Redis

from tests.support.context_fakes import FakeIngestKnowledge
from tests.support.waiting import wait_until

pytestmark = pytest.mark.integration

_STREAM = "aether:knowledge:ingestions:status"
_GROUP = "aether-api"
_JOIN_TIMEOUT = 5.0


def test_worker_notifier_to_api_consumer_projects_succeeded(
    control_connection_factory: Callable[[], psycopg.Connection],
    redis_client: Redis,
) -> None:
    # -- api 쪽: 선언 ---------------------------------------------------------
    store = PostgresKnowledgeDeclarationStore(control_connection_factory)
    knowledge_set = store.create_set(f"set-{uuid4()}")
    ingestion = store.create_ingestion(knowledge_set.id, "/srv/docs")
    assert ingestion.status == "queued"

    # -- api 쪽: 상태 소비자 기동 ----------------------------------------------
    ensure_group(redis_client, _STREAM, _GROUP)
    apply_status = ApplyIngestionStatusUseCase(store)
    stop = threading.Event()
    consumer = IngestionStatusConsumer(
        redis_client, apply_status, stream=_STREAM, group=_GROUP, consumer="api-e2e", block_ms=200
    )
    thread = threading.Thread(target=consumer.run_until, args=(stop,))
    thread.start()

    try:
        # -- worker 쪽: 실제 어댑터로 상태 발행 --------------------------------
        notifier = RedisKnowledgeIngestionStatusNotifier(redis_client)
        handler = HandleIngestionRequestedUseCase(FakeIngestKnowledge(), notifier)
        outcome = handler(
            IngestionRequestedMessage(
                message_id="1-0",
                ingestion_id=ingestion.id,
                knowledge_set_id=knowledge_set.id,
                source="/srv/docs",
            )
        )
        assert outcome.ack is True

        def _projected() -> bool:
            current = store.get_ingestion(ingestion.id)
            return current is not None and current.status == "succeeded"

        done = wait_until(_projected, timeout=_JOIN_TIMEOUT)
        assert done, "5초 안에 control.knowledge_ingestions 가 succeeded 로 투영되지 않았습니다"
    finally:
        stop.set()
        thread.join(_JOIN_TIMEOUT)

    final = store.get_ingestion(ingestion.id)
    assert final is not None
    assert final.status == "succeeded"
