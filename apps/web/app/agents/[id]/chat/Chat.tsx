"use client";

import { createClient, type RunEvent } from "@aether/sdk";
import { CircleAlert } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { RunStatusBadge, type RunStatus } from "@/components/RunStatusBadge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";

import { startRun } from "./actions";

type Connection =
  | { state: "open" }
  | { state: "ended" }
  | { state: "stopped" }
  | { state: "broken"; detail: string };

interface Turn {
  key: number;
  runId: string;
  input: string;
  status: RunStatus;
  /** `model.delta` 조각. `seq` 로 중복을 거릅니다(재생). */
  parts: { seq: number; text: string }[];
  tools: { seq: number; name: string }[];
  failureReason: string | null;
  connection: Connection;
}

const RUN_STATUSES: readonly string[] = [
  "queued",
  "running",
  "waiting",
  "succeeded",
  "failed",
  "cancelled",
  "timed_out",
];

function isRunStatus(value: unknown): value is RunStatus {
  return typeof value === "string" && RUN_STATUSES.includes(value);
}

/**
 * 이 화면이 대화처럼 보이지만 대화가 아니라는 사실(DESIGN 9절). 두 문장은 실제 플래그
 * (`definition.memory_enabled`)로 갈립니다.
 *
 * - `POST /agents/{id}/run` 의 본문은 `{ input, agent_version? }` 이고 이력을 받는 자리가
 *   없습니다. 각 입력은 **독립 Run** 입니다 - 모델은 이전 **질문**을 보지 못합니다.
 * - 다만 `memory_enabled` 인 Agent 는 Run 이 `succeeded` 로 끝날 때 **답변 텍스트**가
 *   Memory 에 남고, 다음 Run 의 Context Compiler 가 Memory 를 포함합니다.
 */
const NOTE_MEMORY =
  "성공으로 끝난 실행의 답변만 Agent 의 Memory 로 남아 다음 실행의 컨텍스트에 들어갑니다. 이전 질문은 전달되지 않습니다.";
const NOTE_INDEPENDENT = "각 실행은 독립입니다 — 이전 질문도 답변도 모델에 전달되지 않습니다.";

function applyEvent(turn: Turn, event: RunEvent): Turn {
  const payload = event.payload;
  switch (event.type) {
    case "model.delta": {
      if (typeof payload.text !== "string") return turn;
      if (turn.parts.some((part) => part.seq === event.seq)) return turn;
      const parts = [...turn.parts, { seq: event.seq, text: payload.text }].sort(
        (a, b) => a.seq - b.seq,
      );
      return { ...turn, parts };
    }
    case "run.status": {
      const reason = typeof payload.failure_reason === "string" ? payload.failure_reason : null;
      return {
        ...turn,
        status: isRunStatus(payload.status) ? payload.status : turn.status,
        failureReason: reason ?? turn.failureReason,
      };
    }
    case "run.finished":
      return { ...turn, status: isRunStatus(payload.status) ? payload.status : turn.status };
    case "tool.called": {
      if (turn.tools.some((tool) => tool.seq === event.seq)) return turn;
      const name = typeof payload.name === "string" ? payload.name : "(이름 없음)";
      return { ...turn, tools: [...turn.tools, { seq: event.seq, name }] };
    }
    default:
      return turn;
  }
}

/**
 * Agent 대화 화면(MVP-2e). 쓰기(`startRun`)는 서버 액션이고 스트림은 중계 경로 위에서
 * **키 없이** 읽습니다(D-15·D-18) - 브라우저는 중계로 쓰기를 하지 않습니다.
 *
 * 재연결 로직은 없습니다(`RunTabs` 와 같은 결정): 끊기면 그 사실을 보이고, 이어서 보는 길은
 * "타임라인 보기" 링크입니다.
 */
export function Chat({
  agentId,
  agentName,
  memoryEnabled,
}: {
  agentId: string;
  agentName: string;
  memoryEnabled: boolean;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<{ message: string; detail?: string } | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const nextKey = useRef(1);

  useEffect(() => () => controllerRef.current?.abort(), []);

  function update(key: number, change: (turn: Turn) => Turn) {
    setTurns((current) => current.map((turn) => (turn.key === key ? change(turn) : turn)));
  }

  async function follow(key: number, runId: string, signal: AbortSignal) {
    let finished = false;
    try {
      const client = createClient({ baseUrl: "/api/aether" });
      for await (const event of client.streamRunEvents(runId, { signal })) {
        if (event.type === "run.finished") finished = true;
        update(key, (turn) => applyEvent(turn, event));
      }
      if (signal.aborted) return;
      update(key, (turn) => ({
        ...turn,
        connection: finished
          ? { state: "ended" }
          : { state: "broken", detail: "run.finished 를 받기 전에 스트림이 닫혔습니다." },
      }));
    } catch (error) {
      if (signal.aborted) return;
      update(key, (turn) => ({
        ...turn,
        connection: {
          state: "broken",
          detail: error instanceof Error ? error.message : String(error),
        },
      }));
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const text = input;
    if (sending || text.trim() === "") return;
    setSending(true);
    setSendError(null);

    let result;
    try {
      result = await startRun(agentId, text);
    } catch (error) {
      setSendError({
        message: "전송에 실패했습니다. 잠시 후 다시 시도하세요.",
        detail: error instanceof Error ? error.message : String(error),
      });
      setSending(false);
      return;
    }
    setSending(false);
    if (!result.ok) {
      setSendError({ message: result.message });
      return;
    }

    // 앞 스트림을 닫고(재전송), 열려 있던 항목에는 닫았다는 사실을 남깁니다.
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const key = nextKey.current++;
    setInput("");
    setTurns((current) => [
      ...current.map(
        (turn): Turn =>
          turn.connection.state === "open" ? { ...turn, connection: { state: "stopped" } } : turn,
      ),
      {
        key,
        runId: result.runId,
        input: text,
        status: "queued",
        parts: [],
        tools: [],
        failureReason: null,
        connection: { state: "open" },
      },
    ]);
    void follow(key, result.runId, controller.signal);
  }

  return (
    <div className="flex flex-col gap-4">
      <p data-testid="continuity-note" className="text-xs text-muted-foreground">
        {memoryEnabled ? NOTE_MEMORY : NOTE_INDEPENDENT}
      </p>

      <ScrollArea className="h-[60vh] rounded-md border" aria-label={`${agentName} 와의 대화`}>
        <div className="flex flex-col gap-4 p-4">
          {turns.length === 0 ? (
            <p className="py-12 text-center text-sm text-muted-foreground">
              아직 보낸 입력이 없습니다.
            </p>
          ) : null}
          {turns.map((turn) => (
            <TurnView key={turn.key} turn={turn} />
          ))}
        </div>
      </ScrollArea>

      {sendError ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>실행을 시작하지 못했습니다</AlertTitle>
          <AlertDescription>
            <p>{sendError.message}</p>
            {sendError.detail ? (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs">기술 정보</summary>
                <pre className="mt-1 whitespace-pre-wrap font-mono text-xs">{sendError.detail}</pre>
              </details>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}

      <form onSubmit={(event) => void onSubmit(event)} className="flex flex-col gap-2">
        <Textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Agent 에게 보낼 내용"
          aria-label="입력"
        />
        <div className="flex justify-end">
          <Button type="submit" disabled={sending || input.trim() === ""}>
            보내기
          </Button>
        </div>
      </form>
    </div>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  const answer = turn.parts.map((part) => part.text).join("");
  return (
    <div className="flex flex-col gap-2 rounded-md border p-3">
      {/* 입력·답변·도구 이름은 외부에서 온 텍스트입니다 - 항상 텍스트로(DESIGN 6절). */}
      <p data-testid="input" className="whitespace-pre-wrap text-sm font-medium">
        {turn.input}
      </p>
      {answer !== "" ? (
        <p data-testid="answer" className="whitespace-pre-wrap text-sm">
          {answer}
        </p>
      ) : null}
      {turn.tools.map((tool) => (
        <p key={tool.seq} data-testid="tool-line" className="text-xs text-muted-foreground">
          도구 호출: {tool.name}
        </p>
      ))}
      <div className="flex items-center gap-3">
        <RunStatusBadge status={turn.status} />
        {turn.failureReason ? (
          <span data-testid="failure-reason" className="font-mono text-xs">
            실패 사유: {turn.failureReason}
          </span>
        ) : null}
        <Link
          href={`/runs/${turn.runId}`}
          className="ml-auto text-xs underline-offset-4 hover:underline"
        >
          타임라인 보기
        </Link>
      </div>
      {turn.connection.state === "stopped" ? (
        <p className="text-xs text-muted-foreground">
          다른 입력을 보내 이 실행의 스트림을 닫았습니다. 이어서 보려면 타임라인 보기를 누르세요.
        </p>
      ) : null}
      {turn.connection.state === "broken" ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>연결이 끊겼습니다</AlertTitle>
          <AlertDescription>
            <p>답변이 끝났는지 알 수 없습니다. 타임라인 보기에서 실행 상태를 확인하세요.</p>
            <details className="mt-2">
              <summary className="cursor-pointer text-xs">기술 정보</summary>
              <pre className="mt-1 whitespace-pre-wrap font-mono text-xs">
                {turn.connection.detail}
              </pre>
            </details>
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
