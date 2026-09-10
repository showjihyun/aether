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
