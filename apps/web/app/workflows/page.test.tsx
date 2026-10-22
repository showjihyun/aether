import { AetherHttpError } from "@aether/sdk";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

const listWorkflows = vi.fn();
const listWorkflowRuns = vi.fn();
const createClientSpy = vi.fn();
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: unknown) => {
    createClientSpy(options);
    return { listWorkflows, listWorkflowRuns };
  },
}));

import Loading from "./loading";
import WorkflowsPage from "./page";

const DEF = {
  id: "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b",
  name: "triage-flow",
  current_version: 4,
  created_at: "2026-10-18T09:00:00Z",
  updated_at: "2026-10-18T11:00:00Z",
};
const RUN = {
  workflow_run_id: "0198aaaa-0000-7000-8000-000000000001",
  workflow_id: DEF.id,
  workflow_version: 4,
  workflow_version_id: "0198bbbb-0000-7000-8000-000000000001",
  status: "running",
  current_node_id: "classify",
  waiting_run_id: null,
  waiting_node_execution_id: null,
  wake_at: null,
  requested_at: "2026-10-18T10:00:00Z",
  started_at: "2026-10-18T10:00:01Z",
  finished_at: null,
  failure_reason: null,
};
const EMPTY = { items: [], next_cursor: null };

async function renderPage(q: { cursor?: string; runsCursor?: string } = {}) {
  const ui = await WorkflowsPage({ searchParams: Promise.resolve(q) });
  render(<TooltipProvider>{ui}</TooltipProvider>);
}

function tables() {
  const [defs, runs] = screen.getAllByRole("table");
  if (!defs || !runs) throw new Error("expected two tables");
  return { defs, runs };
}

const headers = (t: HTMLElement) => within(t).getAllByRole("columnheader").map((h) => h.textContent);

describe("/workflows", () => {
  beforeEach(() => {
    listWorkflows.mockReset();
    listWorkflowRuns.mockReset();
    createClientSpy.mockReset();
    vi.stubEnv("AETHER_API_KEY", "aeth_test_fake_key");
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
  });

  it("D-15: 서버 키를 SDK 에 넘긴다", async () => {
    listWorkflows.mockResolvedValue(EMPTY);
    listWorkflowRuns.mockResolvedValue(EMPTY);
    await renderPage();
    expect(createClientSpy).toHaveBeenCalledWith(
      expect.objectContaining({ apiKey: "aeth_test_fake_key" }),
    );
  });

  it("spec 0006 R-5: 표 둘 — 정의(이름·현재 Version·수정)와 실행(상태·현재 노드·기다리는 대상·요청)", async () => {
    listWorkflows.mockResolvedValue({ items: [DEF], next_cursor: null });
    listWorkflowRuns.mockResolvedValue({ items: [RUN], next_cursor: null });
    await renderPage();

    const { defs, runs } = tables();
    expect(headers(defs)).toEqual(["이름", "현재 Version", "수정"]);
    expect(headers(runs)).toEqual(["상태", "현재 노드", "기다리는 대상", "요청"]);
    expect(within(defs).getByText("triage-flow")).toBeTruthy();
    const badge = within(defs).getByText("v4");
    expect(badge.getAttribute("data-slot")).toBe("badge");
    expect(badge.getAttribute("data-variant")).toBe("outline");
    expect(within(defs).getByText("수정", { selector: "th" })).toBeTruthy();
    expect(defs.querySelector("time")?.getAttribute("title")).toBe(DEF.updated_at);
    expect(within(runs).getByText("running")).toBeTruthy();
    expect(within(runs).getByText("classify")).toBeTruthy();
    expect(runs.querySelector("tbody time")?.getAttribute("title")).toBe(RUN.requested_at);
  });

  it("현재 노드와 기다리는 대상이 없으면 둘 다 대시", async () => {
    listWorkflows.mockResolvedValue(EMPTY);
    listWorkflowRuns.mockResolvedValue({
      items: [{ ...RUN, status: "queued", current_node_id: null }],
      next_cursor: null,
    });
    await renderPage();
    expect(screen.getAllByText("—")).toHaveLength(2);
  });

  it("기다리는 대상: 있는 것만 보인다 (자식 Run / 노드 실행 / 시각)", async () => {
    listWorkflows.mockResolvedValue(EMPTY);
    listWorkflowRuns.mockResolvedValue({
      items: [
        { ...RUN, status: "waiting_run", waiting_run_id: "aaaaaaaa-1111-7000-8000-000000000000" },
        {
          ...RUN,
          workflow_run_id: "r2",
          status: "waiting_approval",
          waiting_node_execution_id: "bbbbbbbb-2222-7000-8000-000000000000",
        },
        { ...RUN, workflow_run_id: "r3", status: "waiting_timer", wake_at: "2026-10-18T12:00:00Z" },
      ],
      next_cursor: null,
    });
    await renderPage();

    const rows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    expect(rows[0]?.textContent).toContain("aaaaaaaa…");
    expect(rows[0]?.textContent).not.toContain("bbbbbbbb");
    // 시각은 요청 칸의 것 하나뿐 — wake_at 이 없으면 기다리는 대상에 시각이 생기지 않는다.
    expect(rows[0]?.querySelectorAll("time")).toHaveLength(1);
    expect(rows[1]?.textContent).toContain("bbbbbbbb…");
    expect(rows[1]?.textContent).not.toContain("aaaaaaaa");
    const wake = [...rows[2]!.querySelectorAll("time")].map((t) => t.getAttribute("title"));
    expect(wake).toContain("2026-10-18T12:00:00Z");
    expect(wake).toHaveLength(2);
    expect(rows[2]?.textContent).not.toContain("…");
    // 셋이 동시에 와도 있는 것은 전부 보인다.
    cleanup();
    listWorkflowRuns.mockResolvedValue({
      items: [
        {
          ...RUN,
          waiting_run_id: "aaaaaaaa-1111-7000-8000-000000000000",
          waiting_node_execution_id: "bbbbbbbb-2222-7000-8000-000000000000",
          wake_at: "2026-10-18T12:00:00Z",
        },
      ],
      next_cursor: null,
    });
    await renderPage();
    const all = screen.getAllByRole("row")[1]?.textContent ?? "";
    expect(all).toContain("aaaaaaaa…");
    expect(all).toContain("bbbbbbbb…");
  });

  it("DESIGN 9: 노드 실행 목록과 자리표시를 만들지 않는다 (표는 정확히 둘)", async () => {
    listWorkflows.mockResolvedValue({ items: [DEF], next_cursor: null });
    listWorkflowRuns.mockResolvedValue({ items: [RUN], next_cursor: null });
    await renderPage();
    expect(screen.getAllByRole("table")).toHaveLength(2);
    expect(document.body.textContent).not.toContain("준비 중");
    expect(document.body.textContent).not.toMatch(/노드 실행 목록/);
  });

  it("커서 둘: 정의의 다음 쪽은 runsCursor 를 보존하고 ? 가 한 번만 나온다", async () => {
    listWorkflows.mockResolvedValue({ items: [DEF], next_cursor: "d2" });
    listWorkflowRuns.mockResolvedValue({ items: [RUN], next_cursor: null });
    await renderPage({ runsCursor: "r1" });

    expect(listWorkflows).toHaveBeenCalledWith({ cursor: undefined });
    expect(listWorkflowRuns).toHaveBeenCalledWith({ cursor: "r1" });
    const href = screen.getByRole("link", { name: "다음 쪽" }).getAttribute("href");
    expect(href).toBe("/workflows?runsCursor=r1&cursor=d2");
    expect(href?.match(/\?/g)).toHaveLength(1);
  });

  it("커서 둘: 실행의 다음 쪽은 정의의 cursor 를 보존한다", async () => {
    listWorkflows.mockResolvedValue({ items: [DEF], next_cursor: null });
    listWorkflowRuns.mockResolvedValue({ items: [RUN], next_cursor: "r2" });
    await renderPage({ cursor: "d1" });

    expect(listWorkflows).toHaveBeenCalledWith({ cursor: "d1" });
    expect(listWorkflowRuns).toHaveBeenCalledWith({ cursor: undefined });
    expect(screen.getByRole("link", { name: "다음 쪽" }).getAttribute("href")).toBe(
      "/workflows?cursor=d1&runsCursor=r2",
    );
  });

  it("커서 둘: 상대편 커서가 없으면 자기 것만 붙는다", async () => {
    listWorkflows.mockResolvedValue({ items: [DEF], next_cursor: null });
    listWorkflowRuns.mockResolvedValue({ items: [RUN], next_cursor: "r2" });
    await renderPage();
    expect(screen.getByRole("link", { name: "다음 쪽" }).getAttribute("href")).toBe(
      "/workflows?runsCursor=r2",
    );
  });

  it("한 표의 오류가 다른 표를 지우지 않는다 (정의 실패, 실행 성공)", async () => {
    listWorkflows.mockRejectedValue(new Error("defs boom"));
    listWorkflowRuns.mockResolvedValue({ items: [RUN], next_cursor: null });
    await renderPage();

    expect(screen.getByRole("alert").textContent).toContain("defs boom");
    expect(screen.getAllByRole("table")).toHaveLength(1);
    expect(screen.getByText("classify")).toBeTruthy();
  });

  it("한 표의 오류가 다른 표를 지우지 않는다 (정의 성공, 실행 실패)", async () => {
    listWorkflows.mockResolvedValue({ items: [DEF], next_cursor: null });
    listWorkflowRuns.mockRejectedValue(new Error("runs boom"));
    await renderPage();

    expect(screen.getByRole("alert").textContent).toContain("runs boom");
    expect(screen.getAllByRole("table")).toHaveLength(1);
    expect(screen.getByText("triage-flow")).toBeTruthy();
  });

  it("DESIGN 7.1: 깨진 커서의 처음부터 보기는 상대편 커서를 보존한다", async () => {
    listWorkflows.mockRejectedValue(new AetherHttpError("x 422", 422, "Unprocessable Entity"));
    listWorkflowRuns.mockResolvedValue({ items: [RUN], next_cursor: null });
    await renderPage({ cursor: "bad", runsCursor: "r1" });
    expect(screen.getByRole("link", { name: "처음부터 보기" }).getAttribute("href")).toBe(
      "/workflows?runsCursor=r1",
    );
  });

  it("DESIGN 7: 빈 결과는 표마다 한 줄", async () => {
    listWorkflows.mockResolvedValue(EMPTY);
    listWorkflowRuns.mockResolvedValue(EMPTY);
    await renderPage();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByText("아직 Workflow 가 없습니다.")).toBeTruthy();
    expect(screen.getByText("아직 Workflow 실행이 없습니다.")).toBeTruthy();
    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });

  it("빈 커서 쪽은 처음부터 보기가 있다", async () => {
    listWorkflows.mockResolvedValue({ items: [DEF], next_cursor: null });
    listWorkflowRuns.mockResolvedValue(EMPTY);
    await renderPage({ cursor: "d1", runsCursor: "stale" });
    expect(screen.getByRole("link", { name: "처음부터 보기" }).getAttribute("href")).toBe(
      "/workflows?cursor=d1",
    );
  });

  it("키가 없으면 호출하지 않는다", async () => {
    vi.stubEnv("AETHER_API_KEY", "");
    await renderPage();
    expect(screen.getByText("api 키가 없습니다")).toBeTruthy();
    expect(listWorkflows).not.toHaveBeenCalled();
    expect(listWorkflowRuns).not.toHaveBeenCalled();
  });

  it("DESIGN 7: 로딩은 skeleton", () => {
    render(<Loading />);
    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
  });

  it("리뷰: 기다리는 대상은 무엇을 기다리는지 말한다 (id 두 종류가 똑같이 보이지 않는다)", async () => {
    // `waiting_run_id` 와 `waiting_node_execution_id` 는 둘 다 `CopyableId` 로 그려집니다 —
    // 라벨이 없으면 "자식 Run 을 기다림" 과 "노드 실행을 기다림" 이 화면에서 **구별되지
    // 않습니다**. 상태 badge 도 갈라주지 않습니다(`waiting_approval` 은 노드 실행 id 와 함께
    // 옵니다). 보는 사람이 다음에 어디를 열어야 하는지가 달라지므로 라벨이 필요합니다.
    listWorkflows.mockResolvedValue(EMPTY);
    listWorkflowRuns.mockResolvedValue({
      items: [
        { ...RUN, status: "waiting_run", waiting_run_id: "aaaaaaaa-1111-7000-8000-000000000000" },
        {
          ...RUN,
          workflow_run_id: "r2",
          status: "waiting_approval",
          waiting_node_execution_id: "bbbbbbbb-2222-7000-8000-000000000000",
        },
        { ...RUN, workflow_run_id: "r3", status: "waiting_timer", wake_at: "2026-10-18T12:00:00Z" },
      ],
      next_cursor: null,
    });
    await renderPage();

    const rows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
    const waitingCell = (row: HTMLElement) => within(row).getAllByRole("cell")[2]?.textContent ?? "";
    expect(waitingCell(rows[0]!)).toContain("자식 Run");
    expect(waitingCell(rows[1]!)).toContain("노드 실행");
    expect(waitingCell(rows[2]!)).toContain("깨어남");
    // 두 id 칸이 라벨 말고는 같은 모양이므로, 라벨이 빠지면 이 단언이 깨집니다.
    expect(waitingCell(rows[0]!)).not.toContain("노드 실행");
    expect(waitingCell(rows[1]!)).not.toContain("자식 Run");
  });

  it("spec 0007 R-6: 실행 행에서 노드 상세로 가는 링크가 있다", async () => {
    listWorkflows.mockResolvedValue(EMPTY);
    listWorkflowRuns.mockResolvedValue({ items: [RUN], next_cursor: null });
    await renderPage();

    expect(
      within(screen.getByRole("table")).getByRole("link", { name: "노드 보기" }).getAttribute("href"),
    ).toBe(`/workflows/runs/${RUN.workflow_run_id}`);
  });

});
