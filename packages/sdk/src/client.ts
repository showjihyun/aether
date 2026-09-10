/**
 * `apps/web` 과 CLI 가 `apps/api` 를 아는 유일한 경로(spec 0001 2.4).
 *
 * 타입은 생성(`src/generated/openapi.d.ts`), 호출 함수는 수기입니다 — 인증 헤더·재시도·
 * 스트리밍(Phase 1)을 우리가 소유해야 하므로 생성기가 만드는 fetch 래퍼는 쓰지 않습니다.
 */

import type { paths } from "./generated/openapi";

/** 생성된 스키마에서 유도한 반환 타입. 수기로 다시 적지 않습니다. */
export type HealthzResponse =
  paths["/healthz"]["get"]["responses"]["200"]["content"]["application/json"];

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
}

function joinUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/+$/, "")}${path}`;
}

/** `createClient({ baseUrl, apiKey?, fetch? })` — spec 0001 2.4 의 계약. */
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
  };
}
