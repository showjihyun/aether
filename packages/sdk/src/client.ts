/**
 * `apps/web` 과 CLI 가 `apps/api` 를 아는 유일한 경로(spec 0001 2.4).
 *
 * 타입은 생성(`src/generated/openapi.d.ts`), 호출 함수는 수기입니다 — 인증 헤더·재시도·
 * 스트리밍(Phase 1)을 우리가 소유해야 하므로 생성기가 만드는 fetch 래퍼는 쓰지 않습니다.
 *
 * P1-1: Agent Registry 5경로(`createAgent`·`listAgents`·`getAgent`·`getAgentVersion`·
 * `updateAgent`)를 더합니다(spec 0002 2.2, D-17).
 */

import type { paths } from "./generated/openapi";

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

export interface ListAgentsParams {
  limit?: number;
  cursor?: string | null;
}

export interface CreateClientOptions {
  /** `apps/api` 의 base URL. 끝의 `/` 유무는 상관없습니다. */
  baseUrl: string;
  /** 있으면 모든 요청에 `Authorization: Bearer <apiKey>` 헤더를 붙입니다(P0-9). */
  apiKey?: string;
  /** 주입 가능한 fetch. 기본값은 `globalThis.fetch` — 테스트가 가짜 fetch 를 꽂습니다. */
  fetch?: typeof globalThis.fetch;
}

export interface AetherClient {
  healthz(): Promise<HealthzResponse>;
  createAgent(body: CreateAgentRequest): Promise<AgentResponse>;
  listAgents(params?: ListAgentsParams): Promise<ListAgentsResponse>;
  getAgent(agentId: string): Promise<AgentDetailResponse>;
  getAgentVersion(agentId: string, version: number): Promise<AgentVersionResponse>;
  updateAgent(agentId: string, body: UpdateAgentRequest): Promise<AgentDetailResponse>;
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
  const queryString = query.toString();
  return queryString ? `/agents?${queryString}` : "/agents";
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
  };
}
