import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { resolveTargets, scanRoutes } from "./targets";

const appDir = join(import.meta.dirname, "..", "app");

describe("a11y 러너의 검사 대상 수집 (spec 0007 R-7, D-7, plan P5-8 red 증거)", () => {
  it("spec 0007 R-7: 검사 대상이 0개이면 실패한다 (아무것도 검사하지 않는 초록 방지)", () => {
    expect(() => resolveTargets([], { "/": {} })).toThrow(/0개/);
  });

  it("spec 0007 R-7: 표에 항목이 없는 경로가 있으면 실패하고 그 경로를 말한다", () => {
    expect(() => resolveTargets(["/", "/새-화면"], { "/": {} })).toThrow(/\/새-화면/);
  });

  it("스캔 결과와 표가 맞으면 경로별 항목을 돌려준다", () => {
    const entry = { params: { id: "x" } };
    expect(resolveTargets(["/a/[id]"], { "/a/[id]": entry })).toEqual([
      { route: "/a/[id]", entry },
    ]);
  });

  it("scanRoutes 는 page.tsx 를 찾고 app/api 는 뺀다 (공허하지 않다는 증거)", () => {
    const routes = scanRoutes(appDir);
    expect(routes).toContain("/");
    expect(routes).toContain("/agents/[id]/chat");
    expect(routes.some((r) => r.startsWith("/api"))).toBe(false);
    expect(routes.length).toBeGreaterThan(0);
  });
});
