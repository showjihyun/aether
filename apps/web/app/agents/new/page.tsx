import { AgentForm } from "../AgentForm";

// 이 화면은 api 를 부르지 않습니다 - 저장은 서버 액션이 하고(키가 없으면 그 액션이 말합니다),
// 만들 때는 읽을 정의가 없습니다.
export default function NewAgentPage() {
  return <AgentForm mode="create" />;
}
