"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { NAV_ITEMS } from "@/components/nav-items";

function currentLocationLabel(pathname: string): string {
  const active = NAV_ITEMS.find((item) => pathname.startsWith(item.href));
  return active?.label ?? "Overview";
}

/**
 * DESIGN.md 5절의 헤더: 현재 위치 텍스트 + 테마 토글.
 * `lg` 미만에서는 사이드바 대신 이 헤더의 sheet 로 사이드바 내비게이션을 엽니다(8절 반응형).
 */
export function AppHeader() {
  const pathname = usePathname();

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-4">
      <Sheet>
        <SheetTrigger asChild>
          <Button variant="outline" size="icon" className="lg:hidden" aria-label="메뉴 열기">
            <Menu className="size-4" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-64 p-0">
          <SheetHeader className="border-b border-border">
            <SheetTitle>aether</SheetTitle>
          </SheetHeader>
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
        </SheetContent>
      </Sheet>
      <p className="flex-1 text-sm font-medium">{currentLocationLabel(pathname)}</p>
      <ThemeToggle />
    </header>
  );
}
