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

// spec 0002 2.2, D-9, D-17: runAgent / getRun / cancelRun.

describe("createClient().runAgent()", () => {
  it("POSTs the input to /agents/{id}/run with Authorization and Content-Type", async () => {
    const fetchMock = fakeFetch({
      ok: true,
      status: 202,
      json: {
        run_id: "11111111-1111-1111-1111-111111111111",
        agent_id: "id-1",
        agent_version: 1,
        status: "queued",
        requested_at: "2026-01-01T00:00:00Z",
        requested_by: "22222222-2222-2222-2222-222222222222",
      },
    });
    const client = createClient({
      baseUrl: "http://localhost:8000",
      apiKey: "aeth_secret",
      fetch: fetchMock,
    });

    const result = await client.runAgent("id-1", { input: "do it" });

    expect(callUrl(fetchMock)).toBe("http://localhost:8000/agents/id-1/run");
    const init = callInit(fetchMock);
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer aeth_secret");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({ input: "do it" });
    expect(result.status).toBe("queued");
  });

  it("includes agent_version in the body when given", async () => {
    const fetchMock = fakeFetch({
      ok: true,
      status: 202,
      json: {
        run_id: "id",
        agent_id: "id-1",
        agent_version: 2,
        status: "queued",
        requested_at: "2026-01-01T00:00:00Z",
        requested_by: "id-key",
      },
    });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await client.runAgent("id-1", { input: "do it", agent_version: 2 });

    const init = callInit(fetchMock);
    expect(JSON.parse(init.body as string)).toEqual({ input: "do it", agent_version: 2 });
  });

  it("throws a clear error on 404 agent_not_found", async () => {
    const fetchMock = fakeFetch({ ok: false, status: 404, statusText: "Not Found" });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await expect(client.runAgent("missing", { input: "x" })).rejects.toThrow(/404/);
  });
});

describe("createClient().getRun()", () => {
  it("GETs /runs/{id}", async () => {
    const fetchMock = fakeFetch({
      ok: true,
      json: {
        run_id: "run-1",
        agent_id: "id-1",
        agent_version: 1,
        status: "queued",
        requested_at: "2026-01-01T00:00:00Z",
        requested_by: "key-1",
        started_at: null,
        finished_at: null,
        failure_reason: null,
        trace_id: null,
        cancel_requested_at: null,
      },
    });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    const result = await client.getRun("run-1");

    expect(callUrl(fetchMock)).toBe("http://localhost:8000/runs/run-1");
    expect(callInit(fetchMock).method).toBe("GET");
    expect(result.status).toBe("queued");
  });

  it("throws a clear error on 404 run_not_found", async () => {
    const fetchMock = fakeFetch({ ok: false, status: 404, statusText: "Not Found" });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await expect(client.getRun("missing")).rejects.toThrow(/404/);
  });
});

describe("createClient().cancelRun()", () => {
  it("POSTs /runs/{id}/cancel with Authorization", async () => {
    const fetchMock = fakeFetch({
      ok: true,
      status: 202,
      json: {
        run_id: "run-1",
        status: "queued",
        cancel_requested_at: "2026-01-01T00:00:00Z",
      },
    });
    const client = createClient({
      baseUrl: "http://localhost:8000",
      apiKey: "aeth_secret",
      fetch: fetchMock,
    });

    const result = await client.cancelRun("run-1");

    expect(callUrl(fetchMock)).toBe("http://localhost:8000/runs/run-1/cancel");
    const init = callInit(fetchMock);
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer aeth_secret");
    expect(result.cancel_requested_at).toBe("2026-01-01T00:00:00Z");
  });

  it("throws a clear error on 404 run_not_found", async () => {
    const fetchMock = fakeFetch({ ok: false, status: 404, statusText: "Not Found" });
    const client = createClient({ baseUrl: "http://localhost:8000", fetch: fetchMock });

    await expect(client.cancelRun("missing")).rejects.toThrow(/404/);
  });
});
