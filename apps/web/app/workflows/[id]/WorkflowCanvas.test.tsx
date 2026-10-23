import type { WorkflowResponse } from "@aether/sdk";
import { cleanup, render } from "@testing-library/react";
import {
  Bot,
  CircleStop,
  GitBranch,
  GitFork,
  GitMerge,
  Hand,
  Plug,
  Play,
  Repeat,
  Sparkles,
  Timer,
  User,
  Wrench,
} from "lucide-react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

import { NODE_KIND_ICON } from "@/components/NodeKindIcon";

import { WorkflowCanvas } from "./WorkflowCanvas";

type Node = WorkflowResponse["nodes"][number];
type Edge = WorkflowResponse["edges"][number];

// jsdom 에는 React Flow 가 요구하는 브라우저 API 가 없습니다.
beforeAll(() => {
  class RO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = RO;
  // 간선 label 의 크기 측정(jsdom 에는 SVG 레이아웃이 없습니다).
  (SVGElement.prototype as unknown as { getBBox: () => object }).getBBox = () => ({
    x: 0, y: 0, width: 40, height: 16,
  });
  globalThis.DOMMatrixReadOnly ??= class {
    m22 = 1;
  } as unknown as typeof DOMMatrixReadOnly;
});
afterEach(cleanup);

const KINDS = [
  "START", "END", "AGENT", "CONDITION", "PARALLEL", "JOIN", "LOOP",
  "WAIT", "LLM", "MCP", "TOOL", "HUMAN", "APPROVAL",
] as const;

const nodes: Node[] = [
  { id: "start", kind: "START" },
  { id: "classify", kind: "AGENT" },
  { id: "end", kind: "END" },
];
const edges: Edge[] = [
  { source: "start", target: "classify" },
  { source: "classify", target: "end", label: "승인됨" },
];

describe("<WorkflowCanvas /> (spec 0007 R-10, D-1, D-9; DESIGN 6절)", () => {
  it("DESIGN 6: NodeKind 열셋 전부가 표에 적힌 lucide 아이콘에 1:1 로 묶인다", () => {
    expect(Object.keys(NODE_KIND_ICON).sort()).toEqual([...KINDS].sort());
    expect(NODE_KIND_ICON).toMatchObject({
      START: Play, END: CircleStop, AGENT: Bot, CONDITION: GitBranch, PARALLEL: GitFork,
      JOIN: GitMerge, LOOP: Repeat, WAIT: Timer, LLM: Sparkles, MCP: Plug, TOOL: Wrench,
      HUMAN: User, APPROVAL: Hand,
    });
  });

  it("P5-5 판정: 고정 그래프의 노드 수만큼 카드가, 간선 수만큼 간선이 그려진다", () => {
    const { container } = render(<WorkflowCanvas nodes={nodes} edges={edges} />);
    expect(container.querySelectorAll(".react-flow__node")).toHaveLength(3);
    expect(container.querySelectorAll(".react-flow__edge")).toHaveLength(2);
  });

  it("DESIGN 6/8: 카드마다 종류 이름과 노드 id 가 함께 보인다", () => {
    const all = KINDS.map((kind) => ({ id: `n-${kind.toLowerCase()}`, kind }));
    const { container } = render(<WorkflowCanvas nodes={all} edges={[]} />);
    const cards = [...container.querySelectorAll<HTMLElement>(".react-flow__node")];
    expect(cards).toHaveLength(13);
    for (const kind of KINDS) {
      const card = cards.find((c) => c.getAttribute("data-id") === `n-${kind.toLowerCase()}`)!;
      expect(card.textContent).toContain(kind);
      expect(card.textContent).toContain(`n-${kind.toLowerCase()}`);
      expect(card.querySelector("svg")).not.toBeNull();
    }
  });

  it("DESIGN 6: 카드는 전부 같은 모양이다(종류별 클래스가 없다)", () => {
    const { container } = render(<WorkflowCanvas nodes={nodes} edges={edges} />);
    const shapes = new Set(
      [...container.querySelectorAll('[data-slot="workflow-node"]')].map((c) => c.className),
    );
    expect(shapes.size).toBe(1);
  });

  it("DESIGN 5: 간선 label 이 있으면 보인다", () => {
    const { container } = render(<WorkflowCanvas nodes={nodes} edges={edges} />);
    expect(container.textContent).toContain("승인됨");
  });

  it("D-9: 노드·간선에 좌표를 넣어 주지 않아도 그려지고, 저장소에 아무것도 쓰지 않는다", () => {
    localStorage.clear();
    const { container } = render(<WorkflowCanvas nodes={nodes} edges={edges} />);
    expect(container.querySelectorAll(".react-flow__node")).toHaveLength(3);
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("읽기 전용: 끌기·선택이 꺼져 있다(P5-6 의 몫)", () => {
    const { container } = render(<WorkflowCanvas nodes={nodes} edges={edges} />);
    expect(container.querySelector(".react-flow__node.draggable")).toBeNull();
    expect(container.querySelector(".react-flow__node.selectable")).toBeNull();
  });
});
