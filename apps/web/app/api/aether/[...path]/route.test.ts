// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ALLOWED_ROUTES } from "@/lib/relay";

import { DELETE, GET, POST } from "./route";

// 명백한 가짜 키입니다. 실제 키 값은 어디에도 쓰지 않습니다.
const KEY = "aeth_test_not_a_real_key_0123456789";
const UPSTREAM = "http://api.test:8000";

const fetchMock = vi.fn();

function ctx(...path: string[]) {
  return { params: Promise.resolve({ path }) };
}

function req(path: string, init?: RequestInit) {
  return new Request(`http://web.test/api/aether${path}`, init);
}

function concretePath(segments: readonly string[]): string[] {
  return segments.map((s) => (s.startsWith(":") ? "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b" : s));
}

function jsonUpstream(extraHeaders: Record<string, string> = {}) {
  return new Response('{"items":[]}', {
    status: 200,
    headers: { "content-type": "application/json", ...extraHeaders },
  });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("AETHER_API_URL", UPSTREAM);
  vi.stubEnv("AETHER_API_KEY", KEY);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("web -> api 중계 (D-15, MVP-2p)", () => {
  it("리뷰 추가: 업스트림의 401·403 은 브라우저로 흘려보내지 않는다", async () => {
    // 401 이 그대로 나가면 화면은 그것을 "당신의 권한이 없다" 로 그립니다. 실제 뜻은
    // **서버의 키가 거부됐다** 이고 브라우저 쪽 사람은 그것을 고칠 수 없습니다. 키를
    // 안 넣은 경우(503)와 넣었는데 거부된 경우를 구별해야 "무엇을 해야 하나" 가 나옵니다.
    for (const status of [401, 403]) {
      fetchMock.mockReset();
      fetchMock.mockResolvedValue(
        new Response('{"detail":"unauthorized"}', {
          status,
          headers: { "content-type": "application/json" },
        }),
      );

      const response = await GET(req("/runs"), ctx("runs"));

      expect(response.status).toBe(502);
      const body = await response.text();
      expect(body).toContain("키");
      expect(body).not.toContain(KEY);
    }
  });

  it("판정 1 (D-15): 업스트림 호출에 Authorization: Bearer <키> 를 붙인다", async () => {
    fetchMock.mockResolvedValue(jsonUpstream());
    await GET(req("/agents"), ctx("agents"));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(String(url)).toBe(`${UPSTREAM}/agents`);
    expect(new Headers(init.headers).get("authorization")).toBe(`Bearer ${KEY}`);
  });

  it("판정 1 (D-15): 브라우저가 보낸 Authorization 은 버리고 서버 키만 쓴다", async () => {
    fetchMock.mockResolvedValue(jsonUpstream());
    await GET(req("/agents", { headers: { authorization: "Bearer from_browser" } }), ctx("agents"));

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(init.headers).get("authorization")).toBe(`Bearer ${KEY}`);
  });

  it("판정 2 (D-15): 중계 응답의 헤더·본문에 키가 없다 (업스트림이 Authorization 을 에코해도)", async () => {
    fetchMock.mockResolvedValue(
      jsonUpstream({
        authorization: `Bearer ${KEY}`,
        "x-echo": `Bearer ${KEY}`,
        "set-cookie": `k=${KEY}`,
      }),
    );
    const res = await GET(req("/agents"), ctx("agents"));

    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("application/json");
    expect(res.headers.get("authorization")).toBeNull();
    for (const [name, value] of res.headers) {
      expect(`${name}: ${value}`).not.toContain(KEY);
    }
    expect(await res.text()).not.toContain(KEY);
  });

  it("판정 3 (D-15): SSE 는 모여서 나가지 않는다 - 둘째 청크 전에 첫 청크를 읽는다", async () => {
    const enc = new TextEncoder();
    let releaseSecond!: () => void;
    const gate = new Promise<void>((r) => (releaseSecond = r));
    const upstreamBody = new ReadableStream<Uint8Array>({
      async start(controller) {
        controller.enqueue(enc.encode("id: 1\ndata: first\n\n"));
        await gate; // 테스트가 첫 청크를 확인하기 전에는 둘째가 나가지 않습니다.
        controller.enqueue(enc.encode("id: 2\ndata: second\n\n"));
        controller.close();
      },
    });
    fetchMock.mockResolvedValue(
      new Response(upstreamBody, { status: 200, headers: { "content-type": "text/event-stream" } }),
    );

    const res = await GET(req("/runs/abc/events"), ctx("runs", "abc", "events"));
    expect(res.headers.get("content-type")).toBe("text/event-stream");
    expect(res.headers.get("cache-control")).toBe("no-cache");
    expect(res.headers.get("connection")).toBe("keep-alive");

    const reader = res.body!.getReader();
    const first = await reader.read(); // 버퍼링 구현이면 gate 가 열리지 않아 여기서 멈춥니다.
    expect(new TextDecoder().decode(first.value)).toContain("data: first");
    releaseSecond();
    const second = await reader.read();
    expect(new TextDecoder().decode(second.value)).toContain("data: second");
  }, 3000);

  it("D-18: 허용 목록은 넷이고 전부 GET 이다 (MVP-2e 가 넓히지 않았다)", () => {
    // 타입 리터럴 `"GET"` 이 컴파일 시점에 막지만, **넓히지 않았다는 것**이 이 중계의
    // 계약이므로 실행 시점 단언도 둡니다 - 대화가 쓰기를 더할 자리가 여기였고
    // 사람이 서버 액션을 골랐습니다(D-18).
    expect(ALLOWED_ROUTES.map((r) => r.method)).toEqual(["GET", "GET", "GET", "GET"]);
  });

  it("판정 4 (D-15): 허용 목록의 모든 경로는 통과한다", async () => {
    expect(ALLOWED_ROUTES.length).toBe(4);
    for (const route of ALLOWED_ROUTES) {
      fetchMock.mockReset();
      fetchMock.mockResolvedValue(jsonUpstream());
      const path = concretePath(route.segments);
      const res = await GET(req(`/${path.join("/")}`), ctx(...path));
      expect(res.status, route.segments.join("/")).toBe(200);
      expect(fetchMock).toHaveBeenCalledTimes(1);
    }
  });

  it("판정 4 (D-15): POST·DELETE 는 업스트림을 부르지 않고 끊는다", async () => {
    const post = await POST(req("/agents", { method: "POST", body: "{}" }), ctx("agents"));
    const del = await DELETE(req("/runs/abc", { method: "DELETE" }), ctx("runs", "abc"));
    expect(post.status).toBe(405);
    expect(del.status).toBe(405);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    [["api-keys"]],
    [["runs", "abc", "cancel"]],
    [["runs", "abc", "events", "extra"]],
    [["agents", "abc"]],
    [["runs", "..", "events"]],
    [["runs", "a/b"]],
    [["healthz"]],
    [[]],
  ])("판정 4 (D-15): 허용 밖 경로 %j 는 업스트림을 부르지 않고 404", async (path) => {
    const res = await GET(req(`/${path.join("/")}`), ctx(...path));
    expect(res.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("판정 5 (D-15): 쿼리 문자열(?cursor=...)이 업스트림 URL 에 남는다", async () => {
    fetchMock.mockResolvedValue(jsonUpstream());
    await GET(req("/runs?cursor=abc&limit=5"), ctx("runs"));

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(String(url)).toBe(`${UPSTREAM}/runs?cursor=abc&limit=5`);
  });

  it.each([[""], ["   "], [undefined]])(
    "판정 6 (D-15): AETHER_API_KEY=%j 이면 업스트림을 부르지 않고 503 으로 말한다",
    async (value) => {
      if (value === undefined) vi.stubEnv("AETHER_API_KEY", "");
      else vi.stubEnv("AETHER_API_KEY", value);
      const res = await GET(req("/agents"), ctx("agents"));

      expect(res.status).toBe(503);
      expect(await res.text()).toContain("AETHER_API_KEY");
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it("D-15: 업스트림이 죽어도 502 이고 본문·로그에 키가 없다", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    fetchMock.mockRejectedValue(new Error(`connect failed with Bearer ${KEY}`));
    const res = await GET(req("/agents"), ctx("agents"));

    expect(res.status).toBe(502);
    expect(await res.text()).not.toContain(KEY);
    expect(JSON.stringify(spy.mock.calls)).not.toContain(KEY);
    spy.mockRestore();
  });
});
