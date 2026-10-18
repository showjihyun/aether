import { createClient } from "@aether/sdk";

import { ThemeToggle } from "@/components/ThemeToggle";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { HealthzCard } from "../HealthzCard";

// 정적 프리렌더가 빌드 시 api 를 부르면 web-build 가 api 없이 실패합니다(홈 화면과 같은 이유).
export const dynamic = "force-dynamic";

/** 브라우저가 api 를 부르는 경로 — 중계(D-15). 서버 쪽 `AETHER_API_URL` 은 내부 주소라 보이지 않습니다. */
const BROWSER_API_ADDRESS = "/api/aether";

const KEY_COMMAND = "docker compose -f infra/docker/compose.yaml exec api aether-api keys create --label web";

// 이 화면은 키를 만들지도 보이지도 않습니다(spec 0006 D-13). 환경변수의 값은 어느 것도 읽어 찍지 않고,
// `/healthz` 는 인증이 필요 없으므로 키 없이 부릅니다 — 그래서 키가 없어도 화면이 뜹니다.
export default async function SettingsPage() {
  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "http://localhost:8000",
  });

  let connection;
  try {
    const result = await client.healthz();
    connection = (
      <HealthzCard
        title="연결"
        status="ok"
        service={result.service}
        version={result.version}
        apiAddress={BROWSER_API_ADDRESS}
      />
    );
  } catch (error) {
    connection = (
      <HealthzCard
        title="연결"
        status="error"
        message={error instanceof Error ? error.message : String(error)}
        apiAddress={BROWSER_API_ADDRESS}
      />
    );
  }

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>테마</CardTitle>
        </CardHeader>
        <CardContent>
          <ThemeToggle />
        </CardContent>
      </Card>

      {connection}

      <Card>
        <CardHeader>
          <CardTitle>키 안내</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 text-sm">
          <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs">{KEY_COMMAND}</pre>
          <p className="text-muted-foreground">
            원문은 발급 때 한 번만 출력됩니다. 출력된 값을 web 컨테이너의{" "}
            <code className="font-mono text-xs">AETHER_WEB_API_KEY</code> 에 넣습니다.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
