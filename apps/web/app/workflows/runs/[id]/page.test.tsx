import { AetherHttpError } from "@aether/sdk";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

const listWorkflowRunNodes = vi.fn();
const createClientSpy = vi.fn();
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: unknown) => {
    createClientSpy(options);
    return { listWorkflowRunNodes };
  },
}));

import Loading from "./loading";
import WorkflowRunPage from "./page";

const ID = "0198aaaa-0000-7000-8000-000000000001";
const OK = {
  node_id: "classify",
  kind: "agent",
  status: "succeeded",
  started_at: "2026-10-18T10:00:01Z",
  finished_at: "2026-10-18T10:00:09Z",
  failure_reason: null,
};
const BAD = {
  node_id: "notify",
  kind: "tool",
  status: "failed",
  started_at: "2026-10-18T10:00:10Z",
  finished_at: "2026-10-18T10:00:11Z",
  failure_reason: "tool_error",
};
const EMPTY = { items: [], next_cursor: null };

async function renderPage(q: { cursor?: string } = {}, id = ID) {
  const ui = await WorkflowRunPage({
    params: Promise.resolve({ id }),
    searchParams: Promise.resolve(q),
  });
  render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe("/workflows/runs/[id]", () => {
  beforeEach(() => {
    listWorkflowRunNodes.mockReset();
    createClientSpy.mockReset();
    vi.stubEnv("AETHER_API_KEY", "aeth_test_fake_key");
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
  });

  it("spec 0007 R-6: 노드가 행이고 이름·종류·상태·시작·종료·실패 사유 열이 있다", async () => {
    listWorkflowRunNodes.mockResolvedValue({ items: [OK, BAD], next_cursor: null });
    await renderPage();

    expect(listWorkflowRunNodes).toHaveBeenCalledWith(ID, { cursor: undefined });
    expect(createClientSpy).toHaveBeenCalledWith(
      expect.objectContaining({ apiKey: "aeth_test_fake_key" }),
    );
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "노드",
      "종류",
      "상태",
      "시작",
      "종료",
      "실패 사유",
    ]);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("classify");
    expect(rows[0]?.textContent).toContain("succeeded");
    expect(rows[0]?.querySelectorAll("time")).toHaveLength(2);
    expect(rows[1]?.textContent).toContain("notify");
    expect(rows[1]?.textContent).toContain("tool_error");
  });

  it("spec 0007 R-6: 실패한 노드는 행 표시와 요약 문장으로 구별되고 성공한 노드는 아니다", async () => {
    listWorkflowRunNodes.mockResolvedValue({ items: [OK, BAD], next_cursor: null });
    await renderPage();

    const rows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
    expect(rows[0]?.getAttribute("data-failed")).toBeNull();
    expect(rows[1]?.getAttribute("data-failed")).toBe("true");
    expect(screen.getByText("실패한 노드 1개")).toBeTruthy();
  });

  it("실패한 노드가 없으면 요약 문장이 없고, 시각이 없으면 대시", async () => {
    listWorkflowRunNodes.mockResolvedValue({
      items: [{ ...OK, status: "running", started_at: null, finished_at: null }],
      next_cursor: null,
    });
    await renderPage();

    expect(screen.queryByText(/실패한 노드/)).toBeNull();
    expect(screen.getAllByText("—")).toHaveLength(3);
  });

  it("spec 0007 D-4: 노드 출력 열이나 자리표시가 없다", async () => {
    listWorkflowRunNodes.mockResolvedValue({ items: [OK], next_cursor: null });
    await renderPage();

    expect(document.body.textContent).not.toMatch(/출력|output|준비 중/i);
  });

  it("커서: 다음 쪽 링크가 cursor 를 가진다", async () => {
    listWorkflowRunNodes.mockResolvedValue({ items: [OK], next_cursor: "n2" });
    await renderPage({ cursor: "n1" });

    expect(listWorkflowRunNodes).toHaveBeenCalledWith(ID, { cursor: "n1" });
    expect(screen.getByRole("link", { name: "다음 쪽" }).getAttribute("href")).toBe(
      `/workflows/runs/${ID}?cursor=n2`,
    );
  });

  it("빈 목록은 표 없이 한 줄이고 오류와 다른 화면이다", async () => {
    listWorkflowRunNodes.mockResolvedValue(EMPTY);
    await renderPage();

    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("아직 실행된 노드가 없습니다.")).toBeTruthy();
  });

  it("빈 커서 쪽은 처음부터 보기가 있다", async () => {
    listWorkflowRunNodes.mockResolvedValue(EMPTY);
    await renderPage({ cursor: "stale" });

    expect(screen.getByRole("link", { name: "처음부터 보기" }).getAttribute("href")).toBe(
      `/workflows/runs/${ID}`,
    );
  });

  it("DESIGN 7: 없는 Workflow Run(404)은 찾을 수 없음이고 목록으로 가는 링크가 있다", async () => {
    listWorkflowRunNodes.mockRejectedValue(
      new AetherHttpError("GET /workflow-runs/x/nodes failed with status 404", 404, "Not Found"),
    );
    await renderPage({}, "x");

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("Workflow 실행을 찾을 수 없습니다");
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByRole("link", { name: "Workflow 목록으로" }).getAttribute("href")).toBe(
      "/workflows",
    );
  });

  it("DESIGN 7: api 에 닿지 못하면 새로고침 안내이고 찾을 수 없음이 아니다", async () => {
    listWorkflowRunNodes.mockRejectedValue(new Error("fetch failed"));
    await renderPage();

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("api 가 떠 있는지 확인한 뒤 새로고침 하세요.");
    expect(alert.textContent).not.toContain("찾을 수 없습니다");
    expect(screen.queryByText("아직 실행된 노드가 없습니다.")).toBeNull();
  });

  it("키가 없으면 호출하지 않는다", async () => {
    vi.stubEnv("AETHER_API_KEY", "");
    await renderPage();

    expect(screen.getByText("api 키가 없습니다")).toBeTruthy();
    expect(listWorkflowRunNodes).not.toHaveBeenCalled();
  });

  it("DESIGN 7: 로딩은 skeleton", () => {
    render(<Loading />);

    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
  });
});
