import { AetherHttpError } from "@aether/sdk";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

const listIngestions = vi.fn();
const createClientSpy = vi.fn();
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: unknown) => {
    createClientSpy(options);
    return { listIngestions };
  },
}));

import Loading from "./loading";
import IngestionsPage from "./page";

const SET_ID = "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b";
const ROW = {
  ingestion_id: "0199ffee-0000-7000-8000-000000000001",
  knowledge_set_id: SET_ID,
  source: "wiki/onboarding.md",
  status: "succeeded",
  requested_at: "2026-10-18T10:00:00Z",
  started_at: "2026-10-18T10:00:01Z",
  finished_at: "2026-10-18T10:01:13Z",
  failure_reason: null,
};

async function renderPage(cursor?: string) {
  const ui = await IngestionsPage({
    params: Promise.resolve({ id: SET_ID }),
    searchParams: Promise.resolve(cursor ? { cursor } : {}),
  });
  render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe("/knowledge/[id]", () => {
  beforeEach(() => {
    listIngestions.mockReset();
    createClientSpy.mockReset();
    vi.stubEnv("AETHER_API_KEY", "aeth_test_fake_key");
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
  });

  it("D-15: 서버 키를 SDK 에 넘기고, 세트 id 로 적재를 부른다", async () => {
    listIngestions.mockResolvedValue({ items: [], next_cursor: null });
    await renderPage("c1");
    expect(createClientSpy).toHaveBeenCalledWith(
      expect.objectContaining({ apiKey: "aeth_test_fake_key" }),
    );
    expect(listIngestions).toHaveBeenCalledWith(SET_ID, { cursor: "c1" });
  });

  it("spec 0006 R-5: 열은 source·상태·요청·소요이고 청크 수 열은 없다", async () => {
    listIngestions.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();

    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "source",
      "상태",
      "요청",
      "소요",
    ]);
    expect(screen.getByText("wiki/onboarding.md")).toBeTruthy();
    expect(screen.getByText("succeeded")).toBeTruthy();
    expect(screen.getByText("1m 12s")).toBeTruthy();
    expect(document.querySelector("time")?.getAttribute("title")).toBe("2026-10-18T10:00:00Z");
  });

  it("DESIGN 6: source 는 외부 텍스트 — 마크업으로 해석되지 않고 글자 그대로 나온다", async () => {
    const evil = '<img src=x onerror="alert(1)">';
    listIngestions.mockResolvedValue({ items: [{ ...ROW, source: evil }], next_cursor: null });
    await renderPage();

    expect(document.querySelector("img")).toBeNull();
    expect(screen.getByText(evil)).toBeTruthy();
  });

  it("failure_reason 이 있으면 그 행에 font-mono text-xs 로 보인다", async () => {
    listIngestions.mockResolvedValue({
      items: [{ ...ROW, status: "failed", failure_reason: "embedding_unavailable" }],
      next_cursor: null,
    });
    await renderPage();

    const reason = screen.getByText("embedding_unavailable");
    expect(reason.className).toContain("font-mono");
    expect(reason.className).toContain("text-xs");
    expect(reason.closest("tr")?.textContent).toContain("failed");
  });

  it("failure_reason 이 없으면 사유 자리를 만들지 않는다", async () => {
    listIngestions.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();
    expect(document.querySelectorAll("tbody td .font-mono").length).toBe(0);
  });

  it("시작하지 않은 적재는 소요가 대시", async () => {
    listIngestions.mockResolvedValue({
      items: [{ ...ROW, status: "queued", started_at: null, finished_at: null }],
      next_cursor: null,
    });
    await renderPage();
    expect(screen.getByText("queued")).toBeTruthy();
    expect(screen.getByText("—")).toBeTruthy();
  });

  it("세트 이름은 보이지 않고, /knowledge 로 돌아가는 링크가 있다", async () => {
    listIngestions.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();
    const back = screen.getByRole("link", { name: /Knowledge/ });
    expect(back.getAttribute("href")).toBe("/knowledge");
  });

  it("돌아가는 링크는 빈 결과·오류에서도 있다", async () => {
    listIngestions.mockResolvedValue({ items: [], next_cursor: null });
    await renderPage();
    expect(screen.getByRole("link", { name: /Knowledge/ }).getAttribute("href")).toBe("/knowledge");
    expect(screen.getByText("아직 적재가 없습니다.")).toBeTruthy();
    cleanup();
    listIngestions.mockRejectedValue(new Error("boom"));
    await renderPage();
    expect(screen.getByRole("link", { name: /Knowledge/ }).getAttribute("href")).toBe("/knowledge");
    expect(screen.getByRole("alert").textContent).toContain("boom");
  });

  it("DESIGN 7.1: 다음 쪽 링크는 이 세트의 주소를 가리킨다", async () => {
    listIngestions.mockResolvedValue({ items: [ROW], next_cursor: "abc" });
    await renderPage();
    expect(screen.getByRole("link", { name: "다음 쪽" }).getAttribute("href")).toBe(
      `/knowledge/${SET_ID}?cursor=abc`,
    );
  });

  it("DESIGN 7.1: 깨진 커서(422)는 이 세트의 처음부터 보기", async () => {
    listIngestions.mockRejectedValue(new AetherHttpError("x 422", 422, "Unprocessable Entity"));
    await renderPage("x");
    expect(screen.getByRole("link", { name: "처음부터 보기" }).getAttribute("href")).toBe(
      `/knowledge/${SET_ID}`,
    );
  });

  it("빈 커서 쪽은 처음부터 보기가 있다", async () => {
    listIngestions.mockResolvedValue({ items: [], next_cursor: null });
    await renderPage("stale");
    expect(screen.getByRole("link", { name: "처음부터 보기" }).getAttribute("href")).toBe(
      `/knowledge/${SET_ID}`,
    );
  });

  it("키가 없으면 호출하지 않는다", async () => {
    vi.stubEnv("AETHER_API_KEY", "");
    await renderPage();
    expect(screen.getByText("api 키가 없습니다")).toBeTruthy();
    expect(listIngestions).not.toHaveBeenCalled();
  });

  it("DESIGN 7: 로딩은 skeleton", () => {
    render(<Loading />);
    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
  });

  it("리뷰: 없는 세트(404)는 '찾을 수 없다' 고 말한다 — api 가 떠 있는지 묻지 않는다", async () => {
    // 404 는 "세트가 없다" 이고 다음 행동은 **목록으로 돌아가기** 입니다. 일반 오류 문구
    // ("api 가 떠 있는지 확인한 뒤 새로고침")는 떠 있는 api 에 대해 틀린 지시입니다.
    // 같은 저장소의 `/runs/{id}` 가 이미 상태 코드 필드로 그 분기를 하고 있습니다
    // (`RunDetailError`). api 는 이 경우 404 `knowledge_set_not_found` 를 줍니다
    // (`adapters/inbound/http/listings.py`).
    listIngestions.mockRejectedValue(
      new AetherHttpError(
        "aether-sdk: GET /knowledge-sets/x/ingestions failed with status 404 Not Found",
        404,
        "Not Found",
      ),
    );
    await renderPage();

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("찾을 수 없습니다");
    expect(alert.textContent).not.toContain("api 가 떠 있는지");
    expect(screen.getByRole("link", { name: "Knowledge 목록으로" }).getAttribute("href")).toBe(
      "/knowledge",
    );
    // 원문은 접힌 자리(DESIGN 7).
    const details = alert.querySelector("details");
    expect(details?.open).toBe(false);
    expect(details?.textContent).toContain("status 404");
  });

});
