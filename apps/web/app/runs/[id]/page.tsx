import { createClient } from "@aether/sdk";

import { CopyableId } from "@/components/CopyableId";
import { RelativeTime } from "@/components/RelativeTime";
import { RunStatusBadge } from "@/components/RunStatusBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EMPTY_CELL, formatDuration } from "@/lib/format";

import { RunDetailError } from "./RunDetailError";
import { RunTabs } from "./RunTabs";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(홈 화면과 같은 이유).
export const dynamic = "force-dynamic";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

export default async function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
  });

  let run;
  try {
    run = await client.getRun(id);
  } catch (error) {
    return <RunDetailError error={error} />;
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <RunStatusBadge status={run.status} />
            <CopyableId id={run.run_id} />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Field label="trace id">
              {run.trace_id ? <CopyableId id={run.trace_id} /> : EMPTY_CELL}
            </Field>
            <Field label="Agent">
              <span className="flex items-center gap-2">
                <CopyableId id={run.agent_id} />
                <Badge variant="outline">v{run.agent_version}</Badge>
              </span>
            </Field>
            <Field label="요청자">
              {/* Workflow 가 선언한 자식 Run 은 요청 주체가 없습니다(마이그레이션 0007). */}
              {run.requested_by ? <CopyableId id={run.requested_by} /> : "Workflow 가 선언"}
            </Field>
            <Field label="소요">{formatDuration(run.started_at, run.finished_at)}</Field>
            <Field label="요청">
              <RelativeTime iso={run.requested_at} />
            </Field>
            <Field label="시작">
              <RelativeTime iso={run.started_at} />
            </Field>
            <Field label="종료">
              <RelativeTime iso={run.finished_at} />
            </Field>
            {run.failure_reason ? (
              <Field label="실패 사유">
                <span className="font-mono text-xs">{run.failure_reason}</span>
              </Field>
            ) : null}
          </dl>
        </CardContent>
      </Card>

      <RunTabs
        runId={run.run_id}
        // 브라우저가 닿는 주소입니다. 서버 쪽 `AETHER_API_URL`(compose 안에서는 http://api:8000)과
        // 다를 수 있어 따로 둡니다.
        apiBaseUrl={process.env.AETHER_PUBLIC_API_URL ?? "http://localhost:8000"}
        traceId={run.trace_id}
      />
    </div>
  );
}
