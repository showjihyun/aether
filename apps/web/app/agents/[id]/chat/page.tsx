import { createClient } from "@aether/sdk";

import { DetailError } from "@/components/DetailError";
import { MissingApiKey } from "@/components/ListStates";
import { Badge } from "@/components/ui/badge";

import { Chat } from "./Chat";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(홈 화면과 같은 이유).
export const dynamic = "force-dynamic";

export default async function AgentChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // 키가 없으면 호출하지 않고 그 사실을 말합니다 — 중계의 503 과 같은 말입니다(MVP-2p 리뷰).
  const apiKey = process.env.AETHER_API_KEY?.trim();
  if (!apiKey) return <MissingApiKey />;

  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
    // 서버에서 서버로 가는 호출이라 중계를 거치지 않고 키를 직접 넘깁니다(D-15).
    // `GET /agents/{id}` 는 중계 허용 목록에 없습니다. 키는 브라우저로 가지 않습니다.
    apiKey: process.env.AETHER_API_KEY,
  });

  let agent;
  try {
    agent = await client.getAgent(id);
  } catch (error) {
    return (
      <DetailError
        error={error}
        notFoundTitle="Agent 를 찾을 수 없습니다"
        notFoundAction="Agent 목록에서 다시 골라 주세요."
        errorTitle="Agent 를 불러오지 못했습니다"
        backLabel="Agent 목록으로"
        backHref="/agents"
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">{agent.name}</h2>
        <Badge variant="outline">{`v${agent.current_version}`}</Badge>
      </div>
      {/* 클라이언트에는 화면에 필요한 세 값만 넘깁니다. 키는 넘기지 않습니다. */}
      <Chat
        agentId={agent.id}
        agentName={agent.name}
        memoryEnabled={agent.definition.memory_enabled === true}
      />
    </div>
  );
}
