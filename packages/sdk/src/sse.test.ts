import { describe, expect, it } from "vitest";

import { parseSse } from "./sse";

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (index >= chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(chunks[index]));
      index += 1;
    },
  });
}

interface ControllableStream {
  stream: ReadableStream<Uint8Array>;
  push: (chunk: string) => void;
  close: () => void;
}

function controllableStream(): ControllableStream {
  const encoder = new TextEncoder();
  let controllerRef: ReadableStreamDefaultController<Uint8Array> | undefined;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controllerRef = controller;
    },
  });
  return {
    stream,
    push: (chunk: string) => controllerRef?.enqueue(encoder.encode(chunk)),
    close: () => controllerRef?.close(),
  };
}

async function collect<T>(iterable: AsyncIterable<T>, limit: number): Promise<T[]> {
  const items: T[] = [];
  for await (const item of iterable) {
    items.push(item);
    if (items.length >= limit) {
      break;
    }
  }
  return items;
}

describe("parseSse", () => {
  it("parses a single event split across two chunks", async () => {
    // 한 이벤트가 청크 경계에서 잘려도 다음 청크와 이어붙여 파싱됩니다.
    const stream = streamFromChunks(["id: 1\nev", 'ent: run.status\ndata: {"a":1}\n\n']);

    const events = await collect(parseSse(stream), 1);

    expect(events).toEqual([{ id: "1", event: "run.status", data: '{"a":1}' }]);
  });

  it("parses two events delivered in a single chunk", async () => {
    const stream = streamFromChunks([
      'id: 1\nevent: run.status\ndata: {"a":1}\n\nid: 2\nevent: task.started\ndata: {"b":2}\n\n',
    ]);

    const events = await collect(parseSse(stream), 2);

    expect(events).toEqual([
      { id: "1", event: "run.status", data: '{"a":1}' },
      { id: "2", event: "task.started", data: '{"b":2}' },
    ]);
  });

  it("joins multiline data: fields with newlines", async () => {
    const stream = streamFromChunks(["id: 1\nevent: run.status\ndata: line one\ndata: line two\n\n"]);

    const events = await collect(parseSse(stream), 1);

    expect(events).toEqual([{ id: "1", event: "run.status", data: "line one\nline two" }]);
  });

  it("assembles id: and event: fields even when the field values are split", async () => {
    // id/event 값 자체가 청크 경계로 잘리는 경우도 버퍼링됩니다.
    const stream = streamFromChunks(["id: 1", "23\nevent: run.f", 'inished\ndata: {}\n\n']);

    const events = await collect(parseSse(stream), 1);

    expect(events).toEqual([{ id: "123", event: "run.finished", data: "{}" }]);
  });

  it("treats a blank line as the event separator and skips blank-only stretches", async () => {
    const stream = streamFromChunks(["\n\nid: 1\nevent: run.status\ndata: ok\n\n\n"]);

    const events = await collect(parseSse(stream), 1);

    expect(events).toEqual([{ id: "1", event: "run.status", data: "ok" }]);
  });

  it("accepts \\r\\n line endings", async () => {
    const stream = streamFromChunks(["id: 1\r\nevent: run.status\r\ndata: ok\r\n\r\n"]);

    const events = await collect(parseSse(stream), 1);

    expect(events).toEqual([{ id: "1", event: "run.status", data: "ok" }]);
  });

  it("stops iteration with an AbortError once the signal is aborted", async () => {
    const controller = new AbortController();
    const { stream, push } = controllableStream();
    const iterator = parseSse(stream, controller.signal)[Symbol.asyncIterator]();

    push("id: 1\nevent: run.status\ndata: ok\n\n");
    const first = await iterator.next();
    expect(first.value).toEqual({ id: "1", event: "run.status", data: "ok" });

    controller.abort();

    await expect(iterator.next()).rejects.toMatchObject({ name: "AbortError" });
  });

  it("rejects immediately when the signal is already aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    const { stream } = controllableStream();

    const iterator = parseSse(stream, controller.signal)[Symbol.asyncIterator]();

    await expect(iterator.next()).rejects.toMatchObject({ name: "AbortError" });
  });
});
