import Link from "next/link";
import type { ReactNode } from "react";

import { AppHeader } from "@/components/AppHeader";
import { NAV_ITEMS } from "@/components/nav-items";

/**
 * DESIGN.md 5절의 앱 셸. 서버 컴포넌트가 기본이고, 상호작용이 필요한 부분(모바일 메뉴,
 * 테마 토글)만 `AppHeader` 아래에서 클라이언트 컴포넌트로 분리합니다.
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-svh">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border lg:flex">
        <div className="flex h-14 shrink-0 items-center border-b border-border px-4 text-sm font-semibold">
          aether
        </div>
        <nav className="flex flex-col gap-1 p-2">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader />
        <main className="mx-auto w-full max-w-6xl flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
