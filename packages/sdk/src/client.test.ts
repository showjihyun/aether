import { describe, expect, it, vi } from "vitest";

import { createClient } from "./client";

function fakeFetch(response: {
  ok: boolean;
  status?: number;
  statusText?: string;
  json?: unknown;
}) {
  return vi.fn<typeof globalThis.fetch>(() =>
    Promise.resolve({
      ok: response.ok,
      status: response.status ?? (response.ok ? 200 : 500),
      statusText: response.statusText ?? "",
      json: () => Promise.resolve(response.json),
    } as Response),
  );
}

describe("createClient().healthz()", () => {
  it("GETs <baseUrl>/healthz", async () => {
    const fetchMock = fakeFetch({
      ok: true,
      json: { status: "ok", service: "api", version: "dev" },
    });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await client.healthz();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/healthz",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("does not send an Authorization header when apiKey is absent", async () => {
    const fetchMock = fakeFetch({
      ok: true,
      json: { status: "ok", service: "api", version: "dev" },
    });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await client.healthz();

    const call = fetchMock.mock.calls[0];
    if (!call) {
      throw new Error("fetch was not called");
    }
    const [, init] = call;
    const headers = init?.headers as Record<string, string> | undefined;
    expect(headers?.Authorization).toBeUndefined();
  });

  it("sends Authorization: Bearer <apiKey> when apiKey is present", async () => {
    const fetchMock = fakeFetch({
      ok: true,
      json: { status: "ok", service: "api", version: "dev" },
    });
    const client = createClient({
      baseUrl: "http://localhost:8000",
      apiKey: "aeth_secret",
      fetch: fetchMock,
    });

    await client.healthz();

    const call = fetchMock.mock.calls[0];
    if (!call) {
      throw new Error("fetch was not called");
    }
    const [, init] = call;
    const headers = init?.headers as Record<string, string> | undefined;
    expect(headers?.Authorization).toBe("Bearer aeth_secret");
  });

  it("resolves with the parsed JSON body", async () => {
    const fetchMock = fakeFetch({
      ok: true,
      json: { status: "ok", service: "api", version: "1.2.3" },
    });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    const result = await client.healthz();

    expect(result).toEqual({ status: "ok", service: "api", version: "1.2.3" });
  });

  it("throws a clear error when the response is not ok (e.g. 500)", async () => {
    const fetchMock = fakeFetch({ ok: false, status: 500, statusText: "Internal Server Error" });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await expect(client.healthz()).rejects.toThrow(/500/);
  });
});

function callInit(fetchMock: ReturnType<typeof fakeFetch>): RequestInit {
  const call = fetchMock.mock.calls[0];
  if (!call) {
    throw new Error("fetch was not called");
  }
  const [, init] = call;
  if (!init) {
    throw new Error("fetch was called without an init object");
  }
  return init;
}

function callUrl(fetchMock: ReturnType<typeof fakeFetch>): string {
  const call = fetchMock.mock.calls[0];
  if (!call) {
    throw new Error("fetch was not called");
  }
  return call[0] as string;
}

describe("createClient().createAgent()", () => {
  it("POSTs the definition to /agents with Authorization and Content-Type", async () => {
    const fetchMock = fakeFetch({
      ok: true,
      status: 201,
      json: {
        id: "11111111-1111-1111-1111-111111111111",
        name: "weather-bot",
        current_version: 1,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    });
    const client = createClient({
      baseUrl: "http://localhost:8000",
      apiKey: "aeth_secret",
      fetch: fetchMock,
    });

    const result = await client.createAgent({
      name: "weather-bot",
      definition: { schema_version: 1, system_prompt: "You are a helper." },
    });

    expect(callUrl(fetchMock)).toBe("http://localhost:8000/agents");
    const init = callInit(fetchMock);
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer aeth_secret");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({
      name: "weather-bot",
      definition: { schema_version: 1, system_prompt: "You are a helper." },
    });
    expect(result.current_version).toBe(1);
  });

  it("throws a clear error on 409 agent_name_taken", async () => {
    const fetchMock = fakeFetch({ ok: false, status: 409, statusText: "Conflict" });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await expect(
      client.createAgent({
        name: "dup",
        definition: { schema_version: 1, system_prompt: "x" },
      }),
    ).rejects.toThrow(/409/);
  });
});

describe("createClient().listAgents()", () => {
  it("GETs /agents without query params when none are given", async () => {
    const fetchMock = fakeFetch({ ok: true, json: { items: [], next_cursor: null } });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await client.listAgents();

    expect(callUrl(fetchMock)).toBe("http://localhost:8000/agents");
  });

  it("encodes limit and cursor as query params", async () => {
    const fetchMock = fakeFetch({ ok: true, json: { items: [], next_cursor: null } });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await client.listAgents({ limit: 10, cursor: "opaque-cursor" });

    expect(callUrl(fetchMock)).toBe(
      "http://localhost:8000/agents?limit=10&cursor=opaque-cursor",
    );
  });
});

describe("createClient().getAgent()", () => {
  it("GETs /agents/{id}", async () => {
    const fetchMock = fakeFetch({
      ok: true,
      json: {
        id: "id-1",
        name: "weather-bot",
        current_version: 1,
        definition: { schema_version: 1, system_prompt: "x" },
        versions: [{ version: 1, created_at: "2026-01-01T00:00:00Z" }],
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await client.getAgent("id-1");

    expect(callUrl(fetchMock)).toBe("http://localhost:8000/agents/id-1");
    expect(callInit(fetchMock).method).toBe("GET");
  });

  it("throws a clear error on 404 agent_not_found", async () => {
    const fetchMock = fakeFetch({ ok: false, status: 404, statusText: "Not Found" });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await expect(client.getAgent("missing")).rejects.toThrow(/404/);
  });
});

describe("createClient().getAgentVersion()", () => {
  it("GETs /agents/{id}/versions/{version}", async () => {
    const fetchMock = fakeFetch({
      ok: true,
      json: {
        agent_id: "id-1",
        version: 1,
        definition: { schema_version: 1, system_prompt: "x" },
        created_at: "2026-01-01T00:00:00Z",
      },
    });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await client.getAgentVersion("id-1", 1);

    expect(callUrl(fetchMock)).toBe("http://localhost:8000/agents/id-1/versions/1");
  });
});

describe("createClient().updateAgent()", () => {
  it("PUTs the definition to /agents/{id}", async () => {
    const fetchMock = fakeFetch({
      ok: true,
      json: {
        id: "id-1",
        name: "weather-bot",
        current_version: 2,
        definition: { schema_version: 1, system_prompt: "v2" },
        versions: [
          { version: 1, created_at: "2026-01-01T00:00:00Z" },
          { version: 2, created_at: "2026-01-02T00:00:00Z" },
        ],
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-02T00:00:00Z",
      },
    });
    const client = createClient({
      baseUrl: "http://localhost:8000",
      apiKey: "aeth_secret",
      fetch: fetchMock,
    });

    const result = await client.updateAgent("id-1", {
      definition: { schema_version: 1, system_prompt: "v2" },
    });

    expect(callUrl(fetchMock)).toBe("http://localhost:8000/agents/id-1");
    const init = callInit(fetchMock);
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({
      definition: { schema_version: 1, system_prompt: "v2" },
    });
    expect(result.current_version).toBe(2);
  });

  it("throws a clear error on 409 agent_version_conflict", async () => {
    const fetchMock = fakeFetch({ ok: false, status: 409, statusText: "Conflict" });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await expect(
      client.updateAgent("id-1", { definition: { schema_version: 1, system_prompt: "x" } }),
    ).rejects.toThrow(/409/);
  });
});
