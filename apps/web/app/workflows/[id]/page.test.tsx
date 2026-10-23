import { AetherHttpError } from "@aether/sdk";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const getWorkflow = vi.fn();
const createClientSpy = vi.fn();
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: unknown) => {
    createClientSpy(options);
    return { getWorkflow };
  },
}));

import Loading from "./loading";
import WorkflowPage from "./page";

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

const ID = "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b";
const WF = {
  id: ID,
  name: "triage-flow",
  current_version: 4,
  nodes: [
    { id: "start", kind: "START" },
    { id: "classify", kind: "AGENT" },
    { id: "end", kind: "END" },
  ],
  edges: [
    { source: "start", target: "classify" },
    { source: "classify", target: "end", label: "ok" },
  ],
};

async function renderPage(id = ID) {
  const ui = await WorkflowPage({ params: Promise.resolve({ id }) });
  return render(ui);
}

describe("/workflows/[id] (spec 0007 R-9·R-10·R-12, D-9)", () => {
  beforeEach(() => {
    getWorkflow.mockReset();
    createClientSpy.mockReset();
    vi.stubEnv("AETHER_API_KEY", "aeth_test_fake_key");
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
  });

  it("D-15: 서버에서 서버 키로 SDK 를 직접 부른다(중계를 거치지 않는다)", async () => {
    getWorkflow.mockResolvedValue(WF);
    await renderPage();
    expect(createClientSpy).toHaveBeenCalledWith(
      expect.objectContaining({ apiKey: "aeth_test_fake_key" }),
    );
    expect(getWorkflow).toHaveBeenCalledWith(ID);
  });

  it("P5-5: 머리에 이름과 현재 Version badge, 노드·간선 수만큼 그려진다", async () => {
    getWorkflow.mockResolvedValue(WF);
    const { container } = await renderPage();
    expect(screen.getByRole("heading", { name: "triage-flow" })).toBeTruthy();
    const badge = screen.getByText("v4");
    expect(badge.getAttribute("data-slot")).toBe("badge");
    expect(badge.getAttribute("data-variant")).toBe("outline");
    expect(container.querySelectorAll(".react-flow__node")).toHaveLength(3);
    expect(container.querySelectorAll(".react-flow__edge")).toHaveLength(2);
  });

  it("R-12: 배치가 자동이고 위치가 저장되지 않는다는 문장이 화면에 있다", async () => {
    getWorkflow.mockResolvedValue(WF);
    await renderPage();
    expect(document.body.textContent).toContain(
      "배치는 자동이라 열 때마다 달라질 수 있습니다. 노드 위치는 저장되지 않습니다",
    );
  });

  it("DESIGN 7: 404 는 없다고 말하고 목록으로 가는 길을 준다", async () => {
    getWorkflow.mockRejectedValue(new AetherHttpError("x 404", 404, "Not Found"));
    await renderPage();
    expect(screen.getByText("Workflow 를 찾을 수 없습니다")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Workflow 목록으로" }).getAttribute("href")).toBe(
      "/workflows",
    );
  });

  it("DESIGN 7: 그 밖의 오류는 일반 오류 문구와 기술 정보", async () => {
    getWorkflow.mockRejectedValue(new Error("boom"));
    await renderPage();
    expect(screen.getByText("Workflow 를 불러오지 못했습니다")).toBeTruthy();
    expect(screen.getByText("boom")).toBeTruthy();
  });

  it("DESIGN 7: 노드 0개는 빈 결과 한 줄이고 캔버스를 그리지 않는다", async () => {
    getWorkflow.mockResolvedValue({ ...WF, nodes: [], edges: [] });
    const { container } = await renderPage();
    expect(screen.getByText("이 Workflow 에는 아직 노드가 없습니다.")).toBeTruthy();
    expect(container.querySelector(".react-flow")).toBeNull();
  });

  it("DESIGN 7: 키가 없으면 호출하지 않는다", async () => {
    vi.stubEnv("AETHER_API_KEY", "");
    await renderPage();
    expect(screen.getByText("api 키가 없습니다")).toBeTruthy();
    expect(getWorkflow).not.toHaveBeenCalled();
  });

  it("경로 조각이 든 id 로는 api 를 부르지 않는다(없는 Workflow 와 같은 화면)", async () => {
    await renderPage("../agents");
    expect(getWorkflow).not.toHaveBeenCalled();
    expect(screen.getByText("Workflow 를 찾을 수 없습니다")).toBeTruthy();
  });

  it("DESIGN 7: 로딩은 skeleton", () => {
    render(<Loading />);
    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
  });
});
