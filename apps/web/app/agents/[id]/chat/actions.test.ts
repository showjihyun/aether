// @vitest-environment node
import { AetherHttpError } from "@aether/sdk";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const runAgent = vi.fn();
const createClient = vi.fn<(options: { baseUrl: string; apiKey?: string }) => void>();
// `AetherHttpError` 는 실제 클래스를 통과시킵니다 — 액션의 `instanceof` 분기가 실제 SDK 오류에서도 성립해야 합니다.
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: { baseUrl: string; apiKey?: string }) => {
    createClient(options);
    return { runAgent };
  },
}));

import { startRun } from "./actions";

// 명백한 가짜 키와 가짜 내부 주소입니다. 어느 것도 실제 값이 아닙니다.
const KEY = "aeth_test_not_a_real_key_0123456789";
const INTERNAL = "http://api.internal.invalid:8000";
const AGENT_ID = "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b";
const RUN_ID = "0199ffee-0000-7000-8000-000000000001";

function httpError(status: number) {
  // 업스트림 본문 같은 것이 메시지에 섞여 있어도 화면 메시지로 새면 안 됩니다.
  return new AetherHttpError(
    `aether-sdk: POST ${INTERNAL}/agents/x/run failed with status ${status} upstream-body-secret`,
    status,
    "x",
  );
}

beforeEach(() => {
  runAgent.mockReset();
  createClient.mockClear();
  vi.stubEnv("AETHER_API_KEY", KEY);
  vi.stubEnv("AETHER_API_URL", INTERNAL);
});
afterEach(() => {
  vi.unstubAllEnvs();
});

describe("startRun 서버 액션 (D-18)", () => {
  it("D-18: 키를 SDK 에 넘기고 runAgent(agentId, { input }) 를 부르며 runId 를 돌려준다", async () => {
    runAgent.mockResolvedValue({ run_id: RUN_ID, status: "queued" });

    const result = await startRun(AGENT_ID, "안녕");

    expect(createClient).toHaveBeenCalledWith({ baseUrl: INTERNAL, apiKey: KEY });
    expect(runAgent).toHaveBeenCalledWith(AGENT_ID, { input: "안녕" });
    expect(result).toEqual({ ok: true, runId: RUN_ID });
  });

  it("D-18: 입력은 앞뒤 공백을 자르지 않고 그대로 보낸다 (본문을 바꾸지 않는다)", async () => {
    runAgent.mockResolvedValue({ run_id: RUN_ID });
    await startRun(AGENT_ID, "  두 줄\n입니다  ");
    expect(runAgent).toHaveBeenCalledWith(AGENT_ID, { input: "  두 줄\n입니다  " });
  });

  it.each([
    ["빈 문자열", ""],
    ["공백만", "  \n\t "],
    ["상한(10,000자) 초과", "a".repeat(10_001)],
  ])("D-18: %s 는 업스트림을 부르지 않고 거절한다", async (_name, input) => {
    const result = await startRun(AGENT_ID, input);

    expect(result.ok).toBe(false);
    expect(runAgent).not.toHaveBeenCalled();
    expect(createClient).not.toHaveBeenCalled();
  });

  it("D-18: 정확히 10,000자는 통과한다 (상한 경계)", async () => {
    runAgent.mockResolvedValue({ run_id: RUN_ID });
    const result = await startRun(AGENT_ID, "a".repeat(10_000));
    expect(result.ok).toBe(true);
  });

  it.each([
    ["경로 조각", "../runs/x"],
    ["슬래시", "a/b"],
    ["쿼리", "a?x=1"],
    ["빈 값", ""],
  ])("D-18: 모양이 틀린 agentId(%s)는 업스트림을 부르지 않고 거절한다", async (_name, id) => {
    const result = await startRun(id, "안녕");

    expect(result.ok).toBe(false);
    expect(runAgent).not.toHaveBeenCalled();
  });

  it("D-18: 키가 없으면(빈 값·공백) 호출하지 않고 키를 주입하라고 말한다", async () => {
    vi.stubEnv("AETHER_API_KEY", "  ");

    const result = await startRun(AGENT_ID, "안녕");

    expect(runAgent).not.toHaveBeenCalled();
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toContain("api 키를 주입");
      expect(result.message).toContain("AETHER_WEB_API_KEY");
    }
  });

  it.each([401, 403])("D-18: %i 는 web 의 키를 다시 발급하라는 말이다 (relay 와 같은 말)", async (status) => {
    runAgent.mockRejectedValue(httpError(status));

    const result = await startRun(AGENT_ID, "안녕");

    expect(result).toEqual({
      ok: false,
      message: "api 가 web 의 키를 거부했습니다. 키를 다시 발급해 주입하세요.",
    });
  });

  it("D-18: 404 는 Agent 가 없다는 말이다", async () => {
    runAgent.mockRejectedValue(httpError(404));

    const result = await startRun(AGENT_ID, "안녕");

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message).toContain("Agent 를 찾을 수 없습니다");
  });

  it("D-18: 닿지 못한 경우(상태 없음)는 api 가 떠 있는지 묻고 다시 시도를 말한다", async () => {
    // 상태 코드가 **있는** 경우는 닿은 것이므로 다른 말을 합니다 - 아래 리뷰 테스트가
    // 그쪽을 봅니다(MVP-2e 리뷰 2026-10-18에 이 기대가 바뀌었습니다).
    runAgent.mockRejectedValue(new TypeError(`fetch failed ${INTERNAL} ${KEY}`));

    const result = await startRun(AGENT_ID, "안녕");

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.message).toContain("api 에 닿지 못했습니다");
      expect(result.message).toContain("다시 시도");
    }
  });

  it.each([
    ["401", httpError(401)],
    ["404", httpError(404)],
    ["500", httpError(500)],
    ["네트워크", new TypeError(`fetch failed ${INTERNAL} ${KEY}`)],
  ])("D-18: 실패 메시지(%s)에 키 값도 내부 주소도 업스트림 본문도 없다", async (_name, error) => {
    runAgent.mockRejectedValue(error);

    const result = await startRun(AGENT_ID, "안녕");

    expect(result.ok).toBe(false);
    const serialized = JSON.stringify(result);
    expect(serialized).not.toContain(KEY);
    expect(serialized).not.toContain("api.internal.invalid");
    expect(serialized).not.toContain("upstream-body-secret");
  });

  it("D-18: 예외를 던지지 않는다 (Next 기본 오류 화면이 나오지 않는다)", async () => {
    runAgent.mockRejectedValue(new Error("boom"));
    await expect(startRun(AGENT_ID, "안녕")).resolves.toMatchObject({ ok: false });
  });

  it("리뷰: api 가 응답한 다른 상태 코드(429·422·500)에는 '닿지 못했다' 고 말하지 않는다", async () => {
    // 상태 코드가 있다는 것은 **닿았다**는 뜻입니다. "api 가 떠 있는지 확인하세요" 는 떠 있는
    // api 에 대해 틀린 지시이고, 같은 결함을 MVP-2c 의 `/knowledge/{id}` 404 에서 한 번
    // 고쳤습니다(MVP-2e 리뷰 2026-10-18). 네트워크 오류만 '닿지 못했다' 입니다.
    for (const status of [429, 422, 500]) {
      runAgent.mockReset();
      runAgent.mockRejectedValue(
        new AetherHttpError(`aether-sdk: POST /agents/x/run failed with status ${status}`, status, "x"),
      );

      const result = await startRun(AGENT_ID, "안녕");

      expect(result.ok).toBe(false);
      if (result.ok) throw new Error("unreachable");
      expect(result.message, `status ${status}`).not.toContain("닿지 못했");
      expect(result.message).toContain(String(status));
    }
  });

  it("리뷰: 네트워크 오류(상태 없음)는 여전히 '닿지 못했다' 다", async () => {
    runAgent.mockRejectedValue(new TypeError("fetch failed"));

    const result = await startRun(AGENT_ID, "안녕");

    expect(result.ok).toBe(false);
    if (result.ok) throw new Error("unreachable");
    expect(result.message).toContain("닿지 못했");
  });

});
