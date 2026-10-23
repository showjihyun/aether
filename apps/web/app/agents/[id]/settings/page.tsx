import { AetherHttpError, createClient } from "@aether/sdk";

import { DetailError } from "@/components/DetailError";
import { MissingApiKey } from "@/components/ListStates";

import { SettingsForm } from "../../SettingsForm";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(홈 화면과 같은 이유).
export const dynamic = "force-dynamic";

// `lib/relay.ts`·서버 액션의 id 칸과 같은 꼴입니다. SDK 가 이 값으로 URL 경로를 만듭니다.
const ID_SHAPE = /^[A-Za-z0-9_-]{1,128}$/;

export default async function AgentSettingsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const apiKey = process.env.AETHER_API_KEY?.trim();
  if (!apiKey) return <MissingApiKey />;

  const detail = (error: unknown) => (
    <DetailError
      error={error}
      notFoundTitle="Agent 를 찾을 수 없습니다"
      notFoundAction="Agent 목록에서 다시 골라 주세요."
      errorTitle="Agent 를 불러오지 못했습니다"
      backLabel="Agent 목록으로"
      backHref="/agents"
    />
  );

  // 경로 조각이 든 id 로는 api 를 부르지 않습니다 - 없는 Agent 와 같은 화면입니다.
  if (!ID_SHAPE.test(id)) return detail(new AetherHttpError("invalid agent id", 404, "Not Found"));

  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
    // 서버에서 서버로 가는 호출이라 중계를 거치지 않고 키를 직접 넘깁니다(D-15). 키는 브라우저로 가지 않습니다.
    apiKey: process.env.AETHER_API_KEY,
  });

  let agent;
  try {
    agent = await client.getAgent(id);
  } catch (error) {
    return detail(error);
  }

  // 클라이언트에는 패널이 아는 칸만 넘깁니다. 나머지(system_prompt·policy 블록)는 저장 때 액션이
  // 다시 읽어 보존합니다 - 브라우저가 들고 있지 않습니다. 오래된 정의는 선택 칸이 없을 수 있습니다.
  const definition = agent.definition;
  return (
    <SettingsForm
      agentId={agent.id}
      name={agent.name}
      version={agent.current_version}
      modelId={definition.model?.id ?? ""}
      tools={definition.tools ?? []}
      mcpServers={definition.mcp_servers ?? []}
      contextBudgetTokens={definition.context_budget_tokens ?? null}
      knowledge={definition.knowledge ?? []}
      knowledgeTopK={definition.knowledge_top_k ?? null}
      memoryEnabled={definition.memory_enabled ?? false}
    />
  );
}
