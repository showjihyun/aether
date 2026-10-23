import type { WorkflowResponse } from "@aether/sdk";
import {
  Bot,
  CircleStop,
  GitBranch,
  GitFork,
  GitMerge,
  Hand,
  type LucideIcon,
  Plug,
  Play,
  Repeat,
  Sparkles,
  Timer,
  User,
  Wrench,
} from "lucide-react";

export type NodeKind = WorkflowResponse["nodes"][number]["kind"];

/**
 * DESIGN.md 6절 `NodeKind` 표의 정본 구현. 키 집합은 SDK 의 타입과 `Record<NodeKind, …>` 로
 * 묶여 있어 api 에 종류가 하나 생기면 **컴파일이 깨집니다**. 아이콘을 바꾸거나 더하려면
 * 문서의 표를 먼저 고칩니다. `WAIT` 는 `waiting_timer`, `APPROVAL` 은 `waiting_approval` 과
 * 같은 아이콘입니다(같은 뜻).
 */
export const NODE_KIND_ICON: Record<NodeKind, LucideIcon> = {
  START: Play,
  END: CircleStop,
  AGENT: Bot,
  CONDITION: GitBranch,
  PARALLEL: GitFork,
  JOIN: GitMerge,
  LOOP: Repeat,
  WAIT: Timer,
  LLM: Sparkles,
  MCP: Plug,
  TOOL: Wrench,
  HUMAN: User,
  APPROVAL: Hand,
};
