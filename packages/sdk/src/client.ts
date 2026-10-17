/**
 * `apps/web` 과 CLI 가 `apps/api` 를 아는 유일한 경로(spec 0001 2.4).
 *
 * 타입은 생성(`src/generated/openapi.d.ts`), 호출 함수는 수기입니다 — 인증 헤더·재시도·
 * 스트리밍(Phase 1)을 우리가 소유해야 하므로 생성기가 만드는 fetch 래퍼는 쓰지 않습니다.
 *
 * P1-1: Agent Registry 5경로(`createAgent`·`listAgents`·`getAgent`·`getAgentVersion`·
 * `updateAgent`)를 더합니다(spec 0002 2.2, D-17).
 *
 * P1-5b: Run 3경로(`runAgent`·`getRun`·`cancelRun`)를 더합니다(spec 0002 2.2, D-17).
 *
 * P1-6: `streamRunEvents` — `GET /runs/{id}/events` 를 `fetch` 로 열고 `./sse.ts` 의
 * `parseSse` 로 SSE 를 직접 파싱합니다(spec 0002 2.7, 2.17, D-4, C-4). 브라우저
 * `EventSource` 는 `Authorization` 헤더를 붙일 수 없어 쓰지 않습니다.
 *
 * MVP-0: 목록 5경로(`listRuns`·`listWorkflows`·`listWorkflowRuns`·`listKnowledgeSets`·
 * `listIngestions`)를 더합니다(spec 0006 2.3, D-9). 페이지 규칙은 `listAgents` 와 같습니다 —
 * `limit`·`cursor` 와 `{ items, next_cursor }`. 기존 함수는 바뀌지 않았습니다(D-11).
 */

import type { paths } from "./generated/openapi";
import type { RunEvent } from "./generated/events";
import { parseSse } from "./sse";

/** 생성된 스키마에서 유도한 반환 타입. 수기로 다시 적지 않습니다. */
export type HealthzResponse =
  paths["/healthz"]["get"]["responses"]["200"]["content"]["application/json"];

export type AgentResponse =
  paths["/agents"]["post"]["responses"]["201"]["content"]["application/json"];
export type ListAgentsResponse =
  paths["/agents"]["get"]["responses"]["200"]["content"]["application/json"];
export type AgentDetailResponse =
  paths["/agents/{agent_id}"]["get"]["responses"]["200"]["content"]["application/json"];
export type AgentVersionResponse =
  paths["/agents/{agent_id}/versions/{version}"]["get"]["responses"]["200"]["content"]["application/json"];
export type CreateAgentRequest =
  paths["/agents"]["post"]["requestBody"]["content"]["application/json"];
export type UpdateAgentRequest =
  paths["/agents/{agent_id}"]["put"]["requestBody"]["content"]["application/json"];

export type RunRequest =
  paths["/agents/{agent_id}/run"]["post"]["requestBody"]["content"]["application/json"];
export type RunAccepted =
  paths["/agents/{agent_id}/run"]["post"]["responses"]["202"]["content"]["application/json"];
export type RunDetailResponse =
  paths["/runs/{run_id}"]["get"]["responses"]["200"]["content"]["application/json"];
export type CancelAccepted =
  paths["/runs/{run_id}/cancel"]["post"]["responses"]["202"]["content"]["application/json"];

export type ListRunsResponse =
  paths["/runs"]["get"]["responses"]["200"]["content"]["application/json"];
export type ListWorkflowsResponse =
  paths["/workflows"]["get"]["responses"]["200"]["content"]["application/json"];
export type ListWorkflowRunsResponse =
  paths["/workflow-runs"]["get"]["responses"]["200"]["content"]["application/json"];
export type ListKnowledgeSetsResponse =
  paths["/knowledge-sets"]["get"]["responses"]["200"]["content"]["application/json"];
export type ListIngestionsResponse =
  paths["/knowledge-sets/{knowledge_set_id}/ingestions"]["get"]["responses"]["200"]["content"]["application/json"];

/** 상태 필터의 값 — 생성된 쿼리 파라미터 타입에서 유도합니다. */
export type RunStatus = NonNullable<NonNullable<paths["/runs"]["get"]["parameters"]["query"]>["status"]>;
export type WorkflowRunStatus = NonNullable<
  NonNullable<paths["/workflow-runs"]["get"]["parameters"]["query"]>["status"]
>;
export type IngestionStatus = NonNullable<
  NonNullable<
    paths["/knowledge-sets/{knowledge_set_id}/ingestions"]["get"]["parameters"]["query"]
  >["status"]
>;

/** 모든 목록 경로의 공통 페이지 파라미터(`GET /agents` 와 같은 규칙). */
export interface PageParams {
  /** 1~200, 기본 50. */
  limit?: number;
  /** 이전 응답의 `next_cursor`. 불투명 문자열입니다. */
  cursor?: string | null;
}
export interface ListRunsParams extends PageParams {
  status?: RunStatus | null;
}
export interface ListWorkflowRunsParams extends PageParams {
  status?: WorkflowRunStatus | null;
}
export interface ListIngestionsParams extends PageParams {
  status?: IngestionStatus | null;
}

export interface ListAgentsParams {
  limit?: number;
  cursor?: string | null;
  /** 이름 부분 일치(대소문자 구분 없음, spec 0002 2.2 `GET /agents?name=`). */
  name?: string | null;
}

export interface CreateClientOptions {
  /** `apps/api` 의 base URL. 끝의 `/` 유무는 상관없습니다. */
  baseUrl: string;
  /** 있으면 모든 요청에 `Authorization: Bearer <apiKey>` 헤더를 붙입니다(P0-9). */
  apiKey?: string;
  /** 주입 가능한 fetch. 기본값은 `globalThis.fetch` — 테스트가 가짜 fetch 를 꽂습니다. */
  fetch?: typeof globalThis.fetch;
}

export interface StreamRunEventsOptions {
  /** `Last-Event-ID` 헤더로 보냅니다 — 그 값 다음 `seq` 부터 재개합니다(spec 2.7). */
  lastEventId?: string;
  /** `fetch` 에 그대로 전달됩니다 — 중단하면 스트림 읽기가 `AbortError` 로 끝납니다. */
  signal?: AbortSignal;
}

export interface AetherClient {
  healthz(): Promise<HealthzResponse>;
  createAgent(body: CreateAgentRequest): Promise<AgentResponse>;
  listAgents(params?: ListAgentsParams): Promise<ListAgentsResponse>;
  getAgent(agentId: string): Promise<AgentDetailResponse>;
  getAgentVersion(agentId: string, version: number): Promise<AgentVersionResponse>;
  updateAgent(agentId: string, body: UpdateAgentRequest): Promise<AgentDetailResponse>;
  runAgent(agentId: string, body: RunRequest): Promise<RunAccepted>;
  getRun(runId: string): Promise<RunDetailResponse>;
  cancelRun(runId: string): Promise<CancelAccepted>;
  streamRunEvents(runId: string, options?: StreamRunEventsOptions): AsyncIterable<RunEvent>;
  listRuns(params?: ListRunsParams): Promise<ListRunsResponse>;
  listWorkflows(params?: PageParams): Promise<ListWorkflowsResponse>;
  listWorkflowRuns(params?: ListWorkflowRunsParams): Promise<ListWorkflowRunsResponse>;
  listKnowledgeSets(params?: PageParams): Promise<ListKnowledgeSetsResponse>;
  listIngestions(
    knowledgeSetId: string,
    params?: ListIngestionsParams,
  ): Promise<ListIngestionsResponse>;
}

function joinUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/+$/, "")}${path}`;
}

/** 공통 JSON 요청 — 실패 시 상태 코드와 경로를 담은 명확한 에러를 던집니다. */
async function requestJson<T>(
  doFetch: typeof globalThis.fetch,
  baseUrl: string,
  authHeaders: Record<string, string>,
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = { ...authHeaders };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await doFetch(joinUrl(baseUrl, path), {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(
      `aether-sdk: ${method} ${path} failed with status ${response.status} ${response.statusText}`,
    );
  }

  return (await response.json()) as T;
}

function buildListAgentsPath(params: ListAgentsParams | undefined): string {
  const query = new URLSearchParams();
  if (params?.limit !== undefined) {
    query.set("limit", String(params.limit));
  }
  if (params?.cursor) {
    query.set("cursor", params.cursor);
  }
  if (params?.name) {
    query.set("name", params.name);
  }
  const queryString = query.toString();
  return queryString ? `/agents?${queryString}` : "/agents";
}

/** 목록 경로의 쿼리 문자열 — 비어 있으면 경로만 돌려줍니다. 빈 `cursor`·`status` 는 보내지 않습니다. */
function buildListPath(
  path: string,
  params: (PageParams & { status?: string | null }) | undefined,
): string {
  const query = new URLSearchParams();
  if (params?.limit !== undefined) {
    query.set("limit", String(params.limit));
  }
  if (params?.cursor) {
    query.set("cursor", params.cursor);
  }
  if (params?.status) {
    query.set("status", params.status);
  }
  const queryString = query.toString();
  return queryString ? `${path}?${queryString}` : path;
}

/** `createClient({ baseUrl, apiKey?, fetch? })` — spec 0001 2.4 · spec 0002 2.2 의 계약. */
export function createClient(options: CreateClientOptions): AetherClient {
  const { baseUrl, apiKey } = options;
  const doFetch = options.fetch ?? globalThis.fetch;

  const headers: Record<string, string> = {};
  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`;
  }

  return {
    async healthz(): Promise<HealthzResponse> {
      const response = await doFetch(joinUrl(baseUrl, "/healthz"), {
        method: "GET",
        headers,
      });

      if (!response.ok) {
        throw new Error(
          `aether-sdk: GET /healthz failed with status ${response.status} ${response.statusText}`,
        );
      }

      return (await response.json()) as HealthzResponse;
    },

    async createAgent(body: CreateAgentRequest): Promise<AgentResponse> {
      return requestJson<AgentResponse>(doFetch, baseUrl, headers, "POST", "/agents", body);
    },

    async listAgents(params?: ListAgentsParams): Promise<ListAgentsResponse> {
      return requestJson<ListAgentsResponse>(
        doFetch,
        baseUrl,
        headers,
        "GET",
        buildListAgentsPath(params),
      );
    },

    async getAgent(agentId: string): Promise<AgentDetailResponse> {
      return requestJson<AgentDetailResponse>(
        doFetch,
        baseUrl,
        headers,
        "GET",
        `/agents/${agentId}`,
      );
    },

    async getAgentVersion(agentId: string, version: number): Promise<AgentVersionResponse> {
      return requestJson<AgentVersionResponse>(
        doFetch,
        baseUrl,
        headers,
        "GET",
        `/agents/${agentId}/versions/${version}`,
      );
    },

    async updateAgent(agentId: string, body: UpdateAgentRequest): Promise<AgentDetailResponse> {
      return requestJson<AgentDetailResponse>(
        doFetch,
        baseUrl,
        headers,
        "PUT",
        `/agents/${agentId}`,
        body,
      );
    },

    async runAgent(agentId: string, body: RunRequest): Promise<RunAccepted> {
      return requestJson<RunAccepted>(
        doFetch,
        baseUrl,
        headers,
        "POST",
        `/agents/${agentId}/run`,
        body,
      );
    },

    async getRun(runId: string): Promise<RunDetailResponse> {
      return requestJson<RunDetailResponse>(doFetch, baseUrl, headers, "GET", `/runs/${runId}`);
    },

    async cancelRun(runId: string): Promise<CancelAccepted> {
      return requestJson<CancelAccepted>(
        doFetch,
        baseUrl,
        headers,
        "POST",
        `/runs/${runId}/cancel`,
      );
    },

    async listRuns(params?: ListRunsParams): Promise<ListRunsResponse> {
      return requestJson<ListRunsResponse>(
        doFetch,
        baseUrl,
        headers,
        "GET",
        buildListPath("/runs", params),
      );
    },

    async listWorkflows(params?: PageParams): Promise<ListWorkflowsResponse> {
      return requestJson<ListWorkflowsResponse>(
        doFetch,
        baseUrl,
        headers,
        "GET",
        buildListPath("/workflows", params),
      );
    },

    async listWorkflowRuns(params?: ListWorkflowRunsParams): Promise<ListWorkflowRunsResponse> {
      return requestJson<ListWorkflowRunsResponse>(
        doFetch,
        baseUrl,
        headers,
        "GET",
        buildListPath("/workflow-runs", params),
      );
    },

    async listKnowledgeSets(params?: PageParams): Promise<ListKnowledgeSetsResponse> {
      return requestJson<ListKnowledgeSetsResponse>(
        doFetch,
        baseUrl,
        headers,
        "GET",
        buildListPath("/knowledge-sets", params),
      );
    },

    async listIngestions(
      knowledgeSetId: string,
      params?: ListIngestionsParams,
    ): Promise<ListIngestionsResponse> {
      return requestJson<ListIngestionsResponse>(
        doFetch,
        baseUrl,
        headers,
        "GET",
        buildListPath(`/knowledge-sets/${knowledgeSetId}/ingestions`, params),
      );
    },

    async *streamRunEvents(
      runId: string,
      options?: StreamRunEventsOptions,
    ): AsyncIterable<RunEvent> {
      const requestHeaders: Record<string, string> = { ...headers, Accept: "text/event-stream" };
      if (options?.lastEventId !== undefined) {
        requestHeaders["Last-Event-ID"] = options.lastEventId;
      }

      const path = `/runs/${runId}/events`;
      const response = await doFetch(joinUrl(baseUrl, path), {
        method: "GET",
        headers: requestHeaders,
        signal: options?.signal,
      });

      if (!response.ok) {
        throw new Error(
          `aether-sdk: GET ${path} failed with status ${response.status} ${response.statusText}`,
        );
      }
      if (!response.body) {
        throw new Error(`aether-sdk: GET ${path} response has no body to stream`);
      }

      for await (const sseEvent of parseSse(response.body, options?.signal)) {
        yield JSON.parse(sseEvent.data) as RunEvent;
      }
    },
  };
}
