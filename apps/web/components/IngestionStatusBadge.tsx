import type { IngestionStatus } from "@aether/sdk";
import { CircleCheck, CircleX, Clock, Loader2, type LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

interface StatusConfig {
  variant: BadgeVariant;
  icon: LucideIcon;
  spin?: boolean;
}

/** DESIGN.md 6절 표. 적재 상태는 네 개이고 SDK 의 `IngestionStatus` 와 타입으로 묶여 있습니다. */
const STATUS_CONFIG: Record<IngestionStatus, StatusConfig> = {
  queued: { variant: "secondary", icon: Clock },
  running: { variant: "default", icon: Loader2, spin: true },
  succeeded: { variant: "secondary", icon: CircleCheck },
  failed: { variant: "destructive", icon: CircleX },
};

export function IngestionStatusBadge({ status }: { status: IngestionStatus }) {
  const { variant, icon: Icon, spin } = STATUS_CONFIG[status];

  return (
    <Badge variant={variant}>
      <Icon aria-hidden="true" className={spin ? "animate-spin" : undefined} />
      {status}
    </Badge>
  );
}
