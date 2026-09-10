/** 표시용 컴포넌트. `healthz()` 의 결과(또는 실패)를 받아 그리기만 합니다 — fetch 를 모릅니다. */
export interface HealthzCardProps {
  status: "ok" | "error";
  service?: string;
  version?: string;
  message?: string;
}

export function HealthzCard({ status, service, version, message }: HealthzCardProps) {
  if (status === "error") {
    return (
      <main>
        <h1>aether</h1>
        <p role="alert">api 에 닿지 못했습니다: {message}</p>
      </main>
    );
  }

  return (
    <main>
      <h1>aether</h1>
      <dl>
        <dt>status</dt>
        <dd>{status}</dd>
        <dt>service</dt>
        <dd>{service}</dd>
        <dt>version</dt>
        <dd>{version}</dd>
      </dl>
    </main>
  );
}
