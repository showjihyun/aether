"use server";

import { AetherHttpError, createClient } from "@aether/sdk";

// "use server" 파일은 async 함수만 내보낼 수 있습니다(타입은 지워지므로 괜찮습니다).
// 상수·보조 함수는 내보내지 않습니다.

export type StartRunResult = { ok: true; runId: string } | { ok: false; message: string };

const MAX_INPUT_LENGTH = 10_000;
// `lib/relay.ts` 의 id 칸과 같은 꼴입니다. SDK 가 이 값으로 URL 경로를 만들기 때문에
// `../`·`/`·`?` 가 든 값을 경로에 끼우지 않습니다.
const ID_SHAPE = /^[A-Za-z0-9_-]{1,128}$/;

const AGENT_NOT_FOUND = "Agent 를 찾을 수 없습니다. Agent 목록에서 다시 들어오세요.";

function fail(message: string): StartRunResult {
  return { ok: false, message };
}

/**
 * Agent 의 실행을 시작합니다(D-18: 쓰기는 중계가 아니라 Next 서버 액션).
 *
 * 서버 액션은 **어떤 브라우저 요청이든 올 수 있는 진입점**이라 인자를 신뢰하지 않습니다.
 * 사용자 세션·권한은 이 단위 밖입니다(Phase 8) - 지금 선은 "web 에 닿는 사람은 Run 을
 * 시작할 수 있다" 입니다.
 *
 * 실패 메시지에는 키 값·`AETHER_API_URL`·업스트림 응답 본문·SDK 오류 원문을 넣지 않습니다.
 * 분기는 `AetherHttpError.status` 필드로 합니다(문구를 파싱하지 않습니다).
 */
export async function startRun(agentId: string, input: string): Promise<StartRunResult> {
  if (typeof agentId !== "string" || !ID_SHAPE.test(agentId)) return fail(AGENT_NOT_FOUND);
  if (typeof input !== "string" || input.trim() === "") return fail("보낼 내용을 입력하세요.");
  if (input.length > MAX_INPUT_LENGTH) {
    return fail("입력은 10,000자까지입니다. 줄여서 다시 보내세요.");
  }

  const apiKey = process.env.AETHER_API_KEY?.trim();
  if (!apiKey) {
    // `MissingApiKey` 와 같은 말입니다.
    return fail(
      "web 컨테이너에 api 키를 주입하세요 — AETHER_WEB_API_KEY (infra/docker/.env.example 참고). 발급은 api 컨테이너에서 한 번만 출력됩니다.",
    );
  }

  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
    apiKey: process.env.AETHER_API_KEY,
  });

  try {
    const accepted = await client.runAgent(agentId, { input });
    return { ok: true, runId: accepted.run_id };
  } catch (error) {
    if (error instanceof AetherHttpError) {
      if (error.status === 401 || error.status === 403) {
        // `lib/relay.ts` 가 하는 말과 같습니다 - 두 경로가 같은 말을 해야 합니다.
        return fail("api 가 web 의 키를 거부했습니다. 키를 다시 발급해 주입하세요.");
      }
      if (error.status === 404) return fail(AGENT_NOT_FOUND);
      // 상태 코드가 있다는 것은 **닿았다**는 뜻입니다 - "api 가 떠 있는지 확인하세요" 는
      // 떠 있는 api 에 대해 틀린 지시입니다(MVP-2c 의 404 와 같은 결함, 리뷰 2026-10-18).
      // 응답 본문은 넘기지 않고 상태 코드만 보입니다.
      return fail(
        `api 가 이 요청을 거절했습니다(상태 ${error.status}). 잠시 뒤 다시 보내고, 계속되면 api 로그를 보세요.`,
      );
    }
    return fail("api 에 닿지 못했습니다. api 가 떠 있는지 확인한 뒤 다시 시도하세요.");
  }
}
