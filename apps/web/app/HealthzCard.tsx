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
  /** card 제목. 기본은 홈 화면의 "aether". */
  title?: string;
  /** 브라우저가 쓰는 api 주소(읽기 전용). 주면 성공·실패 양쪽에서 보입니다. */
  apiAddress?: string;
}

export function HealthzCard({
  status,
  service,
  version,
  message,
  title = "aether",
  apiAddress,
}: HealthzCardProps) {
  if (status === "error") {
    // DESIGN.md 7절: 오류 메시지는 사용자가 할 수 있는 일을 말합니다.
    return (
      <Alert variant="destructive">
        <CircleAlert aria-hidden="true" />
        <AlertTitle>api 에 닿지 못했습니다</AlertTitle>
        <AlertDescription>
          <p>{message}</p>
          <p>api 가 떠 있는지 확인한 뒤 새로고침 하세요.</p>
          {apiAddress ? (
            <p>
              브라우저 api 주소 <code className="font-mono text-xs">{apiAddress}</code>
            </p>
          ) : null}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
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
          {apiAddress ? (
            <>
              <dt className="text-muted-foreground">브라우저 api 주소</dt>
              <dd className="font-mono text-xs">{apiAddress}</dd>
            </>
          ) : null}
        </dl>
      </CardContent>
    </Card>
  );
}
