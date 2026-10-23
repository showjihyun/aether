import { describe, expect, it } from "vitest";

import { VIOLATION_SENTENCE, violationSentence } from "./workflowViolations";

describe("violationSentence (spec 0007 R-4; DESIGN 6절 「Workflow 그래프 위반 사유」)", () => {
  it("R-4: 알려진 사유는 DESIGN 6절 표의 문장 그대로다 (고정값)", () => {
    expect(violationSentence("no_start")).toBe("START 노드가 없습니다. 시작 노드 하나를 두십시오");
    expect(violationSentence("agent_node_without_agent")).toBe(
      "실행 대상 참조가 없습니다 — `AGENT` 는 Agent, `TOOL`·`MCP` 는 서버와 도구 이름이 필요합니다",
    );
    expect(violationSentence("wait_node_without_duration")).toBe(
      "WAIT 노드에 기다릴 시간(`wait_seconds`)이 없습니다",
    );
  });

  it("api 에 새 사유가 생겨 맵에 없어도 던지지 않고, 사유 코드를 보이는 일반 문장이다", () => {
    expect(violationSentence("brand_new_reason")).toContain("brand_new_reason");
  });

  it("맵의 모든 문장은 비어 있지 않다", () => {
    for (const [reason, sentence] of Object.entries(VIOLATION_SENTENCE)) {
      expect(sentence.trim().length, reason).toBeGreaterThan(0);
    }
  });
});
