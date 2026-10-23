import type { NodeKind } from "@/components/NodeKindIcon";

export type EditorNode = { id: string; kind: NodeKind };
export type EditorEdge = { source: string; target: string };

/**
 * 편집기 상태 -> 서버 액션이 받는 `graphJson`(DESIGN 7.3). **좌표를 싣지 않습니다**(spec 0007 D-9) -
 * 노드는 `id`·`kind`, 간선은 `source`·`target` 만 직렬화합니다. 키 순서가 고정이라 같은 상태는
 * 늘 같은 문자열입니다.
 */
export function serializeGraph(nodes: readonly EditorNode[], edges: readonly EditorEdge[]): string {
  return JSON.stringify({
    nodes: nodes.map(({ id, kind }) => ({ id, kind })),
    edges: edges.map(({ source, target }) => ({ source, target })),
  });
}

/** `agent-1`, `agent-2`... - 같은 종류에서 비어 있는 가장 작은 번호. 액션의 id 모양을 만족합니다. */
export function nextNodeId(nodes: readonly EditorNode[], kind: NodeKind): string {
  const taken = new Set(nodes.map((node) => node.id));
  for (let n = 1; ; n += 1) {
    const candidate = `${kind.toLowerCase()}-${n}`;
    if (!taken.has(candidate)) return candidate;
  }
}
