/** DESIGN.md 5절: 사이드바 항목은 MVP 범위만입니다. 대상 페이지는 아직 없어도 됩니다(MVP-2). */
export interface NavItem {
  href: string;
  label: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/agents", label: "Agents" },
  { href: "/runs", label: "Runs" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/workflows", label: "Workflows" },
  { href: "/settings", label: "Settings" },
];
