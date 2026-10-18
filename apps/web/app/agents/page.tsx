import { createClient } from "@aether/sdk";

import { isBrokenCursor, ListEmpty, ListError, LoadMore } from "@/components/ListStates";
import { RelativeTime } from "@/components/RelativeTime";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(홈 화면과 같은 이유).
export const dynamic = "force-dynamic";

// 행 클릭(→ 대화)은 MVP-2c 가 목적지를 만들 때 겁니다. 그 전에는 링크를 심지 않습니다(DESIGN 9절).
export default async function AgentsPage({
  searchParams,
}: {
  searchParams: Promise<{ cursor?: string }>;
}) {
  const { cursor } = await searchParams;
  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
  });

  let page;
  try {
    page = await client.listAgents({ cursor });
  } catch (error) {
    return (
      <ListError
        message={error instanceof Error ? error.message : String(error)}
        restartHref="/agents"
        brokenCursor={isBrokenCursor(error)}
      />
    );
  }

  if (page.items.length === 0) {
    // 첫 쪽이 비면 안내 한 줄. **커서 쪽**이 비면 막다른 길이므로 돌아갈 길을 줍니다
    // (낡은 커서로 들어온 주소. MVP-2a 리뷰 2026-10-18).
    return cursor ? (
      <ListEmpty message="이 쪽에는 더 이상 보여줄 것이 없습니다." restartHref="/agents" />
    ) : (
      <ListEmpty message="아직 Agent 가 없습니다." />
    );
  }

  return (
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
          {page.items.map((agent) => (
            <TableRow key={agent.id}>
              <TableCell>{agent.name}</TableCell>
              <TableCell>
                <Badge variant="outline">{`v${agent.current_version}`}</Badge>
              </TableCell>
              <TableCell>
                <RelativeTime iso={agent.updated_at} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <LoadMore basePath="/agents" nextCursor={page.next_cursor} />
    </>
  );
}
