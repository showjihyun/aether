"""spec 0005 2.3: Workflow Run 이 `failed` 로 끝난 사유.

spec 2.3 은 Workflow 실패 어휘를 정하지 않았으므로 **실행기 골격(P4-2a A)이 필요한 만큼만**
둡니다. 늘리는 것은 뒤 단위(자식 Run 실패는 PR B, 분기는 P4-2b)입니다.
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
