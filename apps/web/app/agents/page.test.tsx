import { AetherHttpError } from "@aether/sdk";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const listAgents = vi.fn();
// `AetherHttpError` 는 **실제 클래스**를 그대로 씁니다 — 가짜로 만들면 화면의
// `instanceof` 분기가 테스트에서만 성립하고 실제 SDK 오류에서는 성립하지 않습니다.
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: () => ({ listAgents }),
}));

import Loading from "./loading";
import AgentsPage from "./page";

const ROW = {
  id: "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b",
  name: "billing-helper",
  current_version: 3,
  updated_at: "2026-10-18T11:00:00Z",
};

async function renderPage(cursor?: string) {
  render(await AgentsPage({ searchParams: Promise.resolve(cursor ? { cursor } : {}) }));
}

// MVP-2p: 서버 컴포넌트는 키가 없으면 호출하지 않고 "api 키가 없습니다" 를 그립니다.
// 이 파일의 테스트는 **키가 있는 경우**를 보므로 가짜 키를 꽂습니다(명백한 가짜입니다).
// 키 부재 경로는 app/runs/page.test.tsx 가 따로 봅니다.
beforeEach(() => {
  vi.stubEnv("AETHER_API_KEY", "aeth_test_fake_key");
});
afterEach(() => {
  vi.unstubAllEnvs();
});

describe("/agents", () => {
  beforeEach(() => {
    listAgents.mockReset();
  });
  afterEach(cleanup);

  it("spec 0006 R-5: SDK 응답 고정값으로 행이 렌더된다 (이름, v3, 수정 시각)", async () => {
    listAgents.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();

    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getByText("billing-helper")).toBeTruthy();
    expect(screen.getByText("v3")).toBeTruthy();
    expect(document.querySelector("time")?.getAttribute("title")).toBe("2026-10-18T11:00:00Z");
  });

  it("MVP-2e: 이름 칸은 /agents/{id}/chat 을 가리키는 링크다 (목적지가 생겼다)", async () => {
    listAgents.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();

    const link = screen.getByRole("link", { name: "billing-helper" });
    expect(link.getAttribute("href")).toBe(`/agents/${ROW.id}/chat`);
    // 링크는 이름 칸, 편집, 새 Agent 셋이다 - 다음 쪽 링크는 next_cursor 가 있을 때만 생긴다.
    expect(screen.getAllByRole("link")).toHaveLength(3);
  });

  it("P5-4 R-1: 행마다 /agents/{id}/edit 으로 가는 편집 링크가 있다", async () => {
    listAgents.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();

    const link = screen.getByRole("link", { name: "billing-helper 편집" });
    expect(link.getAttribute("href")).toBe(`/agents/${ROW.id}/edit`);
  });

  it("P5-4 R-1: 새 Agent 를 만드는 길(/agents/new)이 목록 위에 있다", async () => {
    listAgents.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();

    expect(screen.getByRole("link", { name: "새 Agent" }).getAttribute("href")).toBe("/agents/new");
  });

  it("P5-4 R-1: 목록이 비어 있어도 새 Agent 길이 있다 (첫 Agent 를 만들 곳)", async () => {
    listAgents.mockResolvedValue({ items: [], next_cursor: null });
    await renderPage();

    expect(screen.getByRole("link", { name: "새 Agent" }).getAttribute("href")).toBe("/agents/new");
    expect(screen.getByText("아직 Agent 가 없습니다.")).toBeTruthy();
  });

  it("DESIGN 7.1: next_cursor 가 있으면 다음 쪽", async () => {
    listAgents.mockResolvedValue({ items: [ROW], next_cursor: "abc" });
    await renderPage();

    const more = screen.getByRole("link", { name: "다음 쪽" });
    expect(more.getAttribute("href")).toBe("/agents?cursor=abc");
  });

  it("DESIGN 7.1: 마지막 쪽(next_cursor null)에서는 다음 쪽가 없다", async () => {
    listAgents.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();

    expect(screen.queryByText("다음 쪽")).toBeNull();
  });

  it("DESIGN 7: 빈 결과는 표가 아니라 한 줄 안내", async () => {
    listAgents.mockResolvedValue({ items: [], next_cursor: null });
    await renderPage();

    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("아직 Agent 가 없습니다.")).toBeTruthy();
  });

  it("DESIGN 7: 오류는 alert (빈 결과와 다른 화면)", async () => {
    listAgents.mockRejectedValue(new Error("fetch failed"));
    await renderPage();

    expect(screen.getByRole("alert").textContent).toContain("fetch failed");
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByText("아직 Agent 가 없습니다.")).toBeNull();
  });

  it("DESIGN 7.1: 깨진 커서(422)는 오류 상태이고 다음 행동은 처음부터 보기", async () => {
    listAgents.mockRejectedValue(
      new AetherHttpError(
        "aether-sdk: GET /agents?cursor=x failed with status 422 Unprocessable Entity",
        422,
        "Unprocessable Entity",
      ),
    );
    await renderPage("x");

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByRole("link", { name: "처음부터 보기" }).getAttribute("href")).toBe(
      "/agents",
    );
  });

  it("DESIGN 6절: 외부 텍스트는 텍스트로 렌더된다", async () => {
    listAgents.mockResolvedValue({
      items: [{ ...ROW, name: "<img src=x onerror=alert(1)>" }],
      next_cursor: null,
    });
    await renderPage();

    expect(document.querySelector("img")).toBeNull();
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeTruthy();
  });

  it("DESIGN 7: 로딩은 skeleton", () => {
    render(<Loading />);

    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
  });
});
