import { createClient } from "@aether/sdk";
import Link from "next/link";

import { CopyableId } from "@/components/CopyableId";
import { isBrokenCursor, ListEmpty, ListError, LoadMore, MissingApiKey } from "@/components/ListStates";
import { RelativeTime } from "@/components/RelativeTime";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { WorkflowRunStatusBadge } from "@/components/WorkflowRunStatusBadge";
import { EMPTY_CELL } from "@/lib/format";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(홈 화면과 같은 이유).
export const dynamic = "force-dynamic";

/** 표가 둘이라 커서도 둘입니다(`cursor` = 정의, `runsCursor` = 실행). 한 표의 링크는 상대편 커서를 지켜야 합니다. */
function hrefWith(query: { cursor?: string; runsCursor?: string }): string {
  const parts: string[] = [];
  if (query.cursor) parts.push(`cursor=${encodeURIComponent(query.cursor)}`);
  if (query.runsCursor) parts.push(`runsCursor=${encodeURIComponent(query.runsCursor)}`);
  return parts.length ? `/workflows?${parts.join("&")}` : "/workflows";
}

/** 기다림의 **대상**에 라벨을 붙입니다. 자식 Run id 와 노드 실행 id 는 둘 다 짧은 mono id 로
 * 그려져 라벨이 없으면 구별되지 않고(상태 badge 도 갈라주지 않습니다 — `waiting_approval` 이
 * 노드 실행 id 와 함께 옵니다), 보는 사람이 다음에 열 곳이 달라집니다(MVP-2c 리뷰 2026-10-18). */
function Waiting({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <span className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      {children}
    </span>
  );
}

const messageOf = (error: unknown) => (error instanceof Error ? error.message : String(error));

export default async function WorkflowsPage({
  searchParams,
}: {
  searchParams: Promise<{ cursor?: string; runsCursor?: string }>;
}) {
  const { cursor, runsCursor } = await searchParams;
  const apiKey = process.env.AETHER_API_KEY?.trim();
  if (!apiKey) return <MissingApiKey />;

  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
    // 서버에서 서버로 가는 호출이라 중계를 거치지 않고 키를 직접 넘깁니다(D-15). 키는 브라우저로 가지 않습니다.
    apiKey: process.env.AETHER_API_KEY,
  });

  // 한 표의 실패가 다른 표를 지우지 않도록 따로 받습니다.
  const [defsResult, runsResult] = await Promise.allSettled([
    client.listWorkflows({ cursor }),
    client.listWorkflowRuns({ cursor: runsCursor }),
  ]);

  const defsRestart = hrefWith({ runsCursor });
  const runsRestart = hrefWith({ cursor });

  return (
    <div className="flex flex-col gap-10">
      <section aria-labelledby="workflow-defs">
        <h2 id="workflow-defs" className="mb-3 text-sm font-semibold">
          정의
        </h2>
        {defsResult.status === "rejected" ? (
          <ListError
            message={messageOf(defsResult.reason)}
            restartHref={defsRestart}
            brokenCursor={isBrokenCursor(defsResult.reason)}
          />
        ) : defsResult.value.items.length === 0 ? (
          cursor ? (
            <ListEmpty message="이 쪽에는 더 이상 보여줄 것이 없습니다." restartHref={defsRestart} />
          ) : (
            <ListEmpty message="아직 Workflow 가 없습니다." />
          )
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>이름</TableHead>
                  <TableHead>현재 Version</TableHead>
                  <TableHead>수정</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {defsResult.value.items.map((workflow) => (
                  <TableRow key={workflow.id}>
                    <TableCell>
                      <Link
                        href={`/workflows/${workflow.id}`}
                        className="underline underline-offset-4"
                      >
                        {workflow.name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">v{workflow.current_version}</Badge>
                    </TableCell>
                    <TableCell>
                      <RelativeTime iso={workflow.updated_at} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <LoadMore
              basePath={hrefWith({ runsCursor })}
              nextCursor={defsResult.value.next_cursor}
            />
          </>
        )}
      </section>

      <section aria-labelledby="workflow-runs">
        <h2 id="workflow-runs" className="mb-3 text-sm font-semibold">
          실행
        </h2>
        {runsResult.status === "rejected" ? (
          <ListError
            message={messageOf(runsResult.reason)}
            restartHref={runsRestart}
            brokenCursor={isBrokenCursor(runsResult.reason)}
          />
        ) : runsResult.value.items.length === 0 ? (
          runsCursor ? (
            <ListEmpty message="이 쪽에는 더 이상 보여줄 것이 없습니다." restartHref={runsRestart} />
          ) : (
            <ListEmpty message="아직 Workflow 실행이 없습니다." />
          )
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>상태</TableHead>
                  <TableHead>현재 노드</TableHead>
                  <TableHead>기다리는 대상</TableHead>
                  <TableHead>요청</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runsResult.value.items.map((run) => {
                  const waiting = run.waiting_run_id || run.waiting_node_execution_id || run.wake_at;
                  return (
                    <TableRow key={run.workflow_run_id}>
                      <TableCell>
                        <span className="flex items-center gap-3">
                          <WorkflowRunStatusBadge status={run.status} />
                          <Link
                            href={`/workflows/runs/${run.workflow_run_id}`}
                            className="text-xs underline underline-offset-4"
                          >
                            노드 보기
                          </Link>
                        </span>
                      </TableCell>
                      <TableCell>{run.current_node_id ?? EMPTY_CELL}</TableCell>
                      <TableCell>
                        {waiting ? (
                          <div className="flex flex-col gap-1">
                            {run.waiting_run_id ? (
                              <Waiting label="자식 Run">
                                <CopyableId id={run.waiting_run_id} />
                              </Waiting>
                            ) : null}
                            {run.waiting_node_execution_id ? (
                              <Waiting label="노드 실행">
                                <CopyableId id={run.waiting_node_execution_id} />
                              </Waiting>
                            ) : null}
                            {run.wake_at ? (
                              <Waiting label="깨어남">
                                <RelativeTime iso={run.wake_at} />
                              </Waiting>
                            ) : null}
                          </div>
                        ) : (
                          EMPTY_CELL
                        )}
                      </TableCell>
                      <TableCell>
                        <RelativeTime iso={run.requested_at} />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
            <LoadMore
              basePath={hrefWith({ cursor })}
              param="runsCursor"
              nextCursor={runsResult.value.next_cursor}
            />
          </>
        )}
      </section>
    </div>
  );
}
