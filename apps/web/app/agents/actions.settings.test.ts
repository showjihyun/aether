// @vitest-environment node
import { AetherHttpError } from "@aether/sdk";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getAgent = vi.fn<(id: string) => Promise<unknown>>();
const updateAgent = vi.fn<(id: string, body: { definition: Record<string, unknown> }) => Promise<unknown>>();
const createClient = vi.fn<(options: { baseUrl: string; apiKey?: string }) => void>();
// 클라이언트에는 getAgent·updateAgent 둘뿐입니다 - 다른 SDK 메서드를 부르면 TypeError 로 드러납니다.
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: { baseUrl: string; apiKey?: string }) => {
    createClient(options);
    return { getAgent, updateAgent };
  },
}));

import { updateAgentSettingsAction } from "./actions";

const KEY = "aeth_test_not_a_real_key_0123456789";
const INTERNAL = "http://api.internal.invalid:8000";
const AGENT_ID = "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b";

const POLICY = {
  timeout_seconds: 300,
  max_steps: 12,
  model_retries: 3,
  tool_retries: 2,
  backoff: { base_seconds: 1, max_seconds: 16 },
};
const CURRENT = {
  id: AGENT_ID,
  name: "billing-helper",
  current_version: 3,
  definition: {
    schema_version: 1,
    system_prompt: "keep this prompt",
    model: { id: "old-model" },
    tools: ["search"],
    mcp_servers: [{ name: "old", transport: "stdio", ref: "old-ref" }],
    context_budget_tokens: 4096,
    knowledge: ["faq"],
    knowledge_top_k: 3,
    memory_enabled: false,
    policy: POLICY,
  },
  versions: [],
};

interface Fields {
  agentId: string;
  modelId: string;
  tools: string;
  mcpServers: string;
  contextBudget: string;
  knowledge: string;
  topK: string;
  memory: string;
}
const BASE: Fields = {
  agentId: AGENT_ID,
  modelId: "new-model",
  tools: "clock\ncalculator",
  mcpServers: "builtin stdio builtin\nremote http docs-gateway",
  contextBudget: "2048",
  knowledge: "handbook\nfaq",
  topK: "7",
  memory: "true",
};
type Args = Parameters<typeof updateAgentSettingsAction>;
function args(over: Partial<Fields> = {}): Args {
  const a = { ...BASE, ...over };
  return [a.agentId, a.modelId, a.tools, a.mcpServers, a.contextBudget, a.knowledge, a.topK, a.memory];
}

function httpError(status: number) {
  return new AetherHttpError(
    `aether-sdk: PUT ${INTERNAL}/agents/x failed with status ${status} upstream-body-secret`,
    status,
    "x",
  );
}

beforeEach(() => {
  getAgent.mockReset();
  updateAgent.mockReset();
  createClient.mockClear();
  getAgent.mockResolvedValue(CURRENT);
  updateAgent.mockResolvedValue({ ...CURRENT, current_version: 4 });
  vi.stubEnv("AETHER_API_KEY", KEY);
  vi.stubEnv("AETHER_API_URL", INTERNAL);
});
afterEach(() => vi.unstubAllEnvs());

describe("updateAgentSettingsAction (spec 0007 D-5, R-1, R-12)", () => {
  it("D-5: 네 패널의 칸이 updateAgent 한 번으로 모인다 (다른 SDK 메서드는 클라이언트에 없다)", async () => {
    const result = await updateAgentSettingsAction(...args());

    expect(getAgent).toHaveBeenCalledTimes(1);
    expect(updateAgent).toHaveBeenCalledTimes(1);
    expect(updateAgent).toHaveBeenCalledWith(AGENT_ID, {
      definition: {
        ...CURRENT.definition,
        model: { id: "new-model" },
        tools: ["clock", "calculator"],
        mcp_servers: [
          { name: "builtin", transport: "stdio", ref: "builtin" },
          { name: "remote", transport: "http", ref: "docs-gateway" },
        ],
        context_budget_tokens: 2048,
        knowledge: ["handbook", "faq"],
        knowledge_top_k: 7,
        memory_enabled: true,
      },
    });
    expect(result).toEqual({ ok: true, agentId: AGENT_ID, version: 4 });
  });

  it("2.8: 패널에 없는 칸(system_prompt·policy 블록·schema_version)은 현재 값 그대로 보존된다", async () => {
    await updateAgentSettingsAction(...args());
    const sent = updateAgent.mock.calls[0]![1].definition;
    expect(sent.system_prompt).toBe("keep this prompt");
    expect(sent.policy).toEqual(POLICY);
    expect(sent.schema_version).toBe(1);
  });

  it("비운 칸은 null(모델·예산·top_k) 또는 빈 목록이다 - 빈 줄은 버린다", async () => {
    await updateAgentSettingsAction(
      ...args({
        modelId: "  ",
        tools: "\n  \n",
        mcpServers: "",
        contextBudget: "",
        knowledge: " \n",
        topK: " ",
        memory: "false",
      }),
    );
    const sent = updateAgent.mock.calls[0]![1].definition;
    expect(sent.model).toEqual({ id: null });
    expect(sent.tools).toEqual([]);
    expect(sent.mcp_servers).toEqual([]);
    expect(sent.context_budget_tokens).toBeNull();
    expect(sent.knowledge).toEqual([]);
    expect(sent.knowledge_top_k).toBeNull();
    expect(sent.memory_enabled).toBe(false);
  });

  it("줄 앞뒤 공백·CRLF 는 다듬고, 경계값(예산 1, top_k 1)은 통과한다", async () => {
    await updateAgentSettingsAction(...args({ tools: "  clock  \r\ncalculator", contextBudget: "1", topK: "1" }));
    const sent = updateAgent.mock.calls[0]![1].definition;
    expect(sent.tools).toEqual(["clock", "calculator"]);
    expect(sent.context_budget_tokens).toBe(1);
    expect(sent.knowledge_top_k).toBe(1);
  });

  it.each<[string, Partial<Fields>]>([
    ["agentId 경로 조각", { agentId: "../runs/x" }],
    ["agentId 빈 값", { agentId: "" }],
    ["모델 id 모양", { modelId: "a b/../c" }],
    ["tools 중복", { tools: "clock\nclock" }],
    ["tools 한 줄이 너무 길다", { tools: "a".repeat(201) }],
    ["tools 제어문자", { tools: "cl\u0000ock" }],
    ["knowledge 중복", { knowledge: "faq\nfaq" }],
    ["mcp 칸 수가 모자라다", { mcpServers: "builtin stdio" }],
    ["mcp 칸 수가 넘친다", { mcpServers: "builtin stdio builtin extra" }],
    ["mcp transport 가 stdio|http 가 아니다", { mcpServers: "builtin ws builtin" }],
    ["mcp ref 가 절대 URL 이다", { mcpServers: "remote http https://docs.example.com/mcp" }],
    ["mcp ref 에 자격증명 꼴이 든다", { mcpServers: "remote http user:pw://x" }],
    ["예산 0", { contextBudget: "0" }],
    ["예산 음수", { contextBudget: "-5" }],
    ["예산 소수", { contextBudget: "1.5" }],
    ["예산 문자", { contextBudget: "많이" }],
    ["top_k 0", { topK: "0" }],
    ["top_k 문자", { topK: "abc" }],
    ["memory 가 true|false 가 아니다", { memory: "yes" }],
  ])("R-2: 검증 실패(%s)는 업스트림을 부르지 않고 문장으로 돌려준다", async (_n, over) => {
    const result = await updateAgentSettingsAction(...args(over));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message.length).toBeGreaterThan(0);
    expect(createClient).not.toHaveBeenCalled();
    expect(updateAgent).not.toHaveBeenCalled();
  });

  it("R-2: 문자열이 아닌 인자(브라우저가 보낼 수 있다)는 업스트림을 부르지 않는다", async () => {
    const action = updateAgentSettingsAction as unknown as (...a: unknown[]) => Promise<{ ok: boolean }>;
    const good = args();
    for (let i = 0; i < good.length; i += 1) {
      for (const bad of [null, 5, { x: 1 }, ["a"], undefined, true]) {
        const mutated: unknown[] = [...good];
        mutated[i] = bad;
        expect((await action(...mutated)).ok).toBe(false);
      }
    }
    expect(createClient).not.toHaveBeenCalled();
  });

  it("D-8: 409 는 누군가 먼저 저장했다는 말이고 본문을 흘리지 않는다", async () => {
    updateAgent.mockRejectedValue(httpError(409));
    const result = await updateAgentSettingsAction(...args());
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toContain("누군가 먼저 저장했습니다");
      expect(JSON.stringify(result)).not.toContain("upstream-body-secret");
    }
  });

  it.each([401, 403, 404, 422, 500])("%i: 키·내부 주소·업스트림 본문을 메시지에 넣지 않는다", async (status) => {
    updateAgent.mockRejectedValue(httpError(status));
    const result = await updateAgentSettingsAction(...args());
    expect(result.ok).toBe(false);
    const text = JSON.stringify(result);
    expect(text).not.toContain(KEY);
    expect(text).not.toContain("api.internal.invalid");
    expect(text).not.toContain("upstream-body-secret");
  });

  it("네트워크 오류는 닿지 못했다는 말이고 던지지 않는다", async () => {
    getAgent.mockRejectedValue(new TypeError(`fetch failed ${INTERNAL} ${KEY}`));
    const result = await updateAgentSettingsAction(...args());
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toContain("api 에 닿지 못했습니다");
    expect(JSON.stringify(result)).not.toContain(KEY);
  });

  it("키가 없으면 호출하지 않고 키를 주입하라고 말한다", async () => {
    vi.stubEnv("AETHER_API_KEY", " ");
    const result = await updateAgentSettingsAction(...args());
    expect(updateAgent).not.toHaveBeenCalled();
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toContain("AETHER_WEB_API_KEY");
  });
});
