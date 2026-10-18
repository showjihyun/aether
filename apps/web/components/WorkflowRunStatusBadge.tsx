import type { WorkflowRunStatus } from "@aether/sdk";
import {
  Ban,
  CircleCheck,
  CircleX,
  Clock,
  CornerDownRight,
  Hand,
  Loader2,
  Timer,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

interface StatusConfig {
  variant: BadgeVariant;
  icon: LucideIcon;
  spin?: boolean;
}

/** DESIGN.md 6절 표. WorkflowRun 의 enum 은 Run 과 다릅니다 — 기다림이 셋(자식 Run·사람·시각)입니다.
 * 키 집합은 SDK 의 `WorkflowRunStatus` 와 타입으로 묶여 있어, 새 상태가 생기면 컴파일이 깨집니다.
 */
const STATUS_CONFIG: Record<WorkflowRunStatus, StatusConfig> = {
  queued: { variant: "secondary", icon: Clock },
  running: { variant: "default", icon: Loader2, spin: true },
  waiting_run: { variant: "outline", icon: CornerDownRight },
  waiting_approval: { variant: "outline", icon: Hand },
  waiting_timer: { variant: "outline", icon: Timer },
  succeeded: { variant: "secondary", icon: CircleCheck },
  failed: { variant: "destructive", icon: CircleX },
  cancelled: { variant: "outline", icon: Ban },
};

export function WorkflowRunStatusBadge({ status }: { status: WorkflowRunStatus }) {
  const { variant, icon: Icon, spin } = STATUS_CONFIG[status];

  return (
    <Badge variant={variant}>
      <Icon aria-hidden="true" className={spin ? "animate-spin" : undefined} />
      {status}
    </Badge>
  );
}
