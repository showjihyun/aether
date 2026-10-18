"use client";

import { createClient, type AetherClient } from "@aether/sdk";
import { CircleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { RelativeTime } from "@/components/RelativeTime";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// SDK 는 이벤트 봉투 타입을 index 로 내보내지 않습니다(SDK 를 고치지 않습니다) - 반환 타입에서 꺼냅니다.
type RunEvent = ReturnType<AetherClient["streamRunEvents"]> extends AsyncIterable<infer E>
  ? E
  : never;

type Connection =
  | { state: "open" }
  | { state: "ended" }
  | { state: "broken"; detail: string };

/** `seq` 순서로 끼워 넣습니다. 같은 `seq` 가 다시 오면 무시합니다(재생·중복). */
function insertBySeq(events: RunEvent[], next: RunEvent): RunEvent[] {
  if (events.some((event) => event.seq === next.seq)) return events;
  return [...events, next].sort((a, b) => a.seq - b.seq);
}

/**
 * Run 상세의 탭: 이벤트 타임라인 / 트레이스.
 *
 * DESIGN 5절은 "입력" 탭도 적었지만 **만들지 않았습니다** — 입력 본문은 어떤 API 응답에도
 * 없습니다(`GET /runs/{id}` 는 `control.runs` 투영 열만 읽습니다, spec 0001 D-11). 내용이
 * "API 가 돌려주지 않습니다" 한 줄인 탭은 DESIGN 9절이 금지하는 자리표시입니다(그 절이
 * Workflow 노드에 대해 "'준비 중' 자리표시를 두지 않습니다" 라고 적은 것과 같은 것입니다).
 * 입력을 보여주려면 API 가 그 열을 돌려줘야 하고, 그것은 이 단위 밖입니다 —
 * DESIGN 5절을 그에 맞게 고쳤습니다(MVP-2b 리뷰 2026-10-18).
 *
 * 스트림은 이 컴포넌트가 소유합니다 - 탭을 옮겨도 `TabsContent` 만 갈리고 스트림과 받은
 * 이벤트는 그대로입니다. 재연결 로직은 **없습니다**(새 결정입니다): 끊기면 그 사실을 보이고,
 * 사람이 누르는 "다시 연결" 하나가 처음부터(`Last-Event-ID` 없이) 다시 엽니다.
 */
export function RunTabs({
  runId,
  apiBaseUrl,
  traceId,
}: {
  runId: string;
  /** **브라우저**가 닿을 수 있는 api 주소(서버 쪽 `AETHER_API_URL` 과 다를 수 있습니다). */
  apiBaseUrl: string;
  traceId: string | null;
}) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connection, setConnection] = useState<Connection>({ state: "open" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      let finished = false;
      try {
        const client = createClient({ baseUrl: apiBaseUrl });
        for await (const event of client.streamRunEvents(runId, { signal: controller.signal })) {
          if (event.type === "run.finished") finished = true;
          setEvents((current) => insertBySeq(current, event));
        }
        if (controller.signal.aborted) return;
        setConnection(
          finished
            ? { state: "ended" }
            : { state: "broken", detail: "run.finished 를 받기 전에 스트림이 닫혔습니다." },
        );
      } catch (error) {
        if (controller.signal.aborted) return;
        setConnection({
          state: "broken",
          detail: error instanceof Error ? error.message : String(error),
        });
      }
    })();
    return () => controller.abort();
  }, [runId, apiBaseUrl, attempt]);

  function reconnect() {
    setEvents([]);
    setConnection({ state: "open" });
    setAttempt((n) => n + 1);
  }

  return (
    <Tabs defaultValue="events">
      <TabsList>
        <TabsTrigger value="events">이벤트 타임라인</TabsTrigger>
        <TabsTrigger value="trace">트레이스</TabsTrigger>
      </TabsList>

      <TabsContent value="events" className="mt-4">
        <Timeline events={events} connection={connection} onReconnect={reconnect} />
      </TabsContent>

      <TabsContent value="trace" className="mt-4">
        {traceId ? (
          // 외부에서 온 값이므로 텍스트로, 코드는 pre + font-mono (DESIGN 6절).
          <pre className="whitespace-pre-wrap font-mono text-xs">{traceId}</pre>
        ) : (
          <p className="text-sm text-muted-foreground">아직 trace id 가 없습니다.</p>
        )}
      </TabsContent>
    </Tabs>
  );
}

function Timeline({
  events,
  connection,
  onReconnect,
}: {
  events: RunEvent[];
  connection: Connection;
  onReconnect: () => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      {events.length === 0 && connection.state === "open" ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-8" />
          <Skeleton className="h-8" />
        </div>
      ) : null}

      {events.length > 0 ? (
        <ol className="flex flex-col gap-2">
          {events.map((event) => (
            <li key={event.seq} className="rounded-md border p-3">
              <div className="flex items-center gap-3 text-sm">
                <span data-testid="event-seq" className="font-mono text-xs text-muted-foreground">
                  {event.seq}
                </span>
                <span data-testid="event-type" className="font-medium">
                  {event.type}
                </span>
                <span className="ml-auto text-xs text-muted-foreground">
                  <RelativeTime iso={event.at} />
                </span>
              </div>
              {Object.keys(event.payload).length > 0 ? (
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs text-muted-foreground">payload</summary>
                  {/* 도구 출력·인자는 외부에서 온 텍스트입니다 - 항상 텍스트로(DESIGN 6절). */}
                  <pre className="mt-1 whitespace-pre-wrap font-mono text-xs">
                    {JSON.stringify(event.payload, null, 2)}
                  </pre>
                </details>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}

      {connection.state === "ended" ? (
        <p role="status" className="text-sm text-muted-foreground">
          스트림이 끝났습니다.
        </p>
      ) : null}

      {connection.state === "broken" ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>연결이 끊겼습니다</AlertTitle>
          <AlertDescription>
            <p>다시 연결하면 이벤트를 처음부터 다시 받습니다.</p>
            <Button type="button" variant="outline" size="sm" className="mt-2" onClick={onReconnect}>
              다시 연결
            </Button>
            <details className="mt-2">
              <summary className="cursor-pointer text-xs">기술 정보</summary>
              <pre className="mt-1 whitespace-pre-wrap font-mono text-xs">{connection.detail}</pre>
            </details>
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
