"use server";

import { AetherHttpError, createClient, type CreateWorkflowRequest } from "@aether/sdk";

// "use server" 파일은 async 함수만 내보낼 수 있습니다(타입은 지워지므로 괜찮습니다).
// 상수·보조 함수는 내보내지 않습니다.
//
// `app/agents/actions.ts` 가 세운 쓰기 경로의 모양을 그대로 따릅니다(spec 0007 D-2, R-2):
//   1. 인자는 원시 타입뿐이고, 각 인자는 본문의 **첫 줄들에서** typeof + 내용 검사를 거칩니다.
//   2. 요청 본문은 web 이 조립합니다. 브라우저가 보낸 객체를 api 로 넘기지 않습니다.
//   3. api 호출은 SDK 로만 합니다. 실패는 던지지 않고 `{ ok: false, message }` 로 돌려줍니다.
//   4. 분기는 `AetherHttpError.status` 필드로 합니다. 메시지에 키·URL·업스트림 본문·SDK 오류
//      원문을 넣지 않습니다.
//
// 그래프는 **JSON 문자열 하나**로 옵니다(DESIGN 7.3) - 객체·배열을 통째로 받으면 브라우저가 요청
// 본문을 쓰는 것과 같아집니다. 모양은 **이 액션이** 소유합니다: 파싱한 뒤 노드·간선을 허용 목록의
// 키로 다시 조립하므로 좌표(D-9)나 종류별 칸이 끼어 있어도 api 로 가지 않습니다.
// `tests/arch/test_use_server_actions_are_sdk_only_and_validated.py` 가 1·3 을 파일에서 고정합니다.

export type WorkflowViolation = { reason: string; nodeId: string | null };

export type SaveWorkflowResult =
  | { ok: true; workflowId: string; version: number }
  | { ok: false; message: string; violations?: WorkflowViolation[] };

const MAX_NAME_LENGTH = 100;
// 브라우저가 보낸 문자열이 메모리를 먹는 것을 막는 자리입니다(api 가 거부할 것을 먼저 거부하는 것이 아닙니다).
const MAX_GRAPH_JSON_LENGTH = 200_000;
const MAX_NODES = 200;
const MAX_EDGES = 400;
const MAX_LABEL_LENGTH = 100;
const MAX_REASON_LENGTH = 100;
// `app/agents/actions.ts` 의 id 칸과 같은 꼴입니다.
const ID_SHAPE = /^[A-Za-z0-9_-]{1,128}$/;
// api 의 `NodeKind` 열셋입니다(DESIGN 6절). SDK 타입과 `Record` 로 묶여 있어 api 에 종류가
// 생기거나 사라지면 **컴파일이 깨집니다** - 그때 이 표와 6절을 함께 고칩니다.
type Kind = CreateWorkflowRequest["nodes"][number]["kind"];
const KIND_SET: Record<Kind, true> = {
  START: true, END: true, AGENT: true, CONDITION: true, PARALLEL: true, JOIN: true, LOOP: true,
  WAIT: true, LLM: true, MCP: true, TOOL: true, HUMAN: true, APPROVAL: true,
};

type CleanNode = { id: string; kind: Kind };
type CleanEdge = { source: string; target: string; label?: string };

function fail(message: string, violations?: WorkflowViolation[]): SaveWorkflowResult {
  return violations === undefined ? { ok: false, message } : { ok: false, message, violations };
}

const BAD_GRAPH = "그래프의 모양이 올바르지 않습니다. 화면을 새로고침한 뒤 다시 만드세요.";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** 허용 목록의 키로 다시 조립합니다. 어긋나면 null - 좌표 같은 여분의 키는 여기서 사라집니다. */
function cleanGraph(parsed: unknown): { nodes: CleanNode[]; edges: CleanEdge[] } | null {
  if (!isRecord(parsed) || !Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) return null;
  if (parsed.nodes.length > MAX_NODES || parsed.edges.length > MAX_EDGES) return null;

  const nodes: CleanNode[] = [];
  for (const node of parsed.nodes as unknown[]) {
    if (!isRecord(node)) return null;
    const { id, kind } = node;
    if (typeof id !== "string" || !ID_SHAPE.test(id)) return null;
    if (typeof kind !== "string" || !Object.hasOwn(KIND_SET, kind)) return null;
    nodes.push({ id, kind: kind as Kind });
  }
  // 중복 id 는 막지 않습니다 - 그 판정은 api 의 duplicate_node_id 이고, 사유가 노드 위에 보입니다.
  const known = new Set(nodes.map((node) => node.id));

  const edges: CleanEdge[] = [];
  for (const edge of parsed.edges as unknown[]) {
    if (!isRecord(edge)) return null;
    const { source, target, label } = edge;
    if (typeof source !== "string" || !known.has(source)) return null;
    if (typeof target !== "string" || !known.has(target)) return null;
    if (label === undefined || label === null) {
      edges.push({ source, target });
    } else if (typeof label === "string" && label.length <= MAX_LABEL_LENGTH) {
      edges.push({ source, target, label });
    } else {
      return null;
    }
  }
  return { nodes, edges };
}

/** 400 본문에서 위반 목록을 읽습니다. 약속한 모양이 아니면 null, 모양이 어긋난 항목은 버립니다. */
function violationsFrom(body: unknown): WorkflowViolation[] | null {
  if (!isRecord(body) || body.detail !== "invalid_workflow_graph" || !Array.isArray(body.violations)) {
    return null;
  }
  const found: WorkflowViolation[] = [];
  for (const item of body.violations as unknown[]) {
    if (!isRecord(item)) continue;
    const { reason, node_id: nodeId } = item;
    if (typeof reason !== "string" || reason.length === 0 || reason.length > MAX_REASON_LENGTH) continue;
    if (nodeId !== null && typeof nodeId !== "string") continue;
    found.push({ reason, nodeId });
  }
  return found;
}

function failFrom(error: unknown): SaveWorkflowResult {
  if (error instanceof AetherHttpError) {
    if (error.status === 400) {
      const violations = violationsFrom(error.body);
      if (violations !== null) {
        return fail("api 가 이 그래프를 저장하지 않았습니다. 아래 사유를 고친 뒤 다시 저장하세요.", violations);
      }
    }
    if (error.status === 401 || error.status === 403) {
      // `lib/relay.ts` 가 하는 말과 같습니다 - 두 경로가 같은 말을 해야 합니다.
      return fail("api 가 web 의 키를 거부했습니다. 키를 다시 발급해 주입하세요.");
    }
    // 상태 코드가 있다는 것은 **닿았다**는 뜻입니다. 응답 본문은 넘기지 않고 상태 코드만 보입니다.
    return fail(
      `api 가 이 요청을 거절했습니다(상태 ${error.status}). 입력을 확인한 뒤 다시 저장하고, 계속되면 api 로그를 보세요.`,
    );
  }
  return fail("api 에 닿지 못했습니다. api 가 떠 있는지 확인한 뒤 다시 시도하세요.");
}

/**
 * Workflow 를 만듭니다(`POST /workflows`). Version 1 이 함께 생깁니다.
 *
 * 서버 액션은 **어떤 브라우저 요청이든 올 수 있는 진입점**이라 인자를 신뢰하지 않습니다.
 * 사용자 세션·권한은 이 단위 밖입니다(Phase 8, spec 0007 2.2·C-2). 좌표는 받지도 보내지도
 * 않습니다(D-9).
 */
export async function createWorkflowAction(
  name: string,
  graphJson: string,
): Promise<SaveWorkflowResult> {
  if (typeof name !== "string" || name.trim() === "") return fail("이름을 입력하세요.");
  if (name.trim().length > MAX_NAME_LENGTH) return fail("이름은 100자까지입니다. 줄여서 다시 저장하세요.");
  if (typeof graphJson !== "string" || graphJson.length === 0 || graphJson.length > MAX_GRAPH_JSON_LENGTH) {
    return fail(BAD_GRAPH);
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(graphJson);
  } catch {
    return fail(BAD_GRAPH);
  }
  const graph = cleanGraph(parsed);
  if (graph === null) return fail(BAD_GRAPH);

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
    const created = await client.createWorkflow({
      name: name.trim(),
      nodes: graph.nodes,
      edges: graph.edges,
    });
    return { ok: true, workflowId: created.id, version: created.current_version };
  } catch (error) {
    return failFrom(error);
  }
}
