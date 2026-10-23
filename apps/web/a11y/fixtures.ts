import type { RouteTable } from "./targets";

const ID = "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b";
const RUN_ID = "0198aaaa-0000-7000-8000-000000000001";
const T0 = "2026-10-18T09:00:00Z";
const T1 = "2026-10-18T09:00:05Z";
const T2 = "2026-10-18T09:00:09Z";

const AGENT = { id: ID, name: "triage-agent", current_version: 2, created_at: T0, updated_at: T1 };
const AGENT_DETAIL = {
  ...AGENT,
  definition: { system_prompt: "You triage tickets.", memory_enabled: true },
  versions: [
    { version: 1, created_at: T0 },
    { version: 2, created_at: T1 },
  ],
};
const RUN = {
  run_id: RUN_ID,
  agent_id: ID,
  agent_version: 2,
  status: "succeeded",
  requested_at: T0,
  requested_by: ID,
  started_at: T1,
  finished_at: T2,
  failure_reason: null,
  trace_id: "4bf92f3577b34da6a3ce929d0e0e4736",
  cancel_requested_at: null,
};
const WORKFLOW = {
  id: ID,
  name: "triage-flow",
  current_version: 4,
  nodes: [
    { id: "start", kind: "START" },
    { id: "classify", kind: "AGENT" },
    { id: "end", kind: "END" },
  ],
  edges: [
    { source: "start", target: "classify" },
    { source: "classify", target: "end", label: "ok" },
  ],
};
const WORKFLOW_RUN = {
  workflow_run_id: RUN_ID,
  workflow_id: ID,
  workflow_version: 4,
  workflow_version_id: "0198bbbb-0000-7000-8000-000000000001",
  status: "waiting_run",
  current_node_id: "classify",
  waiting_run_id: "0198cccc-0000-7000-8000-000000000001",
  waiting_node_execution_id: null,
  wake_at: null,
  requested_at: T0,
  started_at: T1,
  finished_at: null,
  failure_reason: null,
};
const page = (item: unknown) => ({ items: [item], next_cursor: "next-1" });

/**
 * 경로(app 아래 page.tsx 를 스캔한 결과와 같은 모양)를 키로 하는 입력 표.
 * 새 화면이 생기면 여기에 항목이 없어 러너가 실패합니다 - 조용히 건너뛰지 않습니다.
 */
export const ROUTE_TABLE: RouteTable = {
  "/": { client: { healthz: { service: "aether-api", version: "0.1.0" } } },
  "/settings": { client: { healthz: { service: "aether-api", version: "0.1.0" } } },
  "/agents": { client: { listAgents: page(AGENT) } },
  "/agents/new": {},
  "/agents/[id]/chat": { params: { id: ID }, client: { getAgent: AGENT_DETAIL } },
  "/agents/[id]/edit": { params: { id: ID }, client: { getAgent: AGENT_DETAIL } },
  "/agents/[id]/settings": { params: { id: ID }, client: { getAgent: AGENT_DETAIL } },
  "/knowledge": {
    client: { listKnowledgeSets: page({ id: ID, name: "handbook", created_at: T0 }) },
  },
  "/knowledge/[id]": {
    params: { id: ID },
    client: {
      listIngestions: page({
        ingestion_id: RUN_ID,
        knowledge_set_id: ID,
        source: "handbook.md",
        status: "succeeded",
        requested_at: T0,
        started_at: T1,
        finished_at: T2,
        failure_reason: null,
      }),
    },
  },
  "/runs": { client: { listRuns: page(RUN) } },
  "/runs/[id]": { params: { id: RUN_ID }, client: { getRun: RUN } },
  "/workflows": {
    client: {
      listWorkflows: page({
        id: ID,
        name: "triage-flow",
        current_version: 4,
        created_at: T0,
        updated_at: T1,
      }),
      listWorkflowRuns: page(WORKFLOW_RUN),
    },
  },
  "/workflows/new": {},
  "/workflows/[id]": { params: { id: ID }, client: { getWorkflow: WORKFLOW } },
  "/workflows/runs/[id]": {
    params: { id: RUN_ID },
    client: {
      listWorkflowRunNodes: page({
        node_id: "classify",
        kind: "AGENT",
        status: "failed",
        started_at: T1,
        finished_at: T2,
        failure_reason: "tool_denied",
      }),
    },
  },
};
