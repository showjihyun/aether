import { AetherHttpError } from "@aether/sdk";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

const getRun = vi.fn();
const streamRunEvents = vi.fn();
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: () => ({ getRun, streamRunEvents }),
}));

import Loading from "./loading";
import RunPage from "./page";

const RUN = {
  run_id: "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b",
  agent_id: "0199ffee-0000-7000-8000-000000000001",
  agent_version: 2,
  status: "failed",
  requested_at: "2026-10-18T10:00:00Z",
  requested_by: "0199aaaa-0000-7000-8000-000000000009",
  started_at: "2026-10-18T10:00:01Z",
  finished_at: "2026-10-18T10:01:13Z",
  failure_reason: "tool_error",
  trace_id: "0af7651916cd43dd8448eb211c80319c",
  cancel_requested_at: null,
};

async function renderPage(id = RUN.run_id) {
  const ui = await RunPage({ params: Promise.resolve({ id }) });
  render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe("/runs/[id]", () => {
  beforeEach(() => {
    getRun.mockReset();
    streamRunEvents.mockReset();
    // 끝나지 않는 스트림 - 머리 렌더만 본다.
    streamRunEvents.mockReturnValue({
      [Symbol.asyncIterator]: () => ({ next: () => new Promise(() => {}) }),
    });
  });
  afterEach(cleanup);

  it("MVP-2b: 머리에 상태 badge, 실패 사유, trace id, 소요, 시각이 있다", async () => {
    getRun.mockResolvedValue(RUN);
    await renderPage();

    expect(getRun).toHaveBeenCalledWith(RUN.run_id);
    expect(screen.getByText("failed")).toBeTruthy();
    expect(screen.getByText("tool_error")).toBeTruthy();
    expect(screen.getByText("0198a1b2…")).toBeTruthy(); // Run ID
    expect(screen.getByText("0af76519…")).toBeTruthy(); // trace id
    expect(screen.getByText("1m 12s")).toBeTruthy();
    expect(document.querySelectorAll("time").length).toBeGreaterThanOrEqual(3);
  });

  it("requested_by 가 null 이면 Workflow 가 선언한 Run 으로 읽힌다 (500 이 아니다)", async () => {
    getRun.mockResolvedValue({ ...RUN, requested_by: null });
    await renderPage();

    expect(screen.getByText("Workflow 가 선언")).toBeTruthy();
  });

  it("requested_by 가 있으면 그 ID 를 보인다", async () => {
    getRun.mockResolvedValue(RUN);
    await renderPage();

    expect(screen.getByText("0199aaaa…")).toBeTruthy();
    expect(screen.queryByText("Workflow 가 선언")).toBeNull();
  });

  it("시작하지 않은 Run 은 시각과 trace id 자리가 대시이고 실패 사유 줄이 없다", async () => {
    getRun.mockResolvedValue({
      ...RUN,
      status: "queued",
      started_at: null,
      finished_at: null,
      failure_reason: null,
      trace_id: null,
    });
    await renderPage();

    expect(screen.getByText("queued")).toBeTruthy();
    expect(screen.queryByText("tool_error")).toBeNull();
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });

  it("취소 버튼은 없다 (범위 밖)", async () => {
    getRun.mockResolvedValue({ ...RUN, status: "running" });
    await renderPage();

    expect(screen.queryByRole("button", { name: /취소|cancel/i })).toBeNull();
  });

  it("DESIGN 7: 없는 Run(404)은 오류 상태이고, 기술 원문은 접힌 자리에 있다", async () => {
    getRun.mockRejectedValue(
      new AetherHttpError(
        "aether-sdk: GET /runs/x failed with status 404 Not Found",
        404,
        "Not Found",
      ),
    );
    await renderPage("x");

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("Run 을 찾을 수 없습니다");
    expect(alert.querySelector("details")?.textContent).toContain("failed with status 404");
    expect(alert.querySelector("details")?.open).toBe(false);
    expect(screen.getByRole("link", { name: "Run 목록으로" }).getAttribute("href")).toBe("/runs");
  });

  it("DESIGN 7: api 에 닿지 못하면 새로고침 안내이고 첫 문장이 할 수 있는 일이다", async () => {
    getRun.mockRejectedValue(new Error("fetch failed"));
    await renderPage();

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("api 가 떠 있는지 확인한 뒤 새로고침 하세요.");
    expect(alert.querySelector("details")?.textContent).toContain("fetch failed");
    expect(alert.textContent).not.toContain("찾을 수 없습니다");
  });

  it("DESIGN 7: 로딩은 skeleton", () => {
    render(<Loading />);

    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
  });
});
