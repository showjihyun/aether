import { AetherHttpError } from "@aether/sdk";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getAgent = vi.fn();
const createClient = vi.fn<(options: Record<string, unknown>) => void>();
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: Record<string, unknown>) => {
    createClient(options);
    return { getAgent };
  },
}));
vi.mock("../../actions", () => ({ createAgentAction: vi.fn(), updateAgentAction: vi.fn() }));

import EditAgentPage, { dynamic } from "./page";

const KEY = "aeth_test_fake_key";
const AGENT = {
  id: "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b",
  name: "billing-helper",
  current_version: 3,
  definition: { schema_version: 1, system_prompt: "old prompt", model: { id: "old-model" } },
};

async function renderPage(id = AGENT.id) {
  render(await EditAgentPage({ params: Promise.resolve({ id }) }));
}

beforeEach(() => {
  getAgent.mockReset();
  createClient.mockClear();
  vi.stubEnv("AETHER_API_KEY", KEY);
  vi.stubEnv("AETHER_API_URL", "http://api.test:8000");
});
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe("/agents/[id]/edit", () => {
  it("정적 프리렌더하지 않는다", () => {
    expect(dynamic).toBe("force-dynamic");
  });

  it("R-1: 서버에서 서버로 현재 정의를 읽어 폼을 채운다 (키는 직접 넘기고 브라우저로 가지 않는다)", async () => {
    getAgent.mockResolvedValue(AGENT);
    await renderPage();

    expect(createClient).toHaveBeenCalledWith({ baseUrl: "http://api.test:8000", apiKey: KEY });
    expect(getAgent).toHaveBeenCalledWith(AGENT.id);
    expect(screen.getByLabelText<HTMLTextAreaElement>("시스템 프롬프트").value).toBe("old prompt");
    expect(screen.getByLabelText<HTMLInputElement>("모델 id").value).toBe("old-model");
    expect(screen.getByText("v3")).toBeTruthy();
    expect(document.body.innerHTML).not.toContain(KEY);
  });

  it("모델 id 가 null 이면 빈 칸으로 채운다", async () => {
    getAgent.mockResolvedValue({
      ...AGENT,
      definition: { schema_version: 1, system_prompt: "p", model: { id: null } },
    });
    await renderPage();
    expect(screen.getByLabelText<HTMLInputElement>("모델 id").value).toBe("");
  });

  it("404 는 Agent 를 찾을 수 없다는 화면이고 폼이 없다", async () => {
    getAgent.mockRejectedValue(
      new AetherHttpError("aether-sdk: GET /agents/x failed with status 404", 404, "Not Found"),
    );
    await renderPage();

    expect(screen.getByRole("alert").textContent).toContain("Agent 를 찾을 수 없습니다");
    expect(screen.queryByLabelText("시스템 프롬프트")).toBeNull();
  });

  it("그 밖의 오류는 불러오지 못했다는 화면이다 (404 와 다른 말)", async () => {
    getAgent.mockRejectedValue(new Error("fetch failed"));
    await renderPage();

    expect(screen.getByRole("alert").textContent).toContain("Agent 를 불러오지 못했습니다");
    expect(screen.queryByLabelText("시스템 프롬프트")).toBeNull();
  });

  it("모양이 틀린 id 는 api 를 부르지 않고 찾을 수 없다고 말한다", async () => {
    await renderPage("../runs/x");
    expect(getAgent).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("Agent 를 찾을 수 없습니다");
  });

  it("키가 없으면 호출하지 않고 그 사실을 말한다", async () => {
    vi.stubEnv("AETHER_API_KEY", " ");
    await renderPage();
    expect(getAgent).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toBeTruthy();
  });
});
