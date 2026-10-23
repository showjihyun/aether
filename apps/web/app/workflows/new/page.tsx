import { WorkflowEditor } from "./WorkflowEditor";

// 이 화면은 api 를 부르지 않습니다 - 저장은 서버 액션이 하고(키가 없으면 그 액션이 말합니다),
// 만들 때는 읽을 그래프가 없습니다. 기존 Workflow 를 고치는 화면은 이 단위에 없습니다(plan 0007 개정 4).
export default function NewWorkflowPage() {
  return <WorkflowEditor />;
}
