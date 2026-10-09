"""spec 0004 2.4, D-4: `ApplyIngestionStatusUseCase` — 저장소에 그대로 위임, 멱등 무시."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from aether_api.application.usecases.apply_ingestion_status import ApplyIngestionStatusUseCase
from aether_api.domain.knowledge_ingestion_status_message import KnowledgeIngestionStatusMessage

from apps.api.tests.fakes_knowledge import FakeKnowledgeDeclarationStore


def test_apply_ingestion_status_updates_store_and_is_idempotent_for_unknown_id() -> None:
    store = FakeKnowledgeDeclarationStore()
    knowledge_set = store.create_set("docs")
    ingestion = store.create_ingestion(knowledge_set.id, "/srv/docs")
    apply_status = ApplyIngestionStatusUseCase(store)

    applied = apply_status(
        KnowledgeIngestionStatusMessage(
            ingestion_id=ingestion.id,
            status="succeeded",
            at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
    )
    assert applied is True
    updated = store.get_ingestion(ingestion.id)
    assert updated is not None
    assert updated.status == "succeeded"

    missing_applied = apply_status(
        KnowledgeIngestionStatusMessage(ingestion_id=uuid4(), status="failed", at=datetime.now(UTC))
    )
    assert missing_applied is False
