import { createClient } from "@aether/sdk";

import { HealthzCard } from "./HealthzCard";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(plan 리뷰 F-4).
// 그러므로 이 페이지는 언제나 요청 시 렌더링으로 고정합니다.
export const dynamic = "force-dynamic";

export default async function HomePage() {
  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
  });

  try {
    const result = await client.healthz();
    return (
      <HealthzCard status="ok" service={result.service} version={result.version} />
    );
  } catch (error) {
    return (
      <HealthzCard
        status="error"
        message={error instanceof Error ? error.message : String(error)}
      />
    );
  }
}
