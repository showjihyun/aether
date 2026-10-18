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

const chatProps = vi.fn<(props: Record<string, unknown>) => void>();
vi.mock("./Chat", () => ({
  Chat: (props: Record<string, unknown>) => {
    chatProps(props);
    return <div data-testid="chat" />;
  },
}));

import AgentChatPage, { dynamic } from "./page";

const KEY = "aeth_test_fake_key";
const AGENT = {
  id: "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b",
  name: "billing-helper",
  current_version: 3,
  definition: { schema_version: 1, system_prompt: "x", memory_enabled: true },
};

async function renderPage(id = AGENT.id) {
  render(await AgentChatPage({ params: Promise.resolve({ id }) }));
}

beforeEach(() => {
  getAgent.mockReset();
  createClient.mockClear();
  chatProps.mockClear();
  vi.stubEnv("AETHER_API_KEY", KEY);
  vi.stubEnv("AETHER_API_URL", "http://api.test:8000");
});
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe("/agents/[id]/chat", () => {
  it("정적 프리렌더하지 않는다 (빌드가 api 를 부르면 실패한다)", () => {
    expect(dynamic).toBe("force-dynamic");
  });

  it("MVP-2e: 서버에서 서버로 키를 직접 넘겨 Agent 를 받는다", async () => {
    getAgent.mockResolvedValue(AGENT);
    await renderPage();

    expect(createClient).toHaveBeenCalledWith({
      baseUrl: "http://api.test:8000",
      apiKey: KEY,
    });
    expect(getAgent).toHaveBeenCalledWith(AGENT.id);
  });

  it("MVP-2e: Chat 에 agentId·agentName·memoryEnabled 만 넘기고 키는 넘기지 않는다", async () => {
    getAgent.mockResolvedValue(AGENT);
    await renderPage();

    expect(chatProps).toHaveBeenCalledWith({
      agentId: AGENT.id,
      agentName: "billing-helper",
      memoryEnabled: true,
    });
    expect(JSON.stringify(chatProps.mock.calls)).not.toContain(KEY);
  });

  it("memory_enabled 가 정의에 없으면 거짓이다 (스키마 기본값)", async () => {
    getAgent.mockResolvedValue({ ...AGENT, definition: { schema_version: 1, system_prompt: "x" } });
    await renderPage();

    expect(chatProps.mock.calls[0]?.[0]).toMatchObject({ memoryEnabled: false });
  });

  it("머리에 이름과 현재 Version 을 보인다", async () => {
    getAgent.mockResolvedValue(AGENT);
    await renderPage();

    expect(screen.getByText("billing-helper")).toBeTruthy();
    expect(screen.getByText("v3")).toBeTruthy();
  });

  it("키가 없으면 호출하지 않고 api 키가 없다고 말한다", async () => {
    vi.stubEnv("AETHER_API_KEY", "  ");
    await renderPage();

    expect(getAgent).not.toHaveBeenCalled();
    expect(screen.getByText("api 키가 없습니다")).toBeTruthy();
  });

  it("404 는 Agent 를 찾을 수 없다는 말과 목록으로 돌아가는 링크다", async () => {
    getAgent.mockRejectedValue(new AetherHttpError("failed with status 404", 404, "Not Found"));
    await renderPage();

    expect(screen.getByRole("alert").textContent).toContain("Agent 를 찾을 수 없습니다");
    expect(screen.getByRole("link", { name: "Agent 목록으로" }).getAttribute("href")).toBe("/agents");
    expect(screen.queryByTestId("chat")).toBeNull();
  });

  it("그 외 오류는 alert 이고 대화 화면을 그리지 않는다", async () => {
    getAgent.mockRejectedValue(new Error("fetch failed"));
    await renderPage();

    expect(screen.getByRole("alert").textContent).toContain("fetch failed");
    expect(screen.queryByTestId("chat")).toBeNull();
  });
});
