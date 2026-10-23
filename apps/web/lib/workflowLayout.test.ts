import { describe, expect, it } from "vitest";

import { layoutGraph } from "./workflowLayout";

const n = (id: string) => ({ id });
const e = (source: string, target: string) => ({ source, target });

describe("layoutGraph (spec 0007 D-9: 자동 배치, 좌표는 저장하지 않는다)", () => {
  it("D-9: 사슬은 간선 방향으로 한 층씩 오른쪽으로 간다", () => {
    const pos = layoutGraph([n("a"), n("b"), n("c")], [e("a", "b"), e("b", "c")]);
    expect(pos.a!.x).toBeLessThan(pos.b!.x);
    expect(pos.b!.x).toBeLessThan(pos.c!.x);
    expect(pos.a!.y).toBe(pos.b!.y);
  });

  it("D-9: 갈라졌다 합쳐지는 그래프는 가장 긴 경로가 층을 정하고 같은 층은 겹치지 않는다", () => {
    const nodes = [n("s"), n("x"), n("y"), n("j")];
    const pos = layoutGraph(nodes, [e("s", "x"), e("s", "y"), e("x", "j"), e("y", "j")]);
    expect(pos.x!.x).toBe(pos.y!.x);
    expect(pos.x!.y).not.toBe(pos.y!.y);
    expect(pos.j!.x).toBeGreaterThan(pos.x!.x);
    const keys = new Set(Object.values(pos).map((p) => `${p.x},${p.y}`));
    expect(keys.size).toBe(nodes.length);
  });

  it("LOOP 의 되돌아가는 간선(사이클)이 있어도 끝나고 모든 노드가 자리를 얻는다", () => {
    const pos = layoutGraph([n("a"), n("b"), n("c")], [e("a", "b"), e("b", "c"), e("c", "b")]);
    expect(Object.keys(pos).sort()).toEqual(["a", "b", "c"]);
  });

  it("간선이 없는 노드와 알 수 없는 id 를 가리키는 간선도 깨지지 않는다", () => {
    const pos = layoutGraph([n("a"), n("b")], [e("a", "ghost")]);
    expect(Object.keys(pos).sort()).toEqual(["a", "b"]);
  });

  it("같은 입력이면 같은 출력이다(무작위 없음)", () => {
    const nodes = [n("s"), n("x"), n("y")];
    const edges = [e("s", "x"), e("s", "y")];
    expect(layoutGraph(nodes, edges)).toEqual(layoutGraph(nodes, edges));
  });

  it("빈 그래프는 빈 배치", () => {
    expect(layoutGraph([], [])).toEqual({});
  });
});
