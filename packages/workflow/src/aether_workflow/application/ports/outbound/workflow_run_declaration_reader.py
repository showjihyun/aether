"""spec 0005 2.3, 2.9 개정 2: `WorkflowRunDeclarationReader` — `control` 에서 **읽기만** 합니다.

`control.workflow_runs` + `control.workflow_versions` JOIN. worker 역할(`aether_data`)은 그 둘에
SELECT 가 있습니다(마이그레이션 0005).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from aether_workflow.domain.node import Edge, Node


@dataclass(frozen=True)
class WorkflowRunDeclaration:
    workflow_run_id: UUID
    workflow_version_id: UUID
    version_number: int
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    input: dict[str, Any] | None
    cancel_requested_at: datetime | None
    requested_by: UUID | None = None
    """Workflow 를 시작한 주체. 0007 이전에 만들어진 행은 `None` 입니다."""


class WorkflowRunDeclarationReader(Protocol):
    def declaration(self, workflow_run_id: UUID) -> WorkflowRunDeclaration | None: ...
