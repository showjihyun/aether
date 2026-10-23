import { readdirSync } from "node:fs";
import { join, relative, sep } from "node:path";

/** 한 경로를 렌더하는 데 필요한 입력. 경로(`/agents/[id]/chat` 형태)를 키로 하는 표의 값입니다. */
export interface RouteEntry {
  params?: Record<string, string>;
  searchParams?: Record<string, string>;
  /** `@aether/sdk` 의 client 메서드 이름 -> 가짜 응답. */
  client?: Record<string, unknown>;
  /** 키가 없을 때 화면(MissingApiKey)을 검사하려면 false. 기본은 키가 있는 상태. */
  apiKey?: boolean;
}

export type RouteTable = Record<string, RouteEntry>;

export interface Target {
  route: string;
  entry: RouteEntry;
}

/** `app/` 아래의 `page.tsx` 를 파일 시스템에서 모읍니다. `app/api` 는 라우트 핸들러라 뺍니다. */
export function scanRoutes(appDir: string): string[] {
  const routes: string[] = [];
  const walk = (dir: string): void => {
    for (const dirent of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, dirent.name);
      if (dirent.isDirectory()) {
        if (dir === appDir && dirent.name === "api") continue;
        walk(full);
      } else if (dirent.name === "page.tsx" || dirent.name === "page.ts") {
        const rel = relative(appDir, dir).split(sep).join("/");
        routes.push(rel === "" ? "/" : `/${rel}`);
      }
    }
  };
  walk(appDir);
  return routes.sort();
}

/**
 * 스캔한 경로마다 표의 항목을 찾습니다. 이 함수가 러너의 거짓 성공 경로를 막습니다 -
 * 대상이 0개이거나 표에 없는 경로가 있으면 조용히 건너뛰지 않고 던집니다.
 */
export function resolveTargets(routes: string[], table: RouteTable): Target[] {
  if (routes.length === 0) {
    throw new Error("a11y 검사 대상이 0개입니다 - 경로 수집이 비었습니다.");
  }
  const missing = routes.filter((route) => !(route in table));
  if (missing.length > 0) {
    throw new Error(`a11y 입력 표에 없는 경로: ${missing.join(", ")}`);
  }
  return routes.map((route) => ({ route, entry: table[route] as RouteEntry }));
}
