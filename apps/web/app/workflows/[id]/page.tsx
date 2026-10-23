import { AetherHttpError, createClient } from "@aether/sdk";
import Link from "next/link";

import { DetailError } from "@/components/DetailError";
import { ListEmpty, MissingApiKey } from "@/components/ListStates";
import { Badge } from "@/components/ui/badge";

import { WorkflowCanvas } from "./WorkflowCanvas";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(홈 화면과 같은 이유).
export const dynamic = "force-dynamic";

// `lib/relay.ts`·서버 액션의 id 칸과 같은 꼴입니다. SDK 가 이 값으로 URL 경로를 만듭니다.
const ID_SHAPE = /^[A-Za-z0-9_-]{1,128}$/;

// 서버에서 서버로 부르므로 중계(`lib/relay.ts`)를 거치지 않습니다 - 브라우저가 부를 것이 없습니다.
// 그리는 것은 현재 Version 의 그래프이고 읽기뿐입니다(끌기·저장은 P5-6).
export default async function WorkflowPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const apiKey = process.env.AETHER_API_KEY?.trim();
  if (!apiKey) return <MissingApiKey />;

  const detail = (error: unknown) => (
    <DetailError
      error={error}
      notFoundTitle="Workflow 를 찾을 수 없습니다"
      notFoundAction="Workflow 목록에서 다시 골라 주세요."
      errorTitle="Workflow 를 불러오지 못했습니다"
      backLabel="Workflow 목록으로"
      backHref="/workflows"
    />
  );

  // 경로 조각이 든 id 로는 api 를 부르지 않습니다 - 없는 Workflow 와 같은 화면입니다.
  if (!ID_SHAPE.test(id)) return detail(new AetherHttpError("invalid workflow id", 404, "Not Found"));

  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
    // 서버에서 서버로 가는 호출이라 키를 직접 넘깁니다(D-15). 키는 브라우저로 가지 않습니다.
    apiKey: process.env.AETHER_API_KEY,
  });

  let workflow;
  try {
    workflow = await client.getWorkflow(id);
  } catch (error) {
    return detail(error);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold">{workflow.name}</h2>
          <Badge variant="outline">v{workflow.current_version}</Badge>
        </div>
        <Link href="/workflows" className="text-xs underline underline-offset-4">
          Workflow 목록으로
        </Link>
      </div>
      {workflow.nodes.length === 0 ? (
        <ListEmpty message="이 Workflow 에는 아직 노드가 없습니다." />
      ) : (
        <>
          {/* spec 0007 R-12: 배치는 저장되지 않습니다 (D-9). */}
          <p className="text-xs text-muted-foreground">
            배치는 자동이라 열 때마다 달라질 수 있습니다. 노드 위치는 저장되지 않습니다.
          </p>
          <WorkflowCanvas nodes={workflow.nodes} edges={workflow.edges} />
        </>
      )}
    </div>
  );
}
