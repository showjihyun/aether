"""spec 0005 2.2, D-14: 노드 종류(열 하나)와 노드·간선 값 객체. 불변."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from aether_workflow.domain.condition import ConditionOperator


class NodeKind(StrEnum):
    START = "START"
    END = "END"
    AGENT = "AGENT"
    CONDITION = "CONDITION"
    PARALLEL = "PARALLEL"
    JOIN = "JOIN"
    LOOP = "LOOP"
    WAIT = "WAIT"
    LLM = "LLM"
    MCP = "MCP"
    TOOL = "TOOL"
    HUMAN = "HUMAN"
    APPROVAL = "APPROVAL"


@dataclass(frozen=True)
class Node:
    """노드는 종류별 설정을 가집니다(spec 0005 2.2 개정 3).

    `max_iterations` 는 `LOOP` 에서만 뜻이 있고(D-11), `agent_id`·`agent_version` 은 `AGENT`
    에서만 뜻이 있습니다 — 같은 자리입니다. 다른 종류의 노드에 있는 값은 거부하지 않고
    **무시**합니다(`max_iterations` 가 `LOOP` 아닌 노드에서 무시되는 것과 같은 규칙).
    `agent_version` 이 없으면 실행 시점의 최신 Version 을 뜻합니다.

    `condition_path`·`condition_operator`·`condition_value` 는 `CONDITION` 과 `LOOP` 에서만 뜻이
    있습니다(개정 4, 개정 7 의 4) - 같은 자리, 같은 규칙입니다. `LOOP` 에서는 `true` 간선이 본문이고
    `false` 간선이 탈출입니다. 연산자가 `exists` 면 `condition_value` 는 없습니다.

    `wait_seconds` 는 `WAIT` 에서만 뜻이 있습니다(개정 7 (5)) - 필수이고 양수여야 하며(저장 때
    검증), 다른 종류의 노드에 있는 값은 무시합니다. 직렬화(R-2)에 **반드시** 들어갑니다 - 빠지면
    기다리는 시간만 다른 두 정의가 같은 바이트를 냅니다.
    """

    id: str
    kind: NodeKind
    max_iterations: int | None = None
    agent_id: UUID | None = None
    agent_version: int | None = None
    condition_path: str | None = None
    condition_operator: ConditionOperator | None = None
    condition_value: Any = None
    wait_seconds: int | None = None


@dataclass(frozen=True)
class Edge:
    """`label` 은 `CONDITION`·`LOOP` 의 분기 이름(`"true"`·`"false"`)입니다."""

    source: str
    target: str
    label: str | None = None
