"""spec 0005 2.6 개정 5 (3) (P4-4): `ApprovalReader` - 저장된 승인을 **읽기만** 합니다.

어댑터는 `control.workflow_approvals` 를 SELECT 합니다(`aether_data` 에 SELECT 만 더해졌습니다,
마이그레이션 0008 - 사람 검토 항목 H-1). 쓰지 않습니다: 승인을 기록하는 것은 api 입니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_workflow.domain.approval import Approval


class ApprovalReader(Protocol):
    def approval_for(self, node_execution_id: UUID) -> Approval | None:
        """그 노드 실행에 저장된 승인. 없으면 `None` - 실행기는 아무 것도 바꾸지 않고 파킹을
        유지합니다. 승인은 노드 실행당 한 건입니다(`unique(workflow_run_id, node_execution_id)`)."""
        ...
