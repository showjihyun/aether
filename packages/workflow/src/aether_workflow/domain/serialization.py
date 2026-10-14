"""spec 0005 R-2: `WorkflowVersion` 의 결정적 직렬화 — 같은 정의는 바이트 동일.

집합·딕셔너리 순회 순서에 기대지 않습니다(spec 0004 D-12 의 함정). 노드는 id, 간선은
(source, target, label) 으로 정렬하고 `sort_keys` 가 붙은 JSON 으로 씁니다.
"""

from __future__ import annotations

import json

from aether_workflow.domain.workflow_version import WorkflowVersion


def serialize_version(version: WorkflowVersion) -> bytes:
    nodes = [
        {
            "id": n.id,
            "kind": n.kind.value,
            "max_iterations": n.max_iterations,
            "agent_id": str(n.agent_id) if n.agent_id is not None else None,
            "agent_version": n.agent_version,
        }
        for n in sorted(version.nodes, key=lambda n: n.id)
    ]
    edges = [
        {"source": e.source, "target": e.target, "label": e.label}
        for e in sorted(version.edges, key=lambda e: (e.source, e.target, e.label or ""))
    ]
    doc = {"number": version.number, "nodes": nodes, "edges": edges}
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
