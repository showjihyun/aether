"""spec 0005 2.2, D-12: 불변 `WorkflowVersion` — 노드와 간선의 집합."""

from __future__ import annotations

from dataclasses import dataclass

from aether_workflow.domain.node import Edge, Node


@dataclass(frozen=True)
class WorkflowVersion:
    number: int
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
