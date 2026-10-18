import { AetherHttpError } from "@aether/sdk";
import type { StreamRunEventsOptions } from "@aether/sdk";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const streamRunEvents = vi.fn<(runId: string, options?: StreamRunEventsOptions) => unknown>();
const createClient = vi.fn<(options: Record<string, unknown>) => void>();
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: Record<string, unknown>) => {
    createClient(options);
    return { streamRunEvents };
  },
}));

const startRun = vi.fn<(agentId: string, input: string) => Promise<unknown>>();
vi.mock("./actions", () => ({
  startRun: (agentId: string, input: string) => startRun(agentId, input),
}));

import { Chat } from "./Chat";

const AGENT_ID = "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b";
const RUN_ID = "0199ffee-0000-7000-8000-000000000001";
const RUN_ID_2 = "0199ffee-0000-7000-8000-000000000002";

function event(runId: string, seq: number, type: string, payload: Record<string, unknown> = {}) {
  return { v: 1, run_id: runId, seq, at: "2026-10-18T10:00:00Z", type, payload };
}

interface Item {
  value?: unknown;
  error?: unknown;
  done?: boolean;
}

/** MVP-2b 의 RunTabs.test 와 같은 모양: 테스트가 이벤트를 한 건씩 밀어 넣는다. */
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
  const push = (item: Item) =>
    act(async () => {
      signal(item);
      await Promise.resolve();
    });
  return {
    iterable,
    push: (value: unknown) => push({ value }),
    end: () => push({ done: true }),
    fail: (error: unknown) => push({ error }),
  };
}

function renderChat(memoryEnabled = false) {
  render(<Chat agentId={AGENT_ID} agentName="billing-helper" memoryEnabled={memoryEnabled} />);
}

async function send(text: string) {
  fireEvent.change(screen.getByRole("textbox"), { target: { value: text } });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "보내기" }));
    await Promise.resolve();
  });
}

/** 보내고, 스트림을 연 채널을 돌려준다. */
async function sendAndOpen(text = "안녕", runId = RUN_ID) {
  const ch = channel();
  startRun.mockResolvedValueOnce({ ok: true, runId });
  streamRunEvents.mockReturnValueOnce(ch.iterable);
  const opened = streamRunEvents.mock.calls.length;
  await send(text);
  await waitFor(() => expect(streamRunEvents.mock.calls.length).toBeGreaterThan(opened));
  return ch;
}

function sendButton() {
  return screen.getByRole<HTMLButtonElement>("button", { name: "보내기" });
}

beforeEach(() => {
  streamRunEvents.mockReset();
  createClient.mockClear();
  startRun.mockReset();
});
afterEach(cleanup);

describe("Chat 정직한 한 줄 (DESIGN 9절)", () => {
  const ENABLED =
    "성공으로 끝난 실행의 답변만 Agent 의 Memory 로 남아 다음 실행의 컨텍스트에 들어갑니다. 이전 질문은 전달되지 않습니다.";
  const DISABLED = "각 실행은 독립입니다 — 이전 질문도 답변도 모델에 전달되지 않습니다.";

  it("MVP-2e: memory_enabled 가 참이면 답변만 이어진다고 말한다", () => {
    renderChat(true);

    const note = screen.getByTestId("continuity-note");
    expect(note.textContent).toBe(ENABLED);
    expect(note.textContent).not.toContain("독립");
  });

  it("MVP-2e: memory_enabled 가 거짓이면 아무것도 이어지지 않는다고 말한다", () => {
    renderChat(false);

    const note = screen.getByTestId("continuity-note");
    expect(note.textContent).toBe(DISABLED);
    expect(note.textContent).not.toContain("Memory");
  });

  it("리뷰: 답변이 이어지는 **조건**(성공으로 끝난 실행)을 빼놓지 않는다", () => {
    // `execute_run.py` 는 Run 이 `succeeded` 일 때만 답변을 Memory 에 남깁니다
    // (`if finished == RunStatus.SUCCEEDED and memory_agent_id is not None`). 조건을 빼고
    // "이전 답변은 Memory 로 남습니다" 라고만 쓰면 실패한 실행의 답변도 이어진다고 읽힙니다 -
    // 이 화면의 존재 이유가 "이어지는 것처럼 보이지만 아닌 것" 을 바로 말하는 것이므로
    // 그 절반이 틀리면 안 됩니다(MVP-2e 리뷰 2026-10-18).
    renderChat(true);

    expect(screen.getByTestId("continuity-note").textContent).toContain("성공");
  });

  it("MVP-2e: 두 경우의 문장이 서로 다르다 (뭉개지 않는다)", () => {
    renderChat(true);
    const a = screen.getByTestId("continuity-note").textContent;
    cleanup();
    renderChat(false);
    const b = screen.getByTestId("continuity-note").textContent;
    expect(a).not.toBe(b);
  });

  it("MVP-2e: 안내는 대화가 쌓인 뒤에도 남아 있다", async () => {
    renderChat(false);
    await sendAndOpen();
    expect(screen.getByTestId("continuity-note").textContent).toBe(DISABLED);
  });
});

describe("Chat 실행 시작과 스트림", () => {
  it("D-18: 서버 액션에 agentId 와 입력을 넘긴다", async () => {
    renderChat();
    await sendAndOpen("요금 알려줘");

    expect(startRun).toHaveBeenCalledWith(AGENT_ID, "요금 알려줘");
  });

  it("D-15·D-18: 스트림은 중계 경로로, 키 없이 연다", async () => {
    renderChat();
    await sendAndOpen();

    expect(createClient).toHaveBeenCalledWith({ baseUrl: "/api/aether" });
    for (const call of createClient.mock.calls) expect(call[0]).not.toHaveProperty("apiKey");
    expect(streamRunEvents.mock.calls[0]?.[0]).toBe(RUN_ID);
  });

  it("D-17: model.delta 는 도착하는 대로 이어 붙는다 (둘째 조각 전에 첫 조각이 있다)", async () => {
    renderChat();
    const ch = await sendAndOpen();

    await ch.push(event(RUN_ID, 1, "model.delta", { text: "안녕" }));
    expect(screen.getByTestId("answer").textContent).toBe("안녕");

    await ch.push(event(RUN_ID, 2, "model.delta", { text: "하세요" }));
    expect(screen.getByTestId("answer").textContent).toBe("안녕하세요");
  });

  it("같은 seq 의 조각이 다시 오면 두 번 붙이지 않는다", async () => {
    renderChat();
    const ch = await sendAndOpen();

    await ch.push(event(RUN_ID, 1, "model.delta", { text: "가" }));
    await ch.push(event(RUN_ID, 1, "model.delta", { text: "가" }));
    await ch.push(event(RUN_ID, 2, "model.delta", { text: "나" }));

    expect(screen.getByTestId("answer").textContent).toBe("가나");
  });

  it("DESIGN 6: 보낸 입력과 답변은 항상 텍스트다 (HTML 로 해석되지 않는다)", async () => {
    renderChat();
    const ch = await sendAndOpen("<b>q</b>");
    await ch.push(event(RUN_ID, 1, "model.delta", { text: '<img src=x onerror="alert(1)">' }));

    expect(document.querySelector("img")).toBeNull();
    expect(document.querySelector("b")).toBeNull();
    expect(screen.getByTestId("answer").textContent).toBe('<img src=x onerror="alert(1)">');
  });

  it("상태는 run.status 로 갱신되고 RunStatusBadge 로 보인다", async () => {
    renderChat();
    const ch = await sendAndOpen();

    await ch.push(event(RUN_ID, 1, "run.status", { status: "running" }));
    expect(screen.getByText("running")).toBeTruthy();

    await ch.push(event(RUN_ID, 2, "run.finished", { status: "succeeded" }));
    expect(screen.getByText("succeeded")).toBeTruthy();
    expect(screen.queryByText("running")).toBeNull();
  });

  it("failed 면 run.status 의 failure_reason 을 보인다", async () => {
    renderChat();
    const ch = await sendAndOpen();

    await ch.push(event(RUN_ID, 1, "run.status", { status: "failed", failure_reason: "tool_error" }));
    await ch.push(event(RUN_ID, 2, "run.finished", { status: "failed" }));
    await ch.end();

    expect(screen.getByText("failed")).toBeTruthy();
    expect(screen.getByTestId("failure-reason").textContent).toContain("tool_error");
  });

  it("tool.called 는 이름만 보이고 인자·tool.result 본문은 여기 없다", async () => {
    renderChat();
    const ch = await sendAndOpen();

    await ch.push(
      event(RUN_ID, 1, "tool.called", { name: "search_docs", arguments: { q: "ARG-SECRET-VALUE" } }),
    );
    await ch.push(event(RUN_ID, 2, "tool.result", { content: "RESULT-BODY-TEXT" }));

    expect(screen.getByTestId("tool-line").textContent).toContain("search_docs");
    expect(document.body.textContent).not.toContain("ARG-SECRET-VALUE");
    expect(document.body.textContent).not.toContain("RESULT-BODY-TEXT");
  });

  it("각 항목에 타임라인 보기 링크(/runs/{runId})가 있다", async () => {
    renderChat();
    await sendAndOpen();

    expect(screen.getByRole("link", { name: "타임라인 보기" }).getAttribute("href")).toBe(
      `/runs/${RUN_ID}`,
    );
  });

  it("run.finished 뒤의 정상 종료는 끊김이 아니다", async () => {
    renderChat();
    const ch = await sendAndOpen();
    await ch.push(event(RUN_ID, 1, "run.finished", { status: "succeeded" }));

    await ch.end();

    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("Chat 끊김 (조용히 멈추지 않는다)", () => {
  it("MVP-2e: run.finished 없이 스트림이 닫히면 끊김이 보인다", async () => {
    renderChat();
    const ch = await sendAndOpen();
    await ch.push(event(RUN_ID, 1, "model.delta", { text: "부분" }));

    await ch.end();

    expect((await screen.findByRole("alert")).textContent).toContain("연결이 끊겼습니다");
    // 끊기기 전에 받은 답변은 남는다.
    expect(screen.getByTestId("answer").textContent).toBe("부분");
  });

  it("MVP-2e: 스트림이 오류로 끊기면 끊김이 보이고 기술 정보는 접혀 있다", async () => {
    renderChat();
    const ch = await sendAndOpen();

    await ch.fail(new TypeError("network error"));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("연결이 끊겼습니다");
    const details = alert.querySelector("details");
    expect(details?.textContent).toContain("network error");
    expect(details?.open).toBe(false);
  });

  it("HTTP 오류로 열리지 못해도 끊김으로 보인다", async () => {
    renderChat();
    streamRunEvents.mockImplementationOnce(() => ({
      [Symbol.asyncIterator]: () => ({
        next: () => Promise.reject(new AetherHttpError("failed with status 502", 502, "Bad Gateway")),
      }),
    }));
    startRun.mockResolvedValueOnce({ ok: true, runId: RUN_ID });
    await send("안녕");

    expect((await screen.findByRole("alert")).textContent).toContain("연결이 끊겼습니다");
  });

  it("재연결 로직이 없다: 끊긴 뒤 스트림을 다시 열지 않는다", async () => {
    renderChat();
    const ch = await sendAndOpen();
    await ch.fail(new TypeError("network error"));
    await screen.findByRole("alert");

    expect(streamRunEvents).toHaveBeenCalledTimes(1);
  });
});

describe("Chat 보내기", () => {
  it("보내는 동안 버튼이 비활성이고, 끝나면 다시 켜진다", async () => {
    renderChat();
    let resolve!: (value: unknown) => void;
    startRun.mockReturnValueOnce(new Promise((r) => (resolve = r)));
    await send("안녕");

    expect(sendButton().disabled).toBe(true);

    streamRunEvents.mockReturnValueOnce(channel().iterable);
    await act(async () => {
      resolve({ ok: true, runId: RUN_ID });
      await Promise.resolve();
    });
    // 입력은 비워졌으므로 다음 입력을 쓰면 다시 켜진다 (전송 중 상태가 풀렸다는 뜻).
    await waitFor(() => expect(streamRunEvents).toHaveBeenCalled());
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "다음" } });
    expect(sendButton().disabled).toBe(false);
  });

  it("빈 입력은 서버 액션을 부르지 않는다 (버튼이 비활성)", () => {
    renderChat();
    expect(sendButton().disabled).toBe(true);
    expect(startRun).not.toHaveBeenCalled();
  });

  it("서버 액션이 실패하면 message 를 오류로 보이고 스트림을 열지 않는다", async () => {
    renderChat();
    startRun.mockResolvedValueOnce({
      ok: false,
      message: "api 가 web 의 키를 거부했습니다. 키를 다시 발급해 주입하세요.",
    });
    await send("안녕");

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("api 가 web 의 키를 거부했습니다. 키를 다시 발급해 주입하세요.");
    expect(streamRunEvents).not.toHaveBeenCalled();
    // 실패한 입력은 textarea 에 남아 다시 보낼 수 있다.
    expect(screen.getByRole<HTMLTextAreaElement>("textbox").value).toBe("안녕");
  });

  it("서버 액션이 던져도(전송 오류) 화면이 깨지지 않고 오류로 보인다", async () => {
    renderChat();
    startRun.mockRejectedValueOnce(new Error("Failed to fetch"));
    await send("안녕");

    expect((await screen.findByRole("alert")).textContent).toContain("다시 시도");
  });

  it("보낸 뒤 textarea 는 비워진다", async () => {
    renderChat();
    await sendAndOpen();
    expect(screen.getByRole<HTMLTextAreaElement>("textbox").value).toBe("");
  });

  it("다시 보내면 앞 스트림을 중단하고 새 항목을 만든다", async () => {
    renderChat();
    await sendAndOpen("하나", RUN_ID);
    await sendAndOpen("둘", RUN_ID_2);

    expect(streamRunEvents.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
    expect(streamRunEvents.mock.calls[1]?.[1]?.signal?.aborted).toBe(false);
    expect(screen.getAllByRole("link", { name: "타임라인 보기" })).toHaveLength(2);
  });

  it("unmount 하면 스트림을 중단한다", async () => {
    renderChat();
    await sendAndOpen();

    cleanup();

    expect(streamRunEvents.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
  });
});
