import { createClient } from "@aether/sdk";
import Link from "next/link";

import { isBrokenCursor, ListEmpty, ListError, LoadMore, MissingApiKey } from "@/components/ListStates";
import { RelativeTime } from "@/components/RelativeTime";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(홈 화면과 같은 이유).
export const dynamic = "force-dynamic";

// 만들기 화면으로 가는 길(P5-4). 목록이 비어 있어도 있습니다 - 첫 Agent 를 만들 곳입니다.
function NewAgentLink() {
  return (
    <div className="mb-4 flex justify-end">
      <Link href="/agents/new" className={cn(buttonVariants({ size: "sm" }))}>
        새 Agent
      </Link>
    </div>
  );
}

// 이름 칸이 대화(`/agents/{id}/chat`, MVP-2e)로 가는 링크입니다 - 목적지가 생겨서 겁니다(DESIGN 9절).
export default async function AgentsPage({
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
      <>
        <NewAgentLink />
        <ListEmpty message="아직 Agent 가 없습니다." />
      </>
    );
  }

  return (
    <>
      <NewAgentLink />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>이름</TableHead>
            <TableHead>현재 Version</TableHead>
            <TableHead>수정</TableHead>
            <TableHead>편집</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {page.items.map((agent) => (
            <TableRow key={agent.id}>
              <TableCell>
                <Link href={`/agents/${agent.id}/chat`} className="underline-offset-4 hover:underline">
                  {agent.name}
                </Link>
              </TableCell>
              <TableCell>
                <Badge variant="outline">{`v${agent.current_version}`}</Badge>
              </TableCell>
              <TableCell>
                <RelativeTime iso={agent.updated_at} />
              </TableCell>
              <TableCell>
                <Link
                  href={`/agents/${agent.id}/edit`}
                  aria-label={`${agent.name} 편집`}
                  className="underline-offset-4 hover:underline"
                >
                  편집
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <LoadMore basePath="/agents" nextCursor={page.next_cursor} />
    </>
  );
}
