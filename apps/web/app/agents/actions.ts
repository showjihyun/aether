"use server";

import { AetherHttpError, createClient } from "@aether/sdk";

// "use server" 파일은 async 함수만 내보낼 수 있습니다(타입은 지워지므로 괜찮습니다).
// 상수·보조 함수는 내보내지 않습니다.
//
// 이 파일이 Phase 5 의 **첫 쓰기 경로**이고, 모양이 선례입니다(spec 0007 D-2, R-2) -
// P5-6(Workflow 저장)·P5-7(설정 저장)이 이 모양을 따릅니다:
//   1. 인자는 원시 타입뿐이고, 각 인자는 본문의 **첫 줄들에서** typeof + 내용 검사를 거칩니다.
//   2. 요청 본문은 web 이 조립합니다. 브라우저가 보낸 객체를 api 로 넘기지 않습니다.
//   3. api 호출은 SDK 로만 합니다. 실패는 던지지 않고 `{ ok: false, message }` 로 돌려줍니다.
//   4. 분기는 `AetherHttpError.status` 필드로 합니다. 메시지에 키·URL·업스트림 본문·SDK 오류
//      원문을 넣지 않습니다.
// `tests/arch/test_use_server_actions_are_sdk_only_and_validated.py` 가 1·3 을 파일에서 고정합니다.

export type SaveAgentResult =
  | { ok: true; agentId: string; version: number }
  | { ok: false; message: string };

const MAX_NAME_LENGTH = 100;
const MAX_PROMPT_LENGTH = 20_000;
// `lib/relay.ts` 의 id 칸과 같은 꼴입니다. SDK 가 이 값으로 URL 경로를 만들기 때문에
// `../`·`/`·`?` 가 든 값을 경로에 끼우지 않습니다.
const ID_SHAPE = /^[A-Za-z0-9_-]{1,128}$/;
// 모델 id 는 공급자마다 점·콜론·슬래시를 씁니다(`provider/model:tag`). 공백·제어문자는 거절합니다.
const MODEL_SHAPE = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$/;

const AGENT_NOT_FOUND = "Agent 를 찾을 수 없습니다. Agent 목록에서 다시 들어오세요.";

function fail(message: string): SaveAgentResult {
  return { ok: false, message };
}

function noKey(): SaveAgentResult {
  // `MissingApiKey` 와 같은 말입니다.
  return fail(
    "web 컨테이너에 api 키를 주입하세요 — AETHER_WEB_API_KEY (infra/docker/.env.example 참고). 발급은 api 컨테이너에서 한 번만 출력됩니다.",
  );
}

/** 빈 칸은 null(배포 설정의 모델을 쓴다), 아니면 앞뒤 공백을 뺀 값. */
function modelOrNull(modelId: string): string | null {
  const trimmed = modelId.trim();
  return trimmed === "" ? null : trimmed;
}

/** 오류를 폼 위 문장으로 바꿉니다. 409 의 뜻은 호출한 쪽이 압니다(생성: 이름, 수정: 버전). */
function failFrom(error: unknown, conflict: string): SaveAgentResult {
  if (error instanceof AetherHttpError) {
    if (error.status === 401 || error.status === 403) {
      // `lib/relay.ts` 가 하는 말과 같습니다 - 두 경로가 같은 말을 해야 합니다.
      return fail("api 가 web 의 키를 거부했습니다. 키를 다시 발급해 주입하세요.");
    }
    if (error.status === 404) return fail(AGENT_NOT_FOUND);
    if (error.status === 409) return fail(conflict);
    // 상태 코드가 있다는 것은 **닿았다**는 뜻입니다 - "api 가 떠 있는지 확인하세요" 는 틀린 지시입니다.
    // 응답 본문은 넘기지 않고 상태 코드만 보입니다.
    return fail(
      `api 가 이 요청을 거절했습니다(상태 ${error.status}). 입력을 확인한 뒤 다시 저장하고, 계속되면 api 로그를 보세요.`,
    );
  }
  return fail("api 에 닿지 못했습니다. api 가 떠 있는지 확인한 뒤 다시 시도하세요.");
}

/**
 * Agent 를 만듭니다(`POST /agents`). 첫 Version(v1)이 함께 생깁니다.
 *
 * 서버 액션은 **어떤 브라우저 요청이든 올 수 있는 진입점**이라 인자를 신뢰하지 않습니다.
 * 사용자 세션·권한은 이 단위 밖입니다(Phase 8) - 지금 선은 "web 에 닿는 사람은 Agent 를
 * 만들 수 있다" 입니다(spec 0007 2.2·C-2).
 */
export async function createAgentAction(
  name: string,
  systemPrompt: string,
  modelId: string,
): Promise<SaveAgentResult> {
  if (typeof name !== "string" || name.trim() === "") return fail("이름을 입력하세요.");
  if (name.trim().length > MAX_NAME_LENGTH) return fail("이름은 100자까지입니다. 줄여서 다시 저장하세요.");
  if (typeof systemPrompt !== "string" || systemPrompt.trim() === "") {
    return fail("시스템 프롬프트를 입력하세요.");
  }
  if (systemPrompt.length > MAX_PROMPT_LENGTH) {
    return fail("시스템 프롬프트는 20,000자까지입니다. 줄여서 다시 저장하세요.");
  }
  if (typeof modelId !== "string" || (modelId.trim() !== "" && !MODEL_SHAPE.test(modelId.trim()))) {
    return fail("모델 id 는 영문·숫자와 . _ : / - 만 쓸 수 있습니다. 비워 두면 배포 설정의 모델을 씁니다.");
  }

  const apiKey = process.env.AETHER_API_KEY?.trim();
  if (!apiKey) return noKey();

  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
    apiKey: process.env.AETHER_API_KEY,
  });

  try {
    const created = await client.createAgent({
      name: name.trim(),
      definition: {
        schema_version: 1,
        system_prompt: systemPrompt,
        model: { id: modelOrNull(modelId) },
      },
    });
    return { ok: true, agentId: created.id, version: created.current_version };
  } catch (error) {
    return failFrom(error, "같은 이름의 Agent 가 이미 있습니다. 다른 이름으로 만드세요.");
  }
}

/**
 * Agent 의 정의를 고칩니다(`PUT /agents/{id}`) - **새 Version** 이 만들어집니다(spec 0007 2.8).
 *
 * `PUT` 은 정의를 통째로 교체합니다. 폼은 두 칸(시스템 프롬프트·모델 id)만 알기 때문에
 * 현재 정의를 api 에서 **이 액션이** 읽어 그 두 칸만 바꿉니다 - 브라우저가 정의를 보내지 않으므로
 * 폼에 없는 칸(tools·memory·knowledge·policy...)이 조용히 사라지지 않고, 브라우저가 정의 전체를
 * 쓸 수도 없습니다. 읽기와 쓰기 사이에 다른 저장이 끼면 api 가 `409` 를 돌려줍니다.
 */
export async function updateAgentAction(
  agentId: string,
  systemPrompt: string,
  modelId: string,
): Promise<SaveAgentResult> {
  if (typeof agentId !== "string" || !ID_SHAPE.test(agentId)) return fail(AGENT_NOT_FOUND);
  if (typeof systemPrompt !== "string" || systemPrompt.trim() === "") {
    return fail("시스템 프롬프트를 입력하세요.");
  }
  if (systemPrompt.length > MAX_PROMPT_LENGTH) {
    return fail("시스템 프롬프트는 20,000자까지입니다. 줄여서 다시 저장하세요.");
  }
  if (typeof modelId !== "string" || (modelId.trim() !== "" && !MODEL_SHAPE.test(modelId.trim()))) {
    return fail("모델 id 는 영문·숫자와 . _ : / - 만 쓸 수 있습니다. 비워 두면 배포 설정의 모델을 씁니다.");
  }

  const apiKey = process.env.AETHER_API_KEY?.trim();
  if (!apiKey) return noKey();

  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
    apiKey: process.env.AETHER_API_KEY,
  });

  try {
    const current = await client.getAgent(agentId);
    const updated = await client.updateAgent(agentId, {
      definition: {
        ...current.definition,
        system_prompt: systemPrompt,
        model: { ...current.definition.model, id: modelOrNull(modelId) },
      },
    });
    return { ok: true, agentId, version: updated.current_version };
  } catch (error) {
    return failFrom(
      error,
      "누군가 먼저 저장했습니다. 이 화면을 새로고침해 최신 정의를 본 뒤 다시 고치세요.",
    );
  }
}
