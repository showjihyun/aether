"""spec 0005 2.3: Workflow Run 이 `failed` 로 끝난 사유.

spec 2.3 은 Workflow 실패 어휘를 정하지 않았으므로 **필요한 만큼만** 둡니다(A: 골격, B: `AGENT`
노드). 늘리는 것은 뒤 단위(분기는 P4-2b)입니다. 노드 실행 기록의 `failure_reason` 도 같은 값을
씁니다.
"""

from __future__ import annotations

from enum import StrEnum


class WorkflowFailureReason(StrEnum):
    UNSUPPORTED_NODE_KIND = "unsupported_node_kind"
    """`START`·`END` 외의 노드 종류를 만났습니다(이 실행기가 아직 모르는 종류)."""

    UNSUPPORTED_BRANCHING = "unsupported_branching"
    """나가는 간선이 둘 이상입니다 — 분기는 P4-2b 입니다. 조용히 하나를 고르지 않습니다."""

    INVALID_GRAPH = "invalid_graph"
    """저장 시점 검증을 통과했다면 생기지 않는 모양(START 없음, 나가는 간선 없는 비-END)."""

    AGENT_RUN_FAILED = "agent_run_failed"
    """자식 Agent Run 이 `succeeded` 가 아닌 종결(`failed`·`cancelled`·`timed_out`)로 끝났습니다."""

    AGENT_VERSION_NOT_FOUND = "agent_version_not_found"
    """`AGENT` 노드가 가리키는 Agent·Version 이 없습니다(또는 참조가 비어 있습니다). 발사하지 않고
    노드를 실패시킵니다 - 발사하면 api 가 선언하지 못한 자식을 기다리며 영원히 파킹됩니다."""

    WORKFLOW_RUN_WITHOUT_REQUESTER = "workflow_run_without_requester"
    """Workflow Run 에 요청자가 없습니다(마이그레이션 0007 이전에 만들어진 행). 비운 채로 자식 Run
    을
    발사하면 `GET /runs/{id}` 가 500 이라 조용히 넘기지 않고 노드를 실패시킵니다."""
