// web 서버 -> api 중계 (D-15, MVP-2p). 브라우저는 same-origin 으로만 부르고 키는 이 프로세스 안에만 있습니다.
// 이 중계는 키를 들고 있으므로 **열어 둔 만큼이 그대로 공개**됩니다 - 아래 허용 목록이 그 전부입니다.

export interface AllowedRoute {
  method: "GET";
  /** `:이름` 으로 시작하는 조각은 id 한 칸(UUID 꼴 문자만)이고, 나머지는 글자 그대로입니다. */
  segments: readonly string[];
}

// 화면이 실제로 쓰는 것만. MVP-2c 가 대화(POST /agents/{id}/run)를 더할 때 여기서 명시적으로 넓힙니다.
export const ALLOWED_ROUTES: readonly AllowedRoute[] = [
  { method: "GET", segments: ["agents"] },
  { method: "GET", segments: ["runs"] },
  { method: "GET", segments: ["runs", ":id"] },
  { method: "GET", segments: ["runs", ":id", "events"] },
];

const ID_SEGMENT = /^[A-Za-z0-9_-]+$/;

function matches(route: AllowedRoute, method: string, path: readonly string[]): boolean {
  if (route.method !== method || route.segments.length !== path.length) return false;
  return route.segments.every((expected, i) =>
    expected.startsWith(":") ? ID_SEGMENT.test(path[i] ?? "") : expected === path[i],
  );
}

// 업스트림으로 보내는 요청 헤더: 이 둘뿐입니다. Authorization·Cookie 는 브라우저 것을 받지 않습니다.
const FORWARD_REQUEST_HEADERS = ["accept", "last-event-id"] as const;
// 브라우저로 돌려주는 응답 헤더: 허용 목록입니다. 업스트림 헤더를 통째로 베끼지 않습니다.
const FORWARD_RESPONSE_HEADERS = ["content-type", "etag", "last-modified", "retry-after"] as const;

function text(status: number, message: string, extra?: Record<string, string>): Response {
  return new Response(JSON.stringify({ detail: message }), {
    status,
    headers: { "content-type": "application/json", ...extra },
  });
}

export async function relay(request: Request, path: readonly string[]): Promise<Response> {
  const method = request.method.toUpperCase();
  const allowed = ALLOWED_ROUTES.filter((r) => matches(r, "GET", path));
  if (allowed.length === 0) return text(404, "not found");
  if (!ALLOWED_ROUTES.some((r) => matches(r, method, path))) {
    return text(405, "method not allowed", { allow: "GET" });
  }

  const apiKey = (process.env.AETHER_API_KEY ?? "").trim();
  if (!apiKey) {
    // 401 로 흘려보내면 "키를 안 넣었다" 와 "키가 틀렸다" 가 구별되지 않습니다.
    return text(
      503,
      "AETHER_API_KEY 가 설정되지 않았습니다. web 컨테이너에 api 키를 주입하세요(infra/docker/.env.example 의 AETHER_WEB_API_KEY).",
    );
  }

  const base = (process.env.AETHER_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
  const search = new URL(request.url).search;
  const upstreamUrl = `${base}/${path.map(encodeURIComponent).join("/")}${search}`;

  const headers = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("authorization", `Bearer ${apiKey}`);

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl, {
      method: "GET",
      headers,
      redirect: "manual",
      signal: request.signal, // 브라우저가 닫으면 업스트림도 닫힙니다.
    });
  } catch {
    // 오류 객체를 본문·로그에 옮기지 않습니다(키가 섞일 수 있는 자리).
    console.error("aether relay: upstream request failed");
    return text(502, "api 에 닿지 못했습니다.");
  }

  if (upstream.status === 401 || upstream.status === 403) {
    // 업스트림이 **서버의 키**를 거부한 것입니다. 그대로 흘려보내면 화면이 그것을
    // "당신의 권한이 없다" 로 그리는데, 브라우저 쪽 사람은 고칠 수 없는 문제입니다.
    // 키가 없는 경우(503)와 넣었는데 거부된 경우를 구별해 둡니다 - 그 둘의 다음 행동이
    // 다릅니다(주입 / 재발급). 업스트림 본문은 넘기지 않습니다(리뷰 2026-10-18).
    console.error(`aether relay: api rejected the server key (status ${upstream.status})`);
    return text(502, "api 가 web 의 키를 거부했습니다. 키를 다시 발급해 주입하세요.");
  }

  const out = new Headers();
  for (const name of FORWARD_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }
  if (upstream.headers.get("content-type")?.startsWith("text/event-stream")) {
    out.set("cache-control", "no-cache");
    out.set("connection", "keep-alive");
    out.set("x-accel-buffering", "no");
  }
  // body 는 ReadableStream 그대로입니다 - text()/json() 으로 받으면 SSE 가 모여서 나갑니다.
  return new Response(upstream.body, { status: upstream.status, headers: out });
}
