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
vi.mock("../../actions", () => ({ updateAgentSettingsAction: vi.fn() }));

import AgentSettingsPage, { dynamic } from "./page";

const KEY = "aeth_test_fake_key";
const AGENT = {
  id: "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b",
  name: "billing-helper",
  current_version: 3,
  definition: {
    schema_version: 1,
    system_prompt: "p",
    model: { id: "old-model" },
    tools: ["search"],
    mcp_servers: [{ name: "builtin", transport: "stdio", ref: "builtin" }],
    context_budget_tokens: 4096,
    knowledge: ["faq"],
    knowledge_top_k: 3,
    memory_enabled: true,
  },
};

async function renderPage(id = AGENT.id) {
  render(await AgentSettingsPage({ params: Promise.resolve({ id }) }));
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

describe("/agents/[id]/settings", () => {
  it("정적 프리렌더하지 않는다", () => {
    expect(dynamic).toBe("force-dynamic");
  });

  it("서버에서 서버로 현재 정의를 읽어 패널을 채운다 (키는 브라우저로 가지 않는다)", async () => {
    getAgent.mockResolvedValue(AGENT);
    await renderPage();

    expect(createClient).toHaveBeenCalledWith({ baseUrl: "http://api.test:8000", apiKey: KEY });
    expect(getAgent).toHaveBeenCalledWith(AGENT.id);
    expect(screen.getByLabelText<HTMLInputElement>("모델 id").value).toBe("old-model");
    expect(screen.getByLabelText<HTMLTextAreaElement>("도구 이름").value).toBe("search");
    expect(screen.getByLabelText<HTMLInputElement>("컨텍스트 예산(토큰)").value).toBe("4096");
    expect(screen.getByLabelText<HTMLInputElement>("Memory 켜기").checked).toBe(true);
    expect(document.body.innerHTML).not.toContain(KEY);
  });

  it("오래된 정의(선택 칸이 없다)도 빈 값으로 채운다", async () => {
    getAgent.mockResolvedValue({
      ...AGENT,
      definition: { schema_version: 1, system_prompt: "p", model: { id: null } },
    });
    await renderPage();
    expect(screen.getByLabelText<HTMLTextAreaElement>("도구 이름").value).toBe("");
    expect(screen.getByLabelText<HTMLInputElement>("컨텍스트 예산(토큰)").value).toBe("");
    expect(screen.getByLabelText<HTMLInputElement>("Memory 켜기").checked).toBe(false);
  });

  it("404 는 Agent 를 찾을 수 없다는 화면이고 폼이 없다", async () => {
    getAgent.mockRejectedValue(new AetherHttpError("aether-sdk: GET /agents/x failed with status 404", 404, "Not Found"));
    await renderPage();
    expect(screen.getByRole("alert").textContent).toContain("Agent 를 찾을 수 없습니다");
    expect(screen.queryByLabelText("모델 id")).toBeNull();
  });

  it("그 밖의 오류는 불러오지 못했다는 화면이다", async () => {
    getAgent.mockRejectedValue(new Error("fetch failed"));
    await renderPage();
    expect(screen.getByRole("alert").textContent).toContain("Agent 를 불러오지 못했습니다");
  });

  it("모양이 틀린 id 는 api 를 부르지 않는다", async () => {
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
