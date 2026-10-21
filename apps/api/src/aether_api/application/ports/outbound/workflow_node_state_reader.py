"""spec 0007 2.3 (P5-2): `control.workflow_node_states` 를 **읽는** outbound 포트.

쓰는 포트(`WorkflowNodeStateProjectionStore`)와 나눈 것은 소비자(상태 통지 적용)와 조회가 서로의
메서드를 몰라도 되게 하기 위해서입니다. PostgreSQL 구현은 한 클래스가 둘 다 만족합니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_api.domain.workflow_node_state import WorkflowNodeStatePage


class WorkflowNodeStateReader(Protocol):
    def list_for_run(
        self, workflow_run_id: UUID, limit: int, cursor: str | None
    ) -> WorkflowNodeStatePage:
        """그 Workflow Run 의 노드 상태를 `node_id` 오름차순 커서 페이지로 돌려줍니다. Run 이 없거나
        노드가 없으면 빈 페이지 -- 404 판정은 호출자(유스케이스)의 몫입니다. 깨진 `cursor` 는
        `InvalidCursor`."""
        ...
