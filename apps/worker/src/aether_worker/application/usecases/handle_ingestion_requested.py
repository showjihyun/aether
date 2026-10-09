"""spec 0004 2.1, 2.4, D-4: `HandleIngestionRequestedUseCase` — `HandleIngestionRequested`
의 구현. `aether_context.IngestKnowledge`(inbound 포트)를 부르고, 시작·종결 상태를
`KnowledgeIngestionStatusNotifier` 로 api 에 알립니다(api 가 `control.knowledge_
ingestions` 에 적용 — worker 는 control 표를 쓰지 않습니다, 마이그레이션 0004 GRANT).

**ack 규칙.** 적재가 성공하든 실패(`Exception`)하든 ack 합니다 — 적재는 Run 과
달리 lease 경합이 없고(한 ingestion 은 한 worker 가 끝까지 처리), 실패는 `failed`
상태로 기록되어 사람이 재시도(새 적재 선언)를 결정합니다. 메시지 자체가 독이 되는
경우는 없습니다(파싱은 consumer 이미 끝냈습니다).

**`failure_reason` 길이 상한(2026-10-09 리뷰).** `str(exc)` 를 그대로 저장하지
않고 `_FAILURE_REASON_MAX_CHARS` 로 자릅니다 — 하위 계층(Connector·Embedder·
Store)의 예외 메시지가 우연히 문서 본문 조각을 담더라도(`UnicodeDecodeError` 등은
원문 바이트 일부를 메시지에 싣습니다) `control.knowledge_ingestions.failure_reason`
에 무제한으로 쌓이지 않게 합니다 — `observation_max_chars`(spec 0002 R-14)와 같은
발상입니다. 자격증명은 이 경로에 원래 등장하지 않습니다(적재는 파일시스템 경로만
다루고, DB 접속 정보는 호출자가 쥔 연결 팩토리 안에만 있습니다) — 그래도 길이
상한은 본문 조각이 길게 새는 것을 막는 일반적인 방어입니다.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from aether_context.application.ports.inbound.ingest_knowledge import (
    IngestKnowledge,
    IngestKnowledgeRequest,
)

from aether_worker.application.ports.inbound.handle_ingestion_requested import (
    HandleIngestionOutcome,
    IngestionRequestedMessage,
)
from aether_worker.application.ports.outbound.knowledge_ingestion_status_notifier import (
    KnowledgeIngestionStatusNotifier,
)

logger = logging.getLogger(__name__)

_FAILURE_REASON_MAX_CHARS = 500


class HandleIngestionRequestedUseCase:
    def __init__(
        self, ingest_knowledge: IngestKnowledge, notifier: KnowledgeIngestionStatusNotifier
    ) -> None:
        self._ingest_knowledge = ingest_knowledge
        self._notifier = notifier

    def __call__(self, message: IngestionRequestedMessage) -> HandleIngestionOutcome:
        started_at = datetime.now(UTC)
        self._notifier.notify(message.ingestion_id, "running", started_at, started_at=started_at)

        try:
            self._ingest_knowledge(
                IngestKnowledgeRequest(
                    knowledge_set_id=message.knowledge_set_id,
                    ingestion_id=message.ingestion_id,
                    source=message.source,
                )
            )
        except Exception as exc:  # noqa: BLE001 -- 실패를 `failed` 상태로 기록합니다
            finished_at = datetime.now(UTC)
            reason = str(exc)[:_FAILURE_REASON_MAX_CHARS]
            logger.warning(
                "worker.handle_ingestion_requested.failed",
                extra={"ingestion_id": str(message.ingestion_id), "error": reason},
            )
            self._notifier.notify(
                message.ingestion_id,
                "failed",
                finished_at,
                finished_at=finished_at,
                failure_reason=reason,
            )
            return HandleIngestionOutcome(ack=True)

        finished_at = datetime.now(UTC)
        self._notifier.notify(
            message.ingestion_id, "succeeded", finished_at, finished_at=finished_at
        )
        return HandleIngestionOutcome(ack=True)
