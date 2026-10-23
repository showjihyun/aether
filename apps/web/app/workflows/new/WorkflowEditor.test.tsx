import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const createWorkflowAction = vi.fn<(name: string, graphJson: string) => Promise<unknown>>();
vi.mock("../actions", () => ({
  createWorkflowAction: (name: string, graphJson: string) => createWorkflowAction(name, graphJson),
}));
const push = vi.fn<(href: string) => void>();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import { VIOLATION_SENTENCE } from "@/lib/workflowViolations";

import { WorkflowEditor } from "./WorkflowEditor";

// jsdom 에는 React Flow 가 요구하는 브라우저 API 가 없습니다.
beforeAll(() => {
  class RO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = RO;
  (SVGElement.prototype as unknown as { getBBox: () => object }).getBBox = () => ({
    x: 0, y: 0, width: 40, height: 16,
  });
  globalThis.DOMMatrixReadOnly ??= class {
    m22 = 1;
  } as unknown as typeof DOMMatrixReadOnly;
});
beforeEach(() => {
  createWorkflowAction.mockReset();
  push.mockReset();
  localStorage.clear();
});
afterEach(cleanup);

const WORKFLOW_ID = "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b";

function addNode(kind: string) {
  fireEvent.change(screen.getByLabelText("노드 종류"), { target: { value: kind } });
  fireEvent.click(screen.getByRole("button", { name: "노드 추가" }));
}
function connect(from: string, to: string) {
  fireEvent.change(screen.getByLabelText("연결 시작"), { target: { value: from } });
  fireEvent.change(screen.getByLabelText("연결 끝"), { target: { value: to } });
  fireEvent.click(screen.getByRole("button", { name: "연결" }));
}
function save() {
  fireEvent.click(screen.getByRole("button", { name: "저장" }));
}
function card(id: string): HTMLElement {
  const el = document.querySelector<HTMLElement>(`[data-slot="workflow-node"][data-node-id="${id}"]`);
  if (!el) throw new Error(`card ${id} not found`);
  return el;
}
function cards(): string[] {
  return [...document.querySelectorAll<HTMLElement>('[data-slot="workflow-node"]')].map(
    (el) => el.dataset.nodeId!,
  );
}

describe("WorkflowEditor - 그리기 (spec 0007 R-3·D-9; DESIGN 5·6절)", () => {
  it("종류 선택지는 NodeKind 열셋이고, 추가하면 종류 이름과 id 가 있는 카드가 생긴다", () => {
    render(<WorkflowEditor />);
    const options = within(screen.getByLabelText("노드 종류"))
      .getAllByRole("option")
      .map((o) => (o as HTMLOptionElement).value);
    expect(options).toEqual([
      "START", "END", "AGENT", "CONDITION", "PARALLEL", "JOIN", "LOOP",
      "WAIT", "LLM", "MCP", "TOOL", "HUMAN", "APPROVAL",
    ]);

    addNode("AGENT");

    expect(cards()).toEqual(["agent-1"]);
    expect(card("agent-1").textContent).toContain("AGENT");
    expect(card("agent-1").textContent).toContain("agent-1");
  });

  it("같은 종류를 또 더하면 id 가 겹치지 않는다", () => {
    render(<WorkflowEditor />);
    addNode("AGENT");
    addNode("AGENT");
    expect(cards()).toEqual(["agent-1", "agent-2"]);
  });

  it("노드를 지우면 그 노드에 닿은 연결도 함께 사라진다", () => {
    render(<WorkflowEditor />);
    addNode("START");
    addNode("END");
    connect("start-1", "end-1");
    expect(screen.getAllByRole("button", { name: /연결 끊기/ })).toHaveLength(1);

    fireEvent.click(within(card("end-1")).getByRole("button", { name: /삭제/ }));

    expect(cards()).toEqual(["start-1"]);
    expect(screen.queryAllByRole("button", { name: /연결 끊기/ })).toHaveLength(0);
  });

  it("연결을 끊을 수 있다", () => {
    render(<WorkflowEditor />);
    addNode("START");
    addNode("END");
    connect("start-1", "end-1");

    fireEvent.click(screen.getByRole("button", { name: /연결 끊기/ }));

    expect(screen.queryAllByRole("button", { name: /연결 끊기/ })).toHaveLength(0);
  });

  it("같은 연결을 두 번 만들지 않는다", () => {
    render(<WorkflowEditor />);
    addNode("START");
    addNode("END");
    connect("start-1", "end-1");
    connect("start-1", "end-1");
    expect(screen.getAllByRole("button", { name: /연결 끊기/ })).toHaveLength(1);
  });

  it("R-12·D-8: 저장 자리에 Version 1 로 만들어지고 이후 수정은 새 Version 이며 돌고 있는 Run 은 이전 Version 을 쓴다고 말한다", () => {
    render(<WorkflowEditor />);
    const note = screen.getByTestId("save-note").textContent;
    expect(note).toContain("Version 1");
    expect(note).toContain("새 Version");
    expect(note).toContain("돌고 있는 Run 은 이전 Version 을 계속 씁니다");
  });

  it("D-9: 좌표가 저장되지 않는다는 문장이 있고, localStorage 에 아무것도 넣지 않는다", () => {
    render(<WorkflowEditor />);
    addNode("START");
    expect(screen.getByText(/노드 위치는 저장되지 않습니다/)).toBeTruthy();
    expect(localStorage.length).toBe(0);
  });
});

describe("WorkflowEditor - 저장 (spec 0007 R-4, D-9; plan P5-6 판정)", () => {
  it("캔버스 상태 -> 액션이 받는 (name, graphJson) 의 고정값. 좌표 키가 없다", async () => {
    createWorkflowAction.mockResolvedValue({ ok: true, workflowId: WORKFLOW_ID, version: 1 });
    render(<WorkflowEditor />);
    fireEvent.change(screen.getByLabelText("이름"), { target: { value: "triage" } });
    addNode("START");
    addNode("AGENT");
    addNode("END");
    connect("start-1", "agent-1");
    connect("agent-1", "end-1");

    save();

    await waitFor(() => expect(createWorkflowAction).toHaveBeenCalledTimes(1));
    const [name, graphJson] = createWorkflowAction.mock.calls[0]!;
    expect(name).toBe("triage");
    expect(graphJson).toBe(
      '{"nodes":[{"id":"start-1","kind":"START"},{"id":"agent-1","kind":"AGENT"},{"id":"end-1","kind":"END"}],' +
        '"edges":[{"source":"start-1","target":"agent-1"},{"source":"agent-1","target":"end-1"}]}',
    );
    expect(graphJson).not.toMatch(/"(x|y|position)"/);
  });

  it("성공하면 /workflows/{만들어진 id} 로 보낸다", async () => {
    createWorkflowAction.mockResolvedValue({ ok: true, workflowId: WORKFLOW_ID, version: 1 });
    render(<WorkflowEditor />);
    fireEvent.change(screen.getByLabelText("이름"), { target: { value: "w" } });
    addNode("START");

    save();

    await waitFor(() => expect(push).toHaveBeenCalledWith(`/workflows/${WORKFLOW_ID}`));
  });

  it("R-4: 400 고정값 -> 노드 위반은 그 카드 위에, node_id 없는 위반은 그래프 수준 자리에 문장으로 붙는다", async () => {
    createWorkflowAction.mockResolvedValue({
      ok: false,
      message: "그래프가 저장되지 않았습니다.",
      violations: [
        { reason: "agent_node_without_agent", nodeId: "agent-1" },
        { reason: "orphan_node", nodeId: "agent-1" },
        { reason: "no_start", nodeId: null },
      ],
    });
    render(<WorkflowEditor />);
    fireEvent.change(screen.getByLabelText("이름"), { target: { value: "w" } });
    addNode("AGENT");
    addNode("END");

    save();

    const onAgent = await waitFor(() => {
      const el = card("agent-1").querySelectorAll('[data-slot="node-violation"]');
      expect(el.length).toBe(2);
      return [...el].map((e) => e.textContent);
    });
    expect(onAgent).toEqual([
      VIOLATION_SENTENCE.agent_node_without_agent,
      VIOLATION_SENTENCE.orphan_node,
    ]);
    // 다른 카드에는 붙지 않는다.
    expect(card("end-1").querySelectorAll('[data-slot="node-violation"]')).toHaveLength(0);
    // 그래프 수준 자리는 alert 이고 node_id 없는 위반만 든다.
    const graphLevel = document.querySelector('[data-slot="graph-violations"]')!;
    expect(graphLevel.getAttribute("role")).toBe("alert");
    expect(graphLevel.textContent).toContain(VIOLATION_SENTENCE.no_start);
    expect(graphLevel.textContent).not.toContain(VIOLATION_SENTENCE.orphan_node);
  });

  it("C-7: 간선에는 위반을 붙이지 않는다 - 연결 목록에 위반 문장이 없다", async () => {
    createWorkflowAction.mockResolvedValue({
      ok: false,
      message: "m",
      violations: [{ reason: "dangling_edge", nodeId: null }],
    });
    render(<WorkflowEditor />);
    fireEvent.change(screen.getByLabelText("이름"), { target: { value: "w" } });
    addNode("START");
    addNode("END");
    connect("start-1", "end-1");

    save();

    await waitFor(() => expect(document.querySelector('[data-slot="graph-violations"]')).toBeTruthy());
    const edgeList = document.querySelector('[data-slot="edge-list"]')!;
    expect(edgeList.textContent).not.toContain(VIOLATION_SENTENCE.dangling_edge);
  });

  it("잘못된 그래프는 저장되지 않는다: 400 뒤에도 이름·노드·연결이 그대로 남고 이동하지 않는다", async () => {
    createWorkflowAction.mockResolvedValue({
      ok: false,
      message: "그래프가 저장되지 않았습니다.",
      violations: [{ reason: "no_start", nodeId: null }],
    });
    render(<WorkflowEditor />);
    fireEvent.change(screen.getByLabelText("이름"), { target: { value: "triage" } });
    addNode("AGENT");
    addNode("END");
    connect("agent-1", "end-1");

    save();

    await waitFor(() => expect(screen.getByText("그래프가 저장되지 않았습니다.")).toBeTruthy());
    expect((screen.getByLabelText<HTMLInputElement>("이름")).value).toBe("triage");
    expect(cards()).toEqual(["agent-1", "end-1"]);
    expect(screen.getAllByRole("button", { name: /연결 끊기/ })).toHaveLength(1);
    expect(push).not.toHaveBeenCalled();
  });

  it("알 수 없는 사유도 던지지 않고 사유 코드를 보인다", async () => {
    createWorkflowAction.mockResolvedValue({
      ok: false,
      message: "m",
      violations: [{ reason: "brand_new_reason", nodeId: "agent-1" }],
    });
    render(<WorkflowEditor />);
    fireEvent.change(screen.getByLabelText("이름"), { target: { value: "w" } });
    addNode("AGENT");

    save();

    await waitFor(() => expect(card("agent-1").textContent).toContain("brand_new_reason"));
  });

  it("node_id 가 이 캔버스에 없는 위반은 그래프 수준 자리로 간다", async () => {
    createWorkflowAction.mockResolvedValue({
      ok: false,
      message: "m",
      violations: [{ reason: "orphan_node", nodeId: "ghost-9" }],
    });
    render(<WorkflowEditor />);
    fireEvent.change(screen.getByLabelText("이름"), { target: { value: "w" } });
    addNode("START");

    save();

    await waitFor(() =>
      expect(document.querySelector('[data-slot="graph-violations"]')?.textContent).toContain(
        VIOLATION_SENTENCE.orphan_node,
      ),
    );
  });

  it("위반 없는 실패(키·네트워크)는 alert 문장만 보이고 입력은 지워지지 않는다", async () => {
    createWorkflowAction.mockResolvedValue({ ok: false, message: "api 에 닿지 못했습니다." });
    render(<WorkflowEditor />);
    fireEvent.change(screen.getByLabelText("이름"), { target: { value: "w" } });
    addNode("START");

    save();

    await waitFor(() => expect(screen.getByText("api 에 닿지 못했습니다.")).toBeTruthy());
    expect(document.querySelector('[data-slot="graph-violations"]')).toBeNull();
    expect(cards()).toEqual(["start-1"]);
  });

  it("액션이 던져도 문구를 보이지 않고 입력은 남는다", async () => {
    createWorkflowAction.mockRejectedValue(new Error("secret internal detail"));
    render(<WorkflowEditor />);
    fireEvent.change(screen.getByLabelText("이름"), { target: { value: "w" } });
    addNode("START");

    save();

    await waitFor(() => expect(screen.getByText(/저장에 실패했습니다/)).toBeTruthy());
    expect(document.body.textContent).not.toContain("secret internal detail");
    expect(cards()).toEqual(["start-1"]);
  });
});
