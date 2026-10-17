"""spec 0006 2.3, D-3: 목록 유스케이스 인터페이스 다섯.

HTTP 어댑터(`adapters/inbound/http/listings.py`)는 이 포트 타입만 보고 부릅니다(AR-12) - 구현은
조립(`main.py`)이 건네줍니다. 페이지 규칙은 `ListAgents` 와 같습니다: `cursor` 이후 최대 `limit`
개, `next_cursor` 는 불투명 문자열. 필터는 상태 하나까지입니다.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from aether_runtime.domain.run import RunStatus
from aether_workflow.domain.run_status import WorkflowRunStatus

from aether_api.domain.knowledge import IngestionStatus, KnowledgeIngestionPage, KnowledgeSetPage
from aether_api.domain.run import RunPage
from aether_api.domain.workflow import WorkflowPage
from aether_api.domain.workflow_run import WorkflowRunPage


class ListRuns(Protocol):
    """Agent Run 의 투영(`control.runs`)을 `status` 로 거를 수 있게 페이지로 돌려줍니다."""

    def __call__(self, limit: int, cursor: str | None, status: RunStatus | None) -> RunPage: ...


class ListWorkflows(Protocol):
    """Workflow 정의의 요약(이름·현재 Version 번호)을 페이지로 돌려줍니다."""

    def __call__(self, limit: int, cursor: str | None) -> WorkflowPage: ...


class ListWorkflowRuns(Protocol):
    """Workflow Run 의 투영(`control.workflow_runs`)을 `status` 로 거를 수 있게 돌려줍니다."""

    def __call__(
        self, limit: int, cursor: str | None, status: WorkflowRunStatus | None
    ) -> WorkflowRunPage: ...


class ListKnowledgeSets(Protocol):
    """Knowledge 세트를 페이지로 돌려줍니다."""

    def __call__(self, limit: int, cursor: str | None) -> KnowledgeSetPage: ...


class ListIngestions(Protocol):
    """한 세트의 적재를 `status` 로 거를 수 있게 돌려줍니다.

    세트가 없으면 `KnowledgeSetNotFound` 를 던집니다(빈 목록이 아닙니다).
    """

    def __call__(
        self,
        knowledge_set_id: UUID,
        limit: int,
        cursor: str | None,
        status: IngestionStatus | None,
    ) -> KnowledgeIngestionPage: ...
