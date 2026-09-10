import { CircleAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** 표시용 컴포넌트. `healthz()` 의 결과(또는 실패)를 받아 그리기만 합니다 — fetch 를 모릅니다. */
export interface HealthzCardProps {
  status: "ok" | "error";
  service?: string;
  version?: string;
  message?: string;
}

export function HealthzCard({ status, service, version, message }: HealthzCardProps) {
  if (status === "error") {
    // DESIGN.md 7절: 오류 메시지는 사용자가 할 수 있는 일을 말합니다.
    return (
      <Alert variant="destructive">
        <CircleAlert aria-hidden="true" />
        <AlertTitle>api 에 닿지 못했습니다</AlertTitle>
        <AlertDescription>
          <p>{message}</p>
          <p>api 가 떠 있는지 확인한 뒤 새로고침 하세요.</p>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>aether</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-2 text-sm">
          <dt className="text-muted-foreground">status</dt>
          <dd>
            <Badge variant="secondary">{status}</Badge>
          </dd>
          <dt className="text-muted-foreground">service</dt>
          <dd>{service}</dd>
          <dt className="text-muted-foreground">version</dt>
          <dd>{version}</dd>
        </dl>
      </CardContent>
    </Card>
  );
}
