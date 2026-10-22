// @vitest-environment node
import { AetherHttpError } from "@aether/sdk";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

interface Sent {
  name?: string;
  definition: {
    system_prompt: string;
    model?: unknown;
    tools?: unknown;
    memory_enabled?: unknown;
    knowledge?: unknown;
    context_budget_tokens?: unknown;
  };
}
const createAgent = vi.fn<(body: Sent) => Promise<unknown>>();
const getAgent = vi.fn<(id: string) => Promise<unknown>>();
const updateAgent = vi.fn<(id: string, body: Sent) => Promise<unknown>>();
const createClient = vi.fn<(options: { baseUrl: string; apiKey?: string }) => void>();
// `AetherHttpError` 는 실제 클래스를 통과시킵니다 - 액션의 `instanceof` 분기가 실제 SDK 오류에서도 성립해야 합니다.
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: { baseUrl: string; apiKey?: string }) => {
    createClient(options);
    return { createAgent, getAgent, updateAgent };
  },
}));

import { createAgentAction, updateAgentAction } from "./actions";

// 명백한 가짜 키와 가짜 내부 주소입니다.
const KEY = "aeth_test_not_a_real_key_0123456789";
const INTERNAL = "http://api.internal.invalid:8000";
const AGENT_ID = "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b";

function httpError(status: number) {
  return new AetherHttpError(
    `aether-sdk: PUT ${INTERNAL}/agents/x failed with status ${status} upstream-body-secret`,
    status,
    "x",
  );
}

const CURRENT = {
  id: AGENT_ID,
  name: "billing-helper",
  current_version: 3,
  definition: {
    schema_version: 1,
    system_prompt: "old",
    model: { id: "old-model" },
    tools: ["search"],
    memory_enabled: true,
    knowledge: ["faq"],
    context_budget_tokens: 4096,
  },
  versions: [],
};

beforeEach(() => {
  createAgent.mockReset();
  getAgent.mockReset();
  updateAgent.mockReset();
  createClient.mockClear();
  vi.stubEnv("AETHER_API_KEY", KEY);
  vi.stubEnv("AETHER_API_URL", INTERNAL);
});
afterEach(() => {
  vi.unstubAllEnvs();
});

describe("createAgentAction (spec 0007 R-1, R-2, D-2)", () => {
  it("R-1: 키를 SDK 에 넘기고 web 이 조립한 본문으로 createAgent 를 부른다", async () => {
    createAgent.mockResolvedValue({ id: AGENT_ID, name: "n", current_version: 1 });

    const result = await createAgentAction("billing-helper", "당신은 도우미입니다.", "gpt-x");

    expect(createClient).toHaveBeenCalledWith({ baseUrl: INTERNAL, apiKey: KEY });
    expect(createAgent).toHaveBeenCalledWith({
      name: "billing-helper",
      definition: {
        schema_version: 1,
        system_prompt: "당신은 도우미입니다.",
        model: { id: "gpt-x" },
      },
    });
    expect(result).toEqual({ ok: true, agentId: AGENT_ID, version: 1 });
  });

  it("R-1: 모델 id 를 비워 두면 null 로 보낸다 (배포 설정의 모델을 쓴다)", async () => {
    createAgent.mockResolvedValue({ id: AGENT_ID, current_version: 1 });
    await createAgentAction("a", "p", "   ");
    expect(createAgent.mock.calls[0]![0].definition.model).toEqual({ id: null });
  });

  it("D-2: 이름은 앞뒤 공백을 자르고, 프롬프트는 본문을 바꾸지 않는다", async () => {
    createAgent.mockResolvedValue({ id: AGENT_ID, current_version: 1 });
    await createAgentAction("  a  ", "  두 줄\n입니다  ", "");
    const body = createAgent.mock.calls[0]![0];
    expect(body.name).toBe("a");
    expect(body.definition.system_prompt).toBe("  두 줄\n입니다  ");
  });

  it.each([
    ["이름이 비어 있다", "", "p", ""],
    ["이름이 공백뿐이다", "  ", "p", ""],
    ["이름이 100자를 넘는다", "a".repeat(101), "p", ""],
    ["프롬프트가 비어 있다", "a", "", ""],
    ["프롬프트가 공백뿐이다", "a", " \n ", ""],
    ["프롬프트가 20,000자를 넘는다", "a", "p".repeat(20_001), ""],
    ["모델 id 모양이 틀리다", "a", "p", "a b/../c"],
  ])("R-2: 검증 실패(%s)는 업스트림을 부르지 않고 문장으로 돌려준다", async (_n, name, prompt, model) => {
    const result = await createAgentAction(name, prompt, model);

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message.length).toBeGreaterThan(0);
    expect(createAgent).not.toHaveBeenCalled();
    expect(createClient).not.toHaveBeenCalled();
  });

  it("R-2: 경계 - 이름 100자와 프롬프트 20,000자는 통과한다", async () => {
    createAgent.mockResolvedValue({ id: AGENT_ID, current_version: 1 });
    const result = await createAgentAction("a".repeat(100), "p".repeat(20_000), "");
    expect(result.ok).toBe(true);
  });

  it("R-2: 문자열이 아닌 인자(브라우저가 보낼 수 있다)는 업스트림을 부르지 않는다", async () => {
    const action = createAgentAction as unknown as (...args: unknown[]) => Promise<{ ok: boolean }>;
    for (const args of [[{ x: 1 }, "p", ""], ["a", null, ""], ["a", "p", 5], [undefined, undefined, undefined]]) {
      expect((await action(...args)).ok).toBe(false);
    }
    expect(createAgent).not.toHaveBeenCalled();
  });

  it("D-8: 409 는 같은 이름이 이미 있다는 말이다 (이름 충돌)", async () => {
    createAgent.mockRejectedValue(httpError(409));

    const result = await createAgentAction("a", "p", "");

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toContain("같은 이름");
  });

  it("키가 없으면 호출하지 않고 키를 주입하라고 말한다", async () => {
    vi.stubEnv("AETHER_API_KEY", "  ");
    const result = await createAgentAction("a", "p", "");
    expect(createAgent).not.toHaveBeenCalled();
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toContain("AETHER_WEB_API_KEY");
  });
});

describe("updateAgentAction (spec 0007 R-1, R-12, 2.8, D-8)", () => {
  it("R-1: 현재 정의를 api 에서 읽어 시스템 프롬프트 한 칸만 바꾸고 나머지는 그대로 updateAgent 로 보낸다", async () => {
    getAgent.mockResolvedValue(CURRENT);
    updateAgent.mockResolvedValue({ ...CURRENT, current_version: 4 });

    const result = await updateAgentAction(AGENT_ID, "new prompt");

    expect(getAgent).toHaveBeenCalledWith(AGENT_ID);
    expect(updateAgent).toHaveBeenCalledWith(AGENT_ID, {
      definition: {
        ...CURRENT.definition,
        system_prompt: "new prompt",
      },
    });
    expect(result).toEqual({ ok: true, agentId: AGENT_ID, version: 4 });
  });

  it("D-5: 프롬프트만 바꾸는 저장은 모델을 지우지 않는다 (model.id 는 설정 패널이 소유한다)", async () => {
    getAgent.mockResolvedValue(CURRENT);
    updateAgent.mockResolvedValue({ ...CURRENT, current_version: 4 });
    await updateAgentAction(AGENT_ID, "p");
    expect(updateAgent.mock.calls[0]![1].definition.model).toEqual({ id: "old-model" });

    updateAgent.mockClear();
    getAgent.mockResolvedValue({ ...CURRENT, definition: { ...CURRENT.definition, model: { id: null } } });
    await updateAgentAction(AGENT_ID, "p");
    expect(updateAgent.mock.calls[0]![1].definition.model).toEqual({ id: null });
  });

  it("2.8: 정의는 통째로 교체되므로 폼에 없는 칸(tools·memory·knowledge)이 사라지지 않는다", async () => {
    getAgent.mockResolvedValue(CURRENT);
    updateAgent.mockResolvedValue({ ...CURRENT, current_version: 4 });

    await updateAgentAction(AGENT_ID, "p");

    const sent = updateAgent.mock.calls[0]![1].definition;
    expect(sent.tools).toEqual(["search"]);
    expect(sent.memory_enabled).toBe(true);
    expect(sent.knowledge).toEqual(["faq"]);
    expect(sent.context_budget_tokens).toBe(4096);
  });

  it.each([
    ["경로 조각", "../runs/x"],
    ["슬래시", "a/b"],
    ["쿼리", "a?x=1"],
    ["빈 값", ""],
  ])("R-2: 모양이 틀린 agentId(%s)는 업스트림을 부르지 않는다", async (_n, id) => {
    const result = await updateAgentAction(id, "p");
    expect(result.ok).toBe(false);
    expect(getAgent).not.toHaveBeenCalled();
    expect(updateAgent).not.toHaveBeenCalled();
  });

  it("R-2: 프롬프트가 비면 업스트림을 부르지 않는다", async () => {
    const result = await updateAgentAction(AGENT_ID, "  ");
    expect(result.ok).toBe(false);
    expect(createClient).not.toHaveBeenCalled();
  });

  it("D-8: 409 는 '누군가 먼저 저장했습니다' 이다 (상태 코드로 분기, 본문을 흘리지 않는다)", async () => {
    getAgent.mockResolvedValue(CURRENT);
    updateAgent.mockRejectedValue(httpError(409));

    const result = await updateAgentAction(AGENT_ID, "p");

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toContain("누군가 먼저 저장했습니다");
      expect(result.message).not.toContain("upstream-body-secret");
      expect(result.message).not.toContain("agent_version_conflict");
    }
  });

  it.each([401, 403])("%i 는 web 의 키를 다시 발급하라는 말이다", async (status) => {
    getAgent.mockRejectedValue(httpError(status));
    expect(await updateAgentAction(AGENT_ID, "p")).toEqual({
      ok: false,
      message: "api 가 web 의 키를 거부했습니다. 키를 다시 발급해 주입하세요.",
    });
  });

  it("404 는 Agent 가 없다는 말이다 (읽기에서도 쓰기에서도)", async () => {
    getAgent.mockRejectedValue(httpError(404));
    const read = await updateAgentAction(AGENT_ID, "p");
    getAgent.mockResolvedValue(CURRENT);
    updateAgent.mockRejectedValue(httpError(404));
    const write = await updateAgentAction(AGENT_ID, "p");
    for (const result of [read, write]) {
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.message).toContain("Agent 를 찾을 수 없습니다");
    }
  });

  it("그 밖의 상태(422·500)는 닿았다는 뜻이므로 '닿지 못했다' 고 말하지 않고 상태 코드를 보인다", async () => {
    for (const status of [422, 500]) {
      getAgent.mockResolvedValue(CURRENT);
      updateAgent.mockReset();
      updateAgent.mockRejectedValue(httpError(status));
      const result = await updateAgentAction(AGENT_ID, "p");
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.message).not.toContain("닿지 못했");
        expect(result.message).toContain(String(status));
      }
    }
  });

  it("네트워크 오류(상태 없음)는 '닿지 못했다' 이다", async () => {
    getAgent.mockResolvedValue(CURRENT);
    updateAgent.mockRejectedValue(new TypeError(`fetch failed ${INTERNAL} ${KEY}`));
    const result = await updateAgentAction(AGENT_ID, "p");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toContain("api 에 닿지 못했습니다");
  });

  it.each([
    ["401", httpError(401)],
    ["404", httpError(404)],
    ["409", httpError(409)],
    ["500", httpError(500)],
    ["네트워크", new TypeError(`fetch failed ${INTERNAL} ${KEY}`)],
  ])("실패 메시지(%s)에 키 값도 내부 주소도 업스트림 본문도 없다", async (_n, error) => {
    getAgent.mockResolvedValue(CURRENT);
    updateAgent.mockRejectedValue(error);

    const result = await updateAgentAction(AGENT_ID, "p");

    const serialized = JSON.stringify(result);
    expect(serialized).not.toContain(KEY);
    expect(serialized).not.toContain("api.internal.invalid");
    expect(serialized).not.toContain("upstream-body-secret");
  });

  it("예외를 던지지 않는다 (Next 기본 오류 화면이 나오지 않는다)", async () => {
    getAgent.mockRejectedValue(new Error("boom"));
    await expect(updateAgentAction(AGENT_ID, "p")).resolves.toMatchObject({ ok: false });
  });
});
