/**
 * a11y 러너 (spec 0007 R-7, D-7). 브라우저 없이 jsdom 에 렌더하고 axe-core 로 WCAG 2.2 AA 를 검사합니다.
 * 경로별 위반을 출력하고, 위반이 있어도 실패하지 않습니다(첫 바퀴). 실패하는 것은
 * 대상 0개 / 표에 없는 경로 / 렌더가 터짐 뿐입니다.
 */
import { cleanup, render } from "@testing-library/react";
import axe from "axe-core";
import { join } from "node:path";
import { createElement, type ReactElement } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/AppShell";
import { ThemeProvider } from "@/components/ThemeProvider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

import { ROUTE_TABLE } from "./fixtures";
import { resolveTargets, scanRoutes, type RouteEntry } from "./targets";

let currentClient: Record<string, unknown> = {};
// 표에 없는 client 메서드 접근 기록. 페이지가 오류를 삼켜 오류 화면을 그리므로 던지는 것만으로는 안 잡힙니다.
let unregistered: string[] = [];
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: () =>
    new Proxy(
      {},
      {
        get: (_t, name: string) => {
          if (name === "streamRunEvents") return async function* () {};
          return () => {
            if (name in currentClient) return Promise.resolve(currentClient[name]);
            unregistered.push(name);
            return Promise.reject(new Error(`a11y 표에 없는 client 메서드: ${name}`));
          };
        },
      },
    ),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

const appDir = join(import.meta.dirname, "..", "app");

// 앱 셸 안에서 렌더합니다 - layout.tsx 와 같은 것(html 과 body 는 jsdom 루트에 못 올립니다).
function Shell({ children }: { children: ReactElement }) {
  return (
    <ThemeProvider>
      <TooltipProvider>
        <AppShell>{children}</AppShell>
        <Toaster />
      </TooltipProvider>
    </ThemeProvider>
  );
}

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

interface Row {
  route: string;
  rules: Map<string, { impact: string | null | undefined; nodes: number }>;
  passes: number;
  incomplete: Map<string, number>;
}
const rows: Row[] = [];

beforeAll(() => {
  class RO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = RO;
  // jsdom 에는 matchMedia 가 없습니다(next-themes 가 읽습니다).
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent: () => false,
    }),
  });
  (SVGElement.prototype as unknown as { getBBox: () => object }).getBBox = () => ({
    x: 0,
    y: 0,
    width: 40,
    height: 16,
  });
  globalThis.DOMMatrixReadOnly ??= class {
    m22 = 1;
  } as unknown as typeof DOMMatrixReadOnly;
});
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

async function renderRoute(route: string, entry: RouteEntry): Promise<HTMLElement> {
  const file = join(appDir, route === "/" ? "" : route, "page.tsx").split("\\").join("/");
  const mod = (await import(/* @vite-ignore */ file)) as { default: unknown };
  currentClient = entry.client ?? {};
  unregistered = [];
  vi.stubEnv("AETHER_API_KEY", entry.apiKey === false ? "" : "aeth_test_fake_key");
  const props = {
    params: Promise.resolve(entry.params ?? {}),
    searchParams: Promise.resolve(entry.searchParams ?? {}),
  };
  // 서버 컴포넌트는 async 함수라 직접 await 해서 요소를 얻습니다.
  const ui = (await (mod.default as (p: unknown) => unknown)(props)) as ReactElement;
  const { container } = render(<Shell>{ui}</Shell>);
  // 클라이언트 컴포넌트의 효과(스트림 시도 등)가 가라앉게 한 틱 기다립니다.
  await new Promise((resolve) => setTimeout(resolve, 0));
  return container;
}

describe("a11y 러너 (WCAG 2.2 AA, jsdom)", () => {
  const routes = scanRoutes(appDir);

  it("검사 대상이 있고 모두 표에 항목이 있다 (0개면 실패)", () => {
    expect(() => resolveTargets(routes, ROUTE_TABLE)).not.toThrow();
  });

  it("탐지기가 살아 있다: alt 없는 이미지는 image-alt 위반으로 잡힌다 (위반 0건이 공허하지 않다는 증거)", async () => {
    const { container } = render(createElement("img", { src: "x.png" }));
    const results = await axe.run(container, { runOnly: { type: "tag", values: TAGS } });
    expect(results.violations.map((v) => v.id)).toContain("image-alt");
  });

  // 대상 수집이 비면 위 단언이 실패하고, 표에 없는 경로는 아래 각 항목이 던집니다.
  it.each(routes)("%s", async (route) => {
    const [target] = resolveTargets([route], ROUTE_TABLE);
    if (!target) throw new Error(`대상 없음: ${route}`);
    const container = await renderRoute(route, target.entry);
    const results = await axe.run(container, { runOnly: { type: "tag", values: TAGS } });
    const rules = new Map<string, { impact: string | null | undefined; nodes: number }>();
    for (const v of results.violations) rules.set(v.id, { impact: v.impact, nodes: v.nodes.length });
    // 표에 없는 호출이 있었다면 의도한 화면이 아니라 오류 화면을 검사한 것입니다.
    expect(unregistered, `${route}: 표에 없는 client 메서드 호출: ${unregistered.join(", ")}`).toEqual([]);
    const incompleteRules = new Map<string, number>();
    for (const v of results.incomplete) incompleteRules.set(v.id, v.nodes.length);
    // 렌더가 비었거나 axe 가 아무 규칙도 돌리지 않았다면 위반 0건이 거짓 초록이 됩니다.
    expect(container.querySelector("main")?.textContent?.trim().length ?? 0).toBeGreaterThan(0);
    expect(results.passes.length).toBeGreaterThan(0);
    rows.push({
      route,
      rules,
      passes: results.passes.length,
      incomplete: incompleteRules,
    });
  });

  afterAll(() => {
    const lines: string[] = ["", "=== a11y 위반 (WCAG 2.2 AA, jsdom) ==="];
    let totalRules = 0;
    let totalNodes = 0;
    const byRule = new Map<string, number>();
    const incompleteByRule = new Map<string, number>();
    for (const { route, rules, passes, incomplete } of rows) {
      const nodes = [...rules.values()].reduce((n, r) => n + r.nodes, 0);
      lines.push(
        `${route}: 규칙 ${rules.size}건, 요소 ${nodes}건 (통과 규칙 ${passes}, 판정불가 ${incomplete.size})`,
      );
      for (const [id, r] of rules) {
        lines.push(`  - ${id} (${r.impact ?? "n/a"}): ${r.nodes}`);
        byRule.set(id, (byRule.get(id) ?? 0) + r.nodes);
      }
      for (const [id, n] of incomplete) {
        lines.push(`  ? ${id} (판정불가): ${n}`);
        incompleteByRule.set(id, (incompleteByRule.get(id) ?? 0) + n);
      }
      totalRules += rules.size;
      totalNodes += nodes;
    }
    lines.push(`검사한 경로 ${rows.length}개 / 규칙 위반 ${totalRules}건 / 요소 위반 ${totalNodes}건`);
    for (const [id, n] of [...byRule].sort()) lines.push(`  총 ${id}: ${n}`);
    for (const [id, n] of [...incompleteByRule].sort()) lines.push(`  총 판정불가 ${id}: ${n}`);
    process.stdout.write(`${lines.join("\n")}\n`);
  });
});
