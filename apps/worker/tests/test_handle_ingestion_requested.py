"""spec 0004 2.1, 2.4, D-4: `HandleIngestionRequestedUseCase` — 상태 통지와 ack 규칙.

fake `IngestKnowledge`(성공/실패)로 `running` → `succeeded`/`failed` 통지 순서와
ack=True(항상)를 확인합니다. 컨테이너 없음 — `aether_context` 의 inbound 포트
타입만 씁니다(AR-12).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from aether_worker.application.ports.inbound.handle_ingestion_requested import (
    IngestionRequestedMessage,
)
from aether_worker.application.usecases.handle_ingestion_requested import (
    HandleIngestionRequestedUseCase,
)

from tests.support.context_fakes import FakeIngestKnowledge


class _FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str, dict[str, object]]] = []

    def notify(
        self,
        ingestion_id: UUID,
        status: Literal["running", "succeeded", "failed"],
        at: datetime,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        failure_reason: str | None = None,
    ) -> None:
        self.calls.append(
            (
                ingestion_id,
                status,
                {
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "failure_reason": failure_reason,
                },
            )
        )


def _message() -> IngestionRequestedMessage:
    return IngestionRequestedMessage(
        message_id="1-0",
        ingestion_id=uuid4(),
        knowledge_set_id=uuid4(),
        source="/srv/docs",
    )


def test_successful_ingestion_notifies_running_then_succeeded_and_acks() -> None:
    ingest = FakeIngestKnowledge()
    notifier = _FakeNotifier()
    use_case = HandleIngestionRequestedUseCase(ingest, notifier)
    message = _message()

    outcome = use_case(message)

    assert outcome.ack is True
    assert len(ingest.calls) == 1
    assert ingest.calls[0].knowledge_set_id == message.knowledge_set_id
    assert ingest.calls[0].ingestion_id == message.ingestion_id
    assert ingest.calls[0].source == message.source

    statuses = [call[1] for call in notifier.calls]
    assert statuses == ["running", "succeeded"]
    assert notifier.calls[0][0] == message.ingestion_id


def test_failed_ingestion_notifies_running_then_failed_with_reason_and_still_acks() -> None:
    ingest = FakeIngestKnowledge(error=RuntimeError("boom"))
    notifier = _FakeNotifier()
    use_case = HandleIngestionRequestedUseCase(ingest, notifier)
    message = _message()

    outcome = use_case(message)

    assert outcome.ack is True
    statuses = [call[1] for call in notifier.calls]
    assert statuses == ["running", "failed"]
    failed_extra = notifier.calls[1][2]
    assert failed_extra["failure_reason"] == "boom"


def test_failure_reason_is_truncated_so_document_content_cannot_leak_unbounded() -> None:
    """2026-10-09 리뷰: 예외 메시지가 우연히 문서 본문·긴 내용을 담아도(예: 하위
    계층이 잘못 구현되어 본문을 예외에 실어도) `failure_reason` 은 고정 길이를
    넘지 않습니다 — `control.knowledge_ingestions.failure_reason` 에 무제한으로
    쌓이지 않게 합니다(`observation_max_chars` 와 같은 발상, spec 0002 R-14)."""
    long_message = "leaked-document-body-" * 200  # 4400+ chars
    ingest = FakeIngestKnowledge(error=RuntimeError(long_message))
    notifier = _FakeNotifier()
    use_case = HandleIngestionRequestedUseCase(ingest, notifier)
    message = _message()

    use_case(message)

    failed_extra = notifier.calls[1][2]
    reason = failed_extra["failure_reason"]
    assert isinstance(reason, str)
    assert len(reason) <= 500
