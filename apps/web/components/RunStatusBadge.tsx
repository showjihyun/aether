import { Ban, CircleCheck, CircleX, Clock, Hand, Loader2, TimerOff, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";

/**
 * spec 0001 2.8 의 `data.run_executions.status` enum 과 1:1 입니다.
 * P1-5 에서 `packages/sdk` 가 생성하는 타입으로 교체합니다.
 */
export type RunStatus =
  | "queued"
  | "running"
  | "waiting"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "timed_out";

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

interface StatusConfig {
  variant: BadgeVariant;
  icon: LucideIcon;
  spin?: boolean;
}

/** DESIGN.md 6절 표. 색이 아니라 variant + 아이콘 + 텍스트로 상태를 구분합니다(D-1, 접근성). */
const STATUS_CONFIG: Record<RunStatus, StatusConfig> = {
  queued: { variant: "secondary", icon: Clock },
  running: { variant: "default", icon: Loader2, spin: true },
  waiting: { variant: "outline", icon: Hand },
  succeeded: { variant: "secondary", icon: CircleCheck },
  failed: { variant: "destructive", icon: CircleX },
  cancelled: { variant: "outline", icon: Ban },
  timed_out: { variant: "destructive", icon: TimerOff },
};

export interface RunStatusBadgeProps {
  status: RunStatus;
}

export function RunStatusBadge({ status }: RunStatusBadgeProps) {
  const { variant, icon: Icon, spin } = STATUS_CONFIG[status];

  return (
    <Badge variant={variant}>
      <Icon aria-hidden="true" className={spin ? "animate-spin" : undefined} />
      {status}
    </Badge>
  );
}
