"""spec 0007 2.3 (P5-1): `control.workflow_node_states` 에 대한 outbound 포트.

fake 와 PostgreSQL 구현(`adapters/outbound/db/workflow_node_state_projection_store.py`)은 같은
계약을 만족해야 합니다. 투영만 합니다 -- 실행 상태의 정본(`data` 평면의 노드 실행 표 —
api 는 그 이름을 부르지 않습니다, 0001 R-7)은 모릅니다.
"""

from __future__ import annotations

from typing import Protocol

from aether_api.domain.workflow_node_status_message import WorkflowNodeStatusMessage


class WorkflowNodeStateProjectionStore(Protocol):
    def apply_status(self, message: WorkflowNodeStatusMessage) -> bool:
        """`(workflow_run_id, node_id)` 키의 행을 만들거나 갱신합니다. 이미 있는 행의 `status_seq`
        가 `message.status_seq` 이상이면 **아무 것도 바꾸지 않고** `False`(늦은 메시지를 버립니다).
        없는 Workflow Run 이면 `False`. 적용됐으면 `True`.

        `started_at` 은 주었을 때만 바꿉니다(`COALESCE`). `finished_at`·`failure_reason` 은 메시지의
        값을 **그대로** 씁니다 -- 루프에서 노드가 다시 `running` 이 되면 이전 회차의 종결 값이
        남지 않아야 합니다."""
        ...
