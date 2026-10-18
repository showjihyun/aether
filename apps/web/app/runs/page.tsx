import { createClient } from "@aether/sdk";
import Link from "next/link";

import { CopyableId } from "@/components/CopyableId";
import { isBrokenCursor, ListEmpty, ListError, LoadMore, MissingApiKey } from "@/components/ListStates";
import { RelativeTime } from "@/components/RelativeTime";
import { RunStatusBadge } from "@/components/RunStatusBadge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDuration } from "@/lib/format";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(홈 화면과 같은 이유).
export const dynamic = "force-dynamic";

// 행 → 상세는 상태 칸의 링크입니다(MVP-2b). `CopyableId` 가 버튼이라 행 전체를 `<a>` 로 감쌀 수 없습니다.
export default async function RunsPage({
  searchParams,
}: {
  searchParams: Promise<{ cursor?: string }>;
}) {
  const { cursor } = await searchParams;
  // 키가 없으면 호출하지 않고 그 사실을 말합니다 — 중계의 503 과 같은 말입니다(MVP-2p 리뷰).
  const apiKey = process.env.AETHER_API_KEY?.trim();
  if (!apiKey) return <MissingApiKey />;

  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
    // 서버에서 서버로 가는 호출이라 중계를 거치지 않고 키를 직접 넘깁니다(D-15). 키는 브라우저로 가지 않습니다.
    apiKey: process.env.AETHER_API_KEY,
  });

  let page;
  try {
    page = await client.listRuns({ cursor });
  } catch (error) {
    return (
      <ListError
        message={error instanceof Error ? error.message : String(error)}
        restartHref="/runs"
        brokenCursor={isBrokenCursor(error)}
      />
    );
  }

  if (page.items.length === 0) {
    // 첫 쪽이 비면 안내 한 줄. **커서 쪽**이 비면 막다른 길이므로 돌아갈 길을 줍니다
    // (낡은 커서로 들어온 주소. MVP-2a 리뷰 2026-10-18).
    return cursor ? (
      <ListEmpty message="이 쪽에는 더 이상 보여줄 것이 없습니다." restartHref="/runs" />
    ) : (
      <ListEmpty message="아직 Run 이 없습니다." />
    );
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>상태</TableHead>
            <TableHead>Agent</TableHead>
            <TableHead>시작</TableHead>
            <TableHead>소요</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {page.items.map((run) => (
            <TableRow key={run.run_id}>
              <TableCell>
                <Link href={`/runs/${run.run_id}`} className="inline-flex">
                  <RunStatusBadge status={run.status} />
                </Link>
              </TableCell>
              <TableCell>
                <CopyableId id={run.agent_id} />
              </TableCell>
              <TableCell>
                <RelativeTime iso={run.started_at} />
              </TableCell>
              <TableCell>{formatDuration(run.started_at, run.finished_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <LoadMore basePath="/runs" nextCursor={page.next_cursor} />
    </>
  );
}
