import { createClient } from "@aether/sdk";
import Link from "next/link";

import { isBrokenCursor, ListEmpty, ListError, LoadMore, MissingApiKey } from "@/components/ListStates";
import { RelativeTime } from "@/components/RelativeTime";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(홈 화면과 같은 이유).
export const dynamic = "force-dynamic";

// 청크 수·적재 상태는 이 목록에 없습니다. API 에 청크 수가 없고, 적재 API 는 세트별 경로라
// 여기서 끌어오면 N+1 입니다(`/runs` 가 Agent 이름을 뺀 것과 같은 이유). 적재는 하위 경로입니다.
export default async function KnowledgePage({
  searchParams,
}: {
  searchParams: Promise<{ cursor?: string }>;
}) {
  const { cursor } = await searchParams;
  const apiKey = process.env.AETHER_API_KEY?.trim();
  if (!apiKey) return <MissingApiKey />;

  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
    // 서버에서 서버로 가는 호출이라 중계를 거치지 않고 키를 직접 넘깁니다(D-15). 키는 브라우저로 가지 않습니다.
    apiKey: process.env.AETHER_API_KEY,
  });

  let page;
  try {
    page = await client.listKnowledgeSets({ cursor });
  } catch (error) {
    return (
      <ListError
        message={error instanceof Error ? error.message : String(error)}
        restartHref="/knowledge"
        brokenCursor={isBrokenCursor(error)}
      />
    );
  }

  if (page.items.length === 0) {
    return cursor ? (
      <ListEmpty message="이 쪽에는 더 이상 보여줄 것이 없습니다." restartHref="/knowledge" />
    ) : (
      <ListEmpty message="아직 Knowledge 세트가 없습니다." />
    );
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>이름</TableHead>
            <TableHead>생성</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {page.items.map((set) => (
            <TableRow key={set.id}>
              <TableCell>
                <Link href={`/knowledge/${set.id}`} className="underline-offset-4 hover:underline">
                  {set.name}
                </Link>
              </TableCell>
              <TableCell>
                <RelativeTime iso={set.created_at} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <LoadMore basePath="/knowledge" nextCursor={page.next_cursor} />
    </>
  );
}
