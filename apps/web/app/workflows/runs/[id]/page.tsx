import { createClient } from "@aether/sdk";
import Link from "next/link";

import { DetailError } from "@/components/DetailError";
import { isBrokenCursor, ListEmpty, ListError, LoadMore, MissingApiKey } from "@/components/ListStates";
import { RelativeTime } from "@/components/RelativeTime";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { WorkflowRunStatusBadge } from "@/components/WorkflowRunStatusBadge";
import { EMPTY_CELL } from "@/lib/format";
import { cn } from "@/lib/utils";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(홈 화면과 같은 이유).
export const dynamic = "force-dynamic";

// 서버에서 서버로 부르므로 중계(`lib/relay.ts`)를 거치지 않습니다 — 목록·상세 화면과 같은 길입니다.
// 노드 출력은 응답에 없고(spec 0007 D-4) 화면에도 자리표시를 두지 않습니다(DESIGN 9절).
export default async function WorkflowRunPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ cursor?: string }>;
}) {
  const { id } = await params;
  const { cursor } = await searchParams;
  const apiKey = process.env.AETHER_API_KEY?.trim();
  if (!apiKey) return <MissingApiKey />;

  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
    apiKey: process.env.AETHER_API_KEY,
  });

  const here = `/workflows/runs/${encodeURIComponent(id)}`;

  let page;
  try {
    page = await client.listWorkflowRunNodes(id, { cursor });
  } catch (error) {
    if (isBrokenCursor(error)) {
      return <ListError message={String(error)} restartHref={here} brokenCursor />;
    }
    return (
      <DetailError
        error={error}
        notFoundTitle="Workflow 실행을 찾을 수 없습니다"
        notFoundAction="목록에서 다른 실행을 고르세요."
        errorTitle="노드 목록을 불러오지 못했습니다"
        backLabel="Workflow 목록으로"
        backHref="/workflows"
      />
    );
  }

  if (page.items.length === 0) {
    return (
      <ListEmpty
        message={cursor ? "이 쪽에는 더 이상 보여줄 것이 없습니다." : "아직 실행된 노드가 없습니다."}
        restartHref={cursor ? here : undefined}
      />
    );
  }

  const failed = page.items.filter((node) => node.status === "failed").length;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">노드 실행</h2>
        <Link href="/workflows" className="text-xs underline underline-offset-4">
          Workflow 목록으로
        </Link>
      </div>
      {failed > 0 ? (
        <p role="status" className="text-sm font-medium text-destructive">
          실패한 노드 {failed}개
        </p>
      ) : null}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>노드</TableHead>
            <TableHead>종류</TableHead>
            <TableHead>상태</TableHead>
            <TableHead>시작</TableHead>
            <TableHead>종료</TableHead>
            <TableHead>실패 사유</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {page.items.map((node) => {
            const isFailed = node.status === "failed";
            return (
              <TableRow
                key={node.node_id}
                data-failed={isFailed ? "true" : undefined}
                className={cn(isFailed && "bg-destructive/10")}
              >
                <TableCell className={cn(isFailed && "font-semibold")}>{node.node_id}</TableCell>
                <TableCell>
                  <Badge variant="outline">{node.kind}</Badge>
                </TableCell>
                <TableCell>
                  <WorkflowRunStatusBadge status={node.status} />
                </TableCell>
                <TableCell>
                  <RelativeTime iso={node.started_at} />
                </TableCell>
                <TableCell>
                  <RelativeTime iso={node.finished_at} />
                </TableCell>
                <TableCell>
                  {node.failure_reason ? (
                    <span className="font-mono text-xs">{node.failure_reason}</span>
                  ) : (
                    EMPTY_CELL
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      <LoadMore basePath={here} nextCursor={page.next_cursor} />
    </div>
  );
}
