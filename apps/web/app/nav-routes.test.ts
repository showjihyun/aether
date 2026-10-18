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
  // 의도된 빨강입니다 (it.fails = xfail 상당, skip 아님). 라우트가 없는 경로와 채우는 단위:
  //   /knowledge  -> MVP-2c
  //   /workflows  -> MVP-2c
  //   /settings   -> MVP-2c (spec 0006 D-13, 사람 2026-10-18). 에이전트는 사이드바에서
  //                  Settings 를 빼는 쪽을 추천했고 사람이 화면을 만드는 쪽을 골랐습니다 —
  //                  앱 셸에 Settings 가 없는 것이 더 낯설다는 이유입니다. 그 화면은 키를
  //                  만들거나 보여주지 않습니다(테마·연결 정보·CLI 안내만).
  // 모두 채워지면 이 it.fails 는 (통과 = 실패로 취급되어) 스스로 깨지므로
  // 제거(`it` 으로 교체)를 잊을 수 없습니다.
  it.fails("NAV_ITEMS 의 모든 href 에 라우트(page.tsx)가 있다", () => {
    expect(missingRoutes()).toEqual([]);
  });

  it("MVP-2a 가 채우는 둘(/agents, /runs)은 있다", () => {
    expect(hasRoute("/agents")).toBe(true);
    expect(hasRoute("/runs")).toBe(true);
  });

  it("현재 없는 경로 목록 (2c 가 앞의 둘을 채우면 이 단언을 고친다)", () => {
    expect(missingRoutes()).toEqual(["/knowledge", "/workflows", "/settings"]);
  });
});
