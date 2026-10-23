/**
 * Workflow 그래프의 자동 배치(spec 0007 D-9, R-12).
 *
 * 좌표는 **저장하지 않습니다** - 정의에도, localStorage 에도 없고, 열 때마다 이 함수가 간선에서
 * 다시 계산합니다. 입력이 같으면 출력이 같습니다(무작위 없음). 그래서 "열 때마다 달라질 수
 * 있다" 는 말은 **그래프가 바뀌었을 때** 의미이고, R-12 의 문장은 위치가 약속이 아니라는
 * 뜻입니다.
 *
 * 층 = 시작점에서 **가장 긴 경로**의 길이. LOOP 의 되돌아가는 간선(사이클)은 DFS 로 찾아 층
 * 계산에서 뺍니다 - 그래도 간선은 그려집니다(배치에만 쓰지 않습니다).
 */

export const COLUMN_GAP = 256;
export const ROW_GAP = 104;

export interface Position {
  x: number;
  y: number;
}

export function layoutGraph(
  nodes: ReadonlyArray<{ id: string }>,
  edges: ReadonlyArray<{ source: string; target: string }>,
): Record<string, Position> {
  const ids = nodes.map((node) => node.id);
  const known = new Set(ids);
  const out = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const { source, target } of edges) {
    if (source !== target && known.has(source) && known.has(target)) out.get(source)!.push(target);
  }

  // 사이클을 끊는 되돌이 간선: DFS 에서 아직 끝나지 않은(회색) 노드를 가리키는 간선.
  const state = new Map<string, 1 | 2>();
  const back = new Set<string>();
  const visit = (start: string) => {
    const stack: Array<{ id: string; next: number }> = [{ id: start, next: 0 }];
    state.set(start, 1);
    while (stack.length > 0) {
      const frame = stack[stack.length - 1]!;
      const targets = out.get(frame.id)!;
      if (frame.next >= targets.length) {
        state.set(frame.id, 2);
        stack.pop();
        continue;
      }
      const target = targets[frame.next++]!;
      if (state.get(target) === 1) back.add(`${frame.id}\u0000${target}`);
      else if (!state.has(target)) {
        state.set(target, 1);
        stack.push({ id: target, next: 0 });
      }
    }
  };
  for (const id of ids) if (!state.has(id)) visit(id);

  // 남은 DAG 에서 가장 긴 경로(Kahn).
  const forward = new Map<string, string[]>(ids.map((id) => [id, []]));
  const indegree = new Map<string, number>(ids.map((id) => [id, 0]));
  for (const [source, targets] of out) {
    for (const target of targets) {
      if (back.has(`${source}\u0000${target}`)) continue;
      forward.get(source)!.push(target);
      indegree.set(target, indegree.get(target)! + 1);
    }
  }
  const layer = new Map<string, number>(ids.map((id) => [id, 0]));
  const ready = ids.filter((id) => indegree.get(id) === 0);
  while (ready.length > 0) {
    const id = ready.shift()!;
    for (const target of forward.get(id)!) {
      layer.set(target, Math.max(layer.get(target)!, layer.get(id)! + 1));
      indegree.set(target, indegree.get(target)! - 1);
      if (indegree.get(target) === 0) ready.push(target);
    }
  }

  const rows = new Map<number, number>();
  const positions: Record<string, Position> = {};
  for (const id of ids) {
    const column = layer.get(id)!;
    const row = rows.get(column) ?? 0;
    rows.set(column, row + 1);
    positions[id] = { x: column * COLUMN_GAP, y: row * ROW_GAP };
  }
  return positions;
}
