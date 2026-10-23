/**
 * Workflow 그래프 위반 사유의 문장(spec 0007 R-4).
 *
 * **키와 문장의 정본은 `DESIGN.md` 6절 「Workflow 그래프 위반 사유」 표입니다** - 여기서 문구를
 * 새로 쓰지 않고 옮깁니다. api 의 `Reason` 열거형·그 표·이 맵의 키 집합이 같음을
 * `tests/scripts/test_workflow_violation_reasons.py` 가 판정하므로, api 에 사유가 늘면 문장 없는
 * 값이 그 자리에서 드러납니다.
 */
export const VIOLATION_SENTENCE: Record<string, string> = {
  no_start: "START 노드가 없습니다. 시작 노드 하나를 두십시오",
  multiple_start: "START 노드가 둘 이상입니다. 하나만 둘 수 있습니다",
  end_unreachable: "이 END 노드에 도달할 수 없습니다 — 시작에서 이어지는 길이 없습니다",
  orphan_node: "이 노드는 아무 간선에도 닿지 않습니다",
  dangling_edge: "이 간선이 없는 노드를 가리킵니다",
  duplicate_node_id: "같은 노드 id 가 둘 이상입니다",
  loop_without_bound: "LOOP 노드에 반복 상한(`max_iterations`)이 없습니다",
  parallel_without_join: "PARALLEL 노드에 대응하는 JOIN 이 없습니다",
  agent_node_without_agent: "실행 대상 참조가 없습니다 — `AGENT` 는 Agent, `TOOL`·`MCP` 는 서버와 도구 이름이 필요합니다",
  condition_node_without_predicate: "조건이 비어 있습니다 — 볼 경로와 비교 방법이 필요합니다",
  condition_node_without_both_branches: "참·거짓 두 갈래가 모두 있어야 합니다 — 나가는 간선의 label 이 `true` 와 `false` 입니다",
  wait_node_without_duration: "WAIT 노드에 기다릴 시간(`wait_seconds`)이 없습니다",
  llm_node_without_prompt: "LLM 노드에 프롬프트가 없습니다",
  tool_node_without_target: "TOOL·MCP 노드에 서버와 도구 이름이 필요합니다",
};

/** 맵에 없는 사유(api 가 앞서갔을 때)도 던지지 않고, 사유 코드를 보여 줍니다. */
export function violationSentence(reason: string): string {
  return Object.hasOwn(VIOLATION_SENTENCE, reason)
    ? VIOLATION_SENTENCE[reason]!
    : `그래프가 api 의 검증 규칙을 어겼습니다(사유 코드: ${reason}).`;
}
