import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const healthz = vi.fn();
const createClientSpy = vi.fn();
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: unknown) => {
    createClientSpy(options);
    return { healthz };
  },
}));

import SettingsPage from "./page";

// 명백한 가짜 값입니다. 화면 어디에도 나오면 안 됩니다.
const FAKE_KEY = "aeth_SECRET_fake_key_0123456789";
const FAKE_INTERNAL_URL = "http://internal-api.fake.invalid:9999";

async function renderPage() {
  render(await SettingsPage());
}

const everything = () => document.body.textContent + "\n" + document.body.innerHTML;

describe("/settings", () => {
  beforeEach(() => {
    healthz.mockReset();
    createClientSpy.mockReset();
    healthz.mockResolvedValue({ status: "ok", service: "aether-api", version: "1.2.3" });
    vi.stubEnv("AETHER_API_KEY", FAKE_KEY);
    vi.stubEnv("AETHER_API_URL", FAKE_INTERNAL_URL);
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
  });

  it("D-13: card 셋 — 테마, 연결, 키 안내", async () => {
    await renderPage();
    const cards = [...document.querySelectorAll("[data-slot='card']")];
    expect(cards).toHaveLength(3);
    expect(cards.map((c) => c.querySelector("[data-slot='card-title']")?.textContent)).toEqual([
      "테마",
      "연결",
      "키 안내",
    ]);
    expect(screen.getByRole("button", { name: "테마 전환" })).toBeTruthy();
  });

  it("D-13: 연결 card 는 /healthz 의 status·service·version 을 보인다", async () => {
    await renderPage();
    expect(screen.getByText("ok")).toBeTruthy();
    expect(screen.getByText("aether-api")).toBeTruthy();
    expect(screen.getByText("1.2.3")).toBeTruthy();
  });

  it("D-15: 보이는 api 주소는 /api/aether 이고 서버 쪽 AETHER_API_URL 은 나오지 않는다", async () => {
    await renderPage();
    expect(screen.getByText("/api/aether")).toBeTruthy();
    expect(everything()).not.toContain("internal-api.fake.invalid");
    expect(everything()).not.toContain("9999");
  });

  it("D-13: 화면 어디에도 AETHER_API_KEY 의 값이 나오지 않고 healthz 에도 키를 넘기지 않는다", async () => {
    await renderPage();
    expect(document.body.textContent).not.toContain(FAKE_KEY);
    expect(document.body.innerHTML).not.toContain(FAKE_KEY);
    expect(document.body.innerHTML).not.toContain("SECRET");
    expect(JSON.stringify(createClientSpy.mock.calls)).not.toContain(FAKE_KEY);
  });

  it("D-13: 오류 화면에서도 키·내부 주소가 나오지 않는다", async () => {
    healthz.mockRejectedValue(new Error("fetch failed"));
    await renderPage();
    expect(screen.getByRole("alert").textContent).toContain("fetch failed");
    expect(everything()).not.toContain(FAKE_KEY);
    expect(everything()).not.toContain("internal-api.fake.invalid");
    expect(screen.getByText("/api/aether")).toBeTruthy();
    expect(screen.getByRole("button", { name: "테마 전환" })).toBeTruthy();
  });

  it("D-13: 키 안내는 발급 명령 한 줄과 안내문이고 입력창·발급 버튼이 없다", async () => {
    await renderPage();
    const pre = document.querySelector("pre");
    expect(pre?.textContent).toBe(
      "docker compose -f infra/docker/compose.yaml exec api aether-api keys create --label web",
    );
    expect(pre?.className).toContain("font-mono");
    expect(pre?.className).toContain("text-xs");
    expect(document.body.textContent).toContain("한 번만 출력됩니다");
    expect(document.body.textContent).toContain("AETHER_WEB_API_KEY");

    expect(document.querySelectorAll("input, textarea, select, form")).toHaveLength(0);
    // 버튼은 테마 전환 하나뿐입니다.
    const names = screen.getAllByRole("button").map((b) => b.getAttribute("aria-label"));
    expect(names).toEqual(["테마 전환"]);
  });

  it("D-13: 키가 없어도 화면이 뜨고 MissingApiKey 로 막지 않는다", async () => {
    vi.stubEnv("AETHER_API_KEY", "");
    await renderPage();
    expect(screen.queryByText("api 키가 없습니다")).toBeNull();
    expect(document.querySelectorAll("[data-slot='card']")).toHaveLength(3);
    expect(healthz).toHaveBeenCalled();
  });
});
