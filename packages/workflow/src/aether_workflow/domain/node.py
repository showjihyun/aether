"""spec 0005 2.2, D-14: 노드 종류(열 하나)와 노드·간선 값 객체. 불변."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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


@dataclass(frozen=True)
class Node:
    """`max_iterations` 는 `LOOP` 에서만 뜻이 있습니다(D-11)."""

    id: str
    kind: NodeKind
    max_iterations: int | None = None


@dataclass(frozen=True)
class Edge:
    """`label` 은 CONDITION 분기 이름 자리입니다(P4-2b 가 채웁니다)."""

    source: str
    target: str
    label: str | None = None
