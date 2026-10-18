import { existsSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { NAV_ITEMS } from "@/components/nav-items";

const appDir = import.meta.dirname;

function hasRoute(href: string): boolean {
  const dir = join(appDir, href);
  return existsSync(join(dir, "page.tsx")) || existsSync(join(dir, "page.ts"));
}

function missingRoutes(): string[] {
  return NAV_ITEMS.filter((item) => !hasRoute(item.href)).map((item) => item.href);
}

describe("사이드바의 링크에 404 가 없다", () => {
  // spec 0006 R-6. 목록을 하드코딩하지 않고 NAV_ITEMS 에서 수집합니다.
  //
  // 이 단언은 MVP-2c 전까지 의도된 빨강(it.fails)이었습니다. 라우트가 채워진 경과:
  //   /agents, /runs                 -> MVP-2a
  //   /knowledge, /workflows         -> MVP-2c (화면 셋)
  //   /settings                      -> MVP-2c (spec 0006 D-13: 테마·연결 정보·CLI 안내만, 키는 만들지도 보이지도 않음)
  // 이제 세 경로가 모두 있으므로 평범한 `it` 입니다. 사이드바에 항목이 추가되고 라우트가
  // 없으면 이 단언이 깨집니다.
  it("NAV_ITEMS 의 모든 href 에 라우트(page.tsx)가 있다", () => {
    expect(missingRoutes()).toEqual([]);
  });

  it("hasRoute 는 존재하는 라우트와 없는 라우트를 구분한다 (위 단언이 공허하지 않다는 증거)", () => {
    expect(hasRoute("/agents")).toBe(true);
    expect(hasRoute("/runs")).toBe(true);
    expect(hasRoute("/definitely-not-a-route")).toBe(false);
  });
});
