import { AetherHttpError } from "@aether/sdk";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

const listKnowledgeSets = vi.fn();
const createClientSpy = vi.fn();
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: unknown) => {
    createClientSpy(options);
    return { listKnowledgeSets };
  },
}));

import Loading from "./loading";
import KnowledgePage from "./page";

const ROW = {
  id: "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b",
  name: "사내 위키",
  created_at: "2026-10-18T10:00:00Z",
};

async function renderPage(cursor?: string) {
  const ui = await KnowledgePage({ searchParams: Promise.resolve(cursor ? { cursor } : {}) });
  render(<TooltipProvider>{ui}</TooltipProvider>);
}

describe("/knowledge", () => {
  beforeEach(() => {
    listKnowledgeSets.mockReset();
    createClientSpy.mockReset();
    vi.stubEnv("AETHER_API_KEY", "aeth_test_fake_key");
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
  });

  it("D-15: 서버 컴포넌트는 서버 키를 SDK 에 넘긴다", async () => {
    listKnowledgeSets.mockResolvedValue({ items: [], next_cursor: null });
    await renderPage();
    expect(createClientSpy).toHaveBeenCalledWith(
      expect.objectContaining({ apiKey: "aeth_test_fake_key" }),
    );
  });

  it("spec 0006 R-5: 행이 렌더된다 (이름, 생성) 그리고 열은 둘뿐이다", async () => {
    listKnowledgeSets.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();

    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["이름", "생성"]);
    expect(screen.getByText("사내 위키")).toBeTruthy();
    expect(document.querySelector("time")?.getAttribute("title")).toBe("2026-10-18T10:00:00Z");
  });

  it("MVP-2c: 이름 칸이 적재 목록으로 가는 링크다", async () => {
    listKnowledgeSets.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();

    const link = screen.getByRole("link", { name: "사내 위키" });
    expect(link.getAttribute("href")).toBe(`/knowledge/${ROW.id}`);
  });

  it("DESIGN 7.1: next_cursor 가 있으면 다음 쪽", async () => {
    listKnowledgeSets.mockResolvedValue({ items: [ROW], next_cursor: "abc" });
    await renderPage();
    expect(screen.getByRole("link", { name: "다음 쪽" }).getAttribute("href")).toBe(
      "/knowledge?cursor=abc",
    );
  });

  it("DESIGN 7.1: 마지막 쪽에서는 다음 쪽이 없다", async () => {
    listKnowledgeSets.mockResolvedValue({ items: [ROW], next_cursor: null });
    await renderPage();
    expect(screen.queryByText("다음 쪽")).toBeNull();
  });

  it("DESIGN 7: 첫 쪽이 비면 안내 한 줄만", async () => {
    listKnowledgeSets.mockResolvedValue({ items: [], next_cursor: null });
    await renderPage();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByText("아직 Knowledge 세트가 없습니다.")).toBeTruthy();
    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });

  it("빈 커서 쪽은 막다른 길이 아니다 — 처음부터 보기", async () => {
    listKnowledgeSets.mockResolvedValue({ items: [], next_cursor: null });
    await renderPage("stale");
    expect(screen.getByRole("link", { name: "처음부터 보기" }).getAttribute("href")).toBe("/knowledge");
  });

  it("DESIGN 7: 오류는 alert", async () => {
    listKnowledgeSets.mockRejectedValue(new Error("fetch failed"));
    await renderPage();
    expect(screen.getByRole("alert").textContent).toContain("fetch failed");
  });

  it("DESIGN 7.1: 깨진 커서(422)는 처음부터 보기", async () => {
    listKnowledgeSets.mockRejectedValue(new AetherHttpError("x 422", 422, "Unprocessable Entity"));
    await renderPage("x");
    expect(screen.getByRole("link", { name: "처음부터 보기" }).getAttribute("href")).toBe("/knowledge");
  });

  it("키가 없으면 호출하지 않고 그 사실을 말한다", async () => {
    vi.stubEnv("AETHER_API_KEY", "");
    await renderPage();
    expect(screen.getByText("api 키가 없습니다")).toBeTruthy();
    expect(listKnowledgeSets).not.toHaveBeenCalled();
  });

  it("DESIGN 7: 로딩은 skeleton", () => {
    render(<Loading />);
    expect(document.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
  });
});
