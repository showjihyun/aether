import { AetherHttpError } from "@aether/sdk";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

const listRuns = vi.fn();
// `AetherHttpError` 는 **실제 클래스**를 그대로 씁니다 — 가짜로 만들면 화면의
// `instanceof` 분기가 테스트에서만 성립하고 실제 SDK 오류에서는 성립하지 않습니다.
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: () => ({ listRuns }),
}));

import Loading from "./loading";
import RunsPage from "./page";

const ROW = {
  run_id: "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b",
  agent_id: "0199ffee-0000-7000-8000-000000000001",
  agent_version: 2,
  status: "succeeded",
  requested_at: "2026-10-18T10:00:00Z",
  requested_by: null,
  started_at: "2026-10-18T10:00:01Z",
  finished_at: "2026-10-18T10:01:13Z",
  failure_reason: null,
  trace_id: null,
  cancel_requested_at: null,
};

async function renderPage(cursor?: string) {
  const ui = await RunsPage({ searchParams: Promise.resolve(cursor ? { cursor } : {}) });
  render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe("/runs", () => {
  beforeEach(() => {
    listRuns.mockReset();
  });
  afterEach(cleanup);

  it("spec 0006 R-5: 행이 렌더된다 (상태 badge, Agent, 시작, 소요)", async () => {
    listRuns.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();

    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getByText("succeeded")).toBeTruthy();
    expect(screen.getByText("0199ffee…")).toBeTruthy();
    expect(screen.getByText("1m 12s")).toBeTruthy();
    expect(document.querySelector("time")?.getAttribute("title")).toBe("2026-10-18T10:00:01Z");
  });

  it("시작하지 않은 Run 은 시작·소요 모두 대시", async () => {
    listRuns.mockResolvedValue({
      items: [{ ...ROW, status: "queued", started_at: null, finished_at: null }],
      next_cursor: null,
    });
    await renderPage();

    expect(screen.getByText("queued")).toBeTruthy();
    expect(screen.getAllByText("—").length).toBe(2);
  });

  it("DESIGN 9절: 상세 화면이 생기기 전까지 행은 링크가 아니다", async () => {
    listRuns.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();

    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });

  it("DESIGN 7.1: next_cursor 가 있으면 다음 쪽", async () => {
    listRuns.mockResolvedValue({ items: [ROW], next_cursor: "abc" });
    await renderPage();

    expect(screen.getByRole("link", { name: "다음 쪽" }).getAttribute("href")).toBe(
      "/runs?cursor=abc",
    );
  });

  it("DESIGN 7.1: 마지막 쪽(next_cursor null)에서는 다음 쪽가 없다", async () => {
    listRuns.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();

    expect(screen.queryByText("다음 쪽")).toBeNull();
  });

  it("DESIGN 7: 빈 결과", async () => {
    listRuns.mockResolvedValue({ items: [], next_cursor: null });
    await renderPage();

    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("아직 Run 이 없습니다.")).toBeTruthy();
  });

  it("DESIGN 7: 오류는 alert", async () => {
    listRuns.mockRejectedValue(new Error("fetch failed"));
    await renderPage();

    expect(screen.getByRole("alert").textContent).toContain("fetch failed");
    expect(screen.queryByText("아직 Run 이 없습니다.")).toBeNull();
  });

  it("DESIGN 7.1: 깨진 커서(422)는 처음부터 보기", async () => {
    listRuns.mockRejectedValue(
      new AetherHttpError(
        "aether-sdk: GET /runs?cursor=x failed with status 422 Unprocessable Entity",
        422,
        "Unprocessable Entity",
      ),
    );
    await renderPage("x");

    expect(screen.getByRole("link", { name: "처음부터 보기" }).getAttribute("href")).toBe("/runs");
  });

  it("빈 커서 쪽은 막다른 길이 아니다 — 처음부터 보기가 있다", async () => {
    // 낡은 커서로 들어온 주소. api 는 422 가 아니라 **빈 쪽**을 줄 수 있고, 그때 머리만
    // 있는 표를 보여주면 사용자가 나갈 길이 없습니다(MVP-2a 리뷰 2026-10-18).
    listRuns.mockResolvedValue({ items: [], next_cursor: null });
    await renderPage("stale");

    expect(screen.getByRole("link", { name: "처음부터 보기" }).getAttribute("href")).toBe("/runs");
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("첫 쪽이 비면 안내 한 줄만 — 갈 곳이 없는 버튼을 만들지 않는다", async () => {
    // DESIGN 7 은 "다음 행동 button 하나" 를 요구하지만 생성 화면이 MVP 범위에 없습니다.
    // 404 로 가는 버튼을 두는 것보다 한 줄이 정직합니다(DESIGN 9절).
    listRuns.mockResolvedValue({ items: [], next_cursor: null });
    await renderPage();

    expect(screen.getByText("아직 Run 이 없습니다.")).toBeTruthy();
    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });

  it("DESIGN 7: 오류의 기술 메시지는 접힌 자리에 있고, 앞에는 할 수 있는 일이 있다", async () => {
    listRuns.mockRejectedValue(
      new AetherHttpError(
        "aether-sdk: GET /runs?cursor=x failed with status 422 Unprocessable Entity",
        422,
        "Unprocessable Entity",
      ),
    );
    await renderPage("x");

    const alert = screen.getByRole("alert");
    // SDK 원문은 details 안에 있습니다 — 사용자가 할 수 있는 일이 그 문장에 없습니다.
    const details = alert.querySelector("details");
    expect(details).not.toBeNull();
    expect(details?.textContent).toContain("failed with status 422");
    expect(details?.open).toBe(false);
  });

  it("DESIGN 7: 로딩은 skeleton", () => {
    render(<Loading />);

    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
  });
});
