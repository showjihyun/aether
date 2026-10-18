import { AetherHttpError, type StreamRunEventsOptions } from "@aether/sdk";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";

const streamRunEvents = vi.fn<(runId: string, options?: StreamRunEventsOptions) => unknown>();
const createClient = vi.fn<(options: { baseUrl: string }) => void>();
// `AetherHttpError` 는 실제 클래스를 통과시킵니다(runs/page.test.tsx 와 같은 이유).
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: { baseUrl: string }) => {
    createClient(options);
    return { streamRunEvents };
  },
}));

import { RunTabs } from "./RunTabs";

const RUN_ID = "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b";

function event(seq: number, type: string, payload: Record<string, unknown> = {}) {
  return { v: 1, run_id: RUN_ID, seq, at: "2026-10-18T10:00:00Z", type, payload };
}

interface Item {
  value?: unknown;
  error?: unknown;
  done?: boolean;
}

/** 테스트가 이벤트를 한 건씩 밀어 넣고, 끝내거나 실패시킬 수 있는 스트림. */
function channel() {
  const queue: Item[] = [];
  let wake: (() => void) | null = null;
  const signal = (item: Item) => {
    queue.push(item);
    wake?.();
  };
  const iterable = {
    async *[Symbol.asyncIterator]() {
      for (;;) {
        while (queue.length === 0) await new Promise<void>((resolve) => (wake = resolve));
        const item = queue.shift()!;
        if (item.error) throw item.error as Error;
        if (item.done) return;
        yield item.value;
      }
    },
  };
  // act 안에서 신호를 보내고 마이크로태스크를 한 번 비워 React 가 갱신하게 합니다.
  const send = (item: Item) =>
    act(async () => {
      signal(item);
      await Promise.resolve();
    });
  return {
    iterable,
    push: (value: unknown) => send({ value }),
    end: () => send({ done: true }),
    fail: (error: unknown) => send({ error }),
  };
}

function renderTabs(traceId: string | null = null) {
  render(
    <TooltipProvider>
      <RunTabs runId={RUN_ID} apiBaseUrl="http://localhost:8000" traceId={traceId} />
    </TooltipProvider>,
  );
}

function seqOrder(): string[] {
  return screen.queryAllByTestId("event-seq").map((node) => node.textContent ?? "");
}

describe("RunTabs 이벤트 타임라인", () => {
  beforeEach(() => {
    streamRunEvents.mockReset();
    createClient.mockClear();
  });
  afterEach(cleanup);

  it("MVP-2b: 이벤트는 도착하는 대로 하나씩 나타난다 (모아서 내보내지 않는다)", async () => {
    const ch = channel();
    streamRunEvents.mockReturnValue(ch.iterable);
    renderTabs();

    await ch.push(event(1, "run.status", { status: "running" }));
    expect(seqOrder()).toEqual(["1"]);

    await ch.push(event(2, "task.started", { task_id: "t", step: 1 }));
    expect(seqOrder()).toEqual(["1", "2"]);
  });

  it("MVP-2b: seq 순서로 렌더되고 run.finished 가 마지막이다", async () => {
    const ch = channel();
    streamRunEvents.mockReturnValue(ch.iterable);
    renderTabs();

    // 순서가 어긋나 도착해도 seq 로 놓입니다.
    await ch.push(event(2, "task.started"));
    await ch.push(event(1, "run.status"));
    await ch.push(event(3, "run.finished", { status: "succeeded" }));
    await ch.end();

    expect(seqOrder()).toEqual(["1", "2", "3"]);
    const types = screen.getAllByTestId("event-type").map((node) => node.textContent);
    expect(types.at(-1)).toBe("run.finished");
  });

  it("같은 seq 가 두 번 오면 한 번만 그린다", async () => {
    const ch = channel();
    streamRunEvents.mockReturnValue(ch.iterable);
    renderTabs();

    await ch.push(event(1, "run.status"));
    await ch.push(event(1, "run.status"));

    expect(seqOrder()).toEqual(["1"]);
  });

  it("MVP-2b: 스트림이 오류로 끊기면 그 사실이 화면에 나타난다", async () => {
    const ch = channel();
    streamRunEvents.mockReturnValue(ch.iterable);
    renderTabs();
    await ch.push(event(1, "run.status"));

    await ch.fail(new TypeError("network error"));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("연결이 끊겼습니다");
    // 기술 원문은 접힌 자리(DESIGN 7).
    const details = alert.querySelector("details");
    expect(details?.textContent).toContain("network error");
    expect(details?.open).toBe(false);
    // 끊기기 전에 받은 이벤트는 그대로 남는다.
    expect(seqOrder()).toEqual(["1"]);
  });

  it("MVP-2b: run.finished 없이 스트림이 닫혀도 끊김이다 (조용히 멈추지 않는다)", async () => {
    const ch = channel();
    streamRunEvents.mockReturnValue(ch.iterable);
    renderTabs();
    await ch.push(event(1, "run.status"));

    await ch.end();

    expect((await screen.findByRole("alert")).textContent).toContain("연결이 끊겼습니다");
  });

  it("run.finished 뒤의 정상 종료는 끊김이 아니다", async () => {
    const ch = channel();
    streamRunEvents.mockReturnValue(ch.iterable);
    renderTabs();
    await ch.push(event(1, "run.finished", { status: "succeeded" }));

    await ch.end();

    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("스트림이 끝났습니다.")).toBeTruthy();
  });

  it("HTTP 오류(404)로 열리지 못해도 끊김으로 나타난다", async () => {
    streamRunEvents.mockImplementation(() => ({
      [Symbol.asyncIterator]: () => ({
        next: () =>
          Promise.reject(
            new AetherHttpError(
              "aether-sdk: GET /runs/x/events failed with status 404 Not Found",
              404,
              "Not Found",
            ),
          ),
      }),
    }));
    renderTabs();

    expect((await screen.findByRole("alert")).textContent).toContain("연결이 끊겼습니다");
  });

  it("MVP-2b: 다시 연결 버튼 하나가 스트림을 처음부터 다시 연다 (재연결 로직은 없다)", async () => {
    const first = channel();
    const second = channel();
    streamRunEvents.mockReturnValueOnce(first.iterable).mockReturnValueOnce(second.iterable);
    renderTabs();
    await first.push(event(1, "run.status"));
    await first.fail(new TypeError("network error"));
    await screen.findByRole("alert");
    expect(streamRunEvents).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "다시 연결" }));
    await second.push(event(1, "run.status"));
    await second.push(event(2, "task.started"));

    expect(streamRunEvents).toHaveBeenCalledTimes(2);
    // Last-Event-ID 없이 열어 저장된 이벤트부터 재생됩니다 - 목록이 두 배가 되지 않는다.
    expect(streamRunEvents.mock.calls[1]?.[1]?.lastEventId).toBeUndefined();
    expect(seqOrder()).toEqual(["1", "2"]);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("스트림은 주어진 api 주소로 연다", () => {
    streamRunEvents.mockReturnValue(channel().iterable);
    renderTabs();

    expect(createClient).toHaveBeenCalledWith({ baseUrl: "http://localhost:8000" });
    expect(streamRunEvents.mock.calls[0]?.[0]).toBe(RUN_ID);
  });

  it("DESIGN 6: 이벤트 payload 는 항상 텍스트다 (HTML 로 해석되지 않는다)", async () => {
    const ch = channel();
    streamRunEvents.mockReturnValue(ch.iterable);
    renderTabs();

    await ch.push(
      event(1, "tool.result", { content: '<img src=x onerror="alert(1)"><script>x()</script>' }),
    );

    expect(document.querySelector("img")).toBeNull();
    expect(document.querySelector("script")).toBeNull();
    const pre = document.querySelector("pre");
    expect(pre?.className).toContain("font-mono");
    expect(pre?.textContent).toContain('<img src=x onerror=\\"alert(1)\\">');
  });

  it("unmount 하면 스트림을 중단한다", () => {
    streamRunEvents.mockReturnValue(channel().iterable);
    renderTabs();

    cleanup();

    const signal = streamRunEvents.mock.calls[0]?.[1]?.signal;
    expect(signal?.aborted).toBe(true);
  });
});

describe("RunTabs 탭", () => {
  beforeEach(() => {
    streamRunEvents.mockReset();
    streamRunEvents.mockReturnValue(channel().iterable);
  });
  afterEach(cleanup);

  function openTab(name: string) {
    fireEvent.mouseDown(screen.getByRole("tab", { name }), { button: 0 });
  }

  it("탭은 이벤트 타임라인 / 트레이스 둘이다 — 내용 없는 탭을 만들지 않는다", () => {
    // DESIGN 5절은 "입력" 탭도 적었지만 입력 본문은 어떤 API 응답에도 없습니다
    // (`GET /runs/{id}` 는 투영 열만 읽습니다). 내용이 "API 가 돌려주지 않습니다" 한 줄인
    // 탭은 9절이 금지하는 자리표시입니다 — 그래서 탭 자체를 두지 않고 DESIGN 을 고쳤습니다
    // (MVP-2b 리뷰 2026-10-18). 입력을 보이려면 API 가 그 열을 돌려줘야 합니다.
    renderTabs();

    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "이벤트 타임라인",
      "트레이스",
    ]);
  });

  it("트레이스 탭은 trace id 를 보인다", async () => {
    renderTabs("0af7651916cd43dd8448eb211c80319c");
    openTab("트레이스");

    await waitFor(() => expect(screen.getByText("0af7651916cd43dd8448eb211c80319c")).toBeTruthy());
  });

  it("trace id 가 없으면 없다고 말한다", async () => {
    renderTabs(null);
    openTab("트레이스");

    await waitFor(() => expect(screen.getByText("아직 trace id 가 없습니다.")).toBeTruthy());
  });

  it("탭을 옮겨도 스트림은 다시 열리지 않는다", () => {
    renderTabs();
    openTab("트레이스");
    openTab("이벤트 타임라인");

    expect(streamRunEvents).toHaveBeenCalledTimes(1);
  });
});
