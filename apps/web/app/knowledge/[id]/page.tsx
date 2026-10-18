import { createClient } from "@aether/sdk";
import Link from "next/link";

import { DetailError } from "@/components/DetailError";
import { IngestionStatusBadge } from "@/components/IngestionStatusBadge";
import {
  isBrokenCursor,
  isNotFound,
  ListEmpty,
  ListError,
  LoadMore,
  MissingApiKey,
} from "@/components/ListStates";
import { RelativeTime } from "@/components/RelativeTime";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDuration } from "@/lib/format";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(홈 화면과 같은 이유).
export const dynamic = "force-dynamic";

// 세트 이름은 보이지 않습니다 — 세트 상세 API 가 없습니다. 대신 목록으로 돌아가는 링크를 둡니다.
// 청크 수도 없습니다(`IngestionSummary` 에 없는 값을 추정하지 않습니다).
export default async function IngestionsPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ cursor?: string }>;
}) {
  const { id } = await params;
  const { cursor } = await searchParams;
  const here = `/knowledge/${id}`;
  const back = (
    <Link
      href="/knowledge"
      className="mb-4 inline-block text-sm text-muted-foreground underline-offset-4 hover:underline"
    >
      ← Knowledge
    </Link>
  );

  const apiKey = process.env.AETHER_API_KEY?.trim();
  if (!apiKey) return <MissingApiKey />;

  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
    // 서버에서 서버로 가는 호출이라 중계를 거치지 않고 키를 직접 넘깁니다(D-15). 키는 브라우저로 가지 않습니다.
    apiKey: process.env.AETHER_API_KEY,
  });

  let page;
  try {
    page = await client.listIngestions(id, { cursor });
  } catch (error) {
    // 404 는 "이 세트가 없다" 이고 다음 행동이 다릅니다(목록으로). 상태 코드 **필드**로
    // 가릅니다 — `/runs/{id}` 와 같은 분기입니다(MVP-2c 리뷰 2026-10-18).
    if (isNotFound(error)) {
      return (
        <>
          {back}
          <DetailError
            error={error}
            notFoundTitle="Knowledge 세트를 찾을 수 없습니다"
            notFoundAction="목록에서 다른 세트를 고르세요."
            errorTitle="적재를 불러오지 못했습니다"
            backLabel="Knowledge 목록으로"
            backHref="/knowledge"
          />
        </>
      );
    }
    return (
      <>
        {back}
        <ListError
          message={error instanceof Error ? error.message : String(error)}
          restartHref={here}
          brokenCursor={isBrokenCursor(error)}
        />
      </>
    );
  }

  if (page.items.length === 0) {
    return (
      <>
        {back}
        {cursor ? (
          <ListEmpty message="이 쪽에는 더 이상 보여줄 것이 없습니다." restartHref={here} />
        ) : (
          <ListEmpty message="아직 적재가 없습니다." />
        )}
      </>
    );
  }

  return (
    <>
      {back}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>source</TableHead>
            <TableHead>상태</TableHead>
            <TableHead>요청</TableHead>
            <TableHead>소요</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {page.items.map((ingestion) => (
            <TableRow key={ingestion.ingestion_id}>
              <TableCell className="max-w-md whitespace-normal break-all">
                {/* 외부에서 온 텍스트입니다(DESIGN 6절). 항상 텍스트로 그립니다. */}
                {ingestion.source}
                {ingestion.failure_reason ? (
                  <p className="mt-1 font-mono text-xs text-muted-foreground">{ingestion.failure_reason}</p>
                ) : null}
              </TableCell>
              <TableCell>
                <IngestionStatusBadge status={ingestion.status} />
              </TableCell>
              <TableCell>
                <RelativeTime iso={ingestion.requested_at} />
              </TableCell>
              <TableCell>{formatDuration(ingestion.started_at, ingestion.finished_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <LoadMore basePath={here} nextCursor={page.next_cursor} />
    </>
  );
}
