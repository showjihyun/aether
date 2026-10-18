import type { IngestionStatus } from "@aether/sdk";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { IngestionStatusBadge } from "./IngestionStatusBadge";

afterEach(cleanup);

// 키 집합이 SDK 의 IngestionStatus 와 다르면 타입 검사가 깨집니다(누락·초과 모두).
const ALL = {
  queued: true,
  running: true,
  succeeded: true,
  failed: true,
} satisfies Record<IngestionStatus, true>;
const STATUSES = Object.keys(ALL) as IngestionStatus[];

function render1(status: IngestionStatus) {
  const { container } = render(<IngestionStatusBadge status={status} />);
  const badge = container.querySelector("[data-slot='badge']");
  return { badge, icon: badge?.querySelector("svg") };
}

describe("IngestionStatusBadge", () => {
  it.each(STATUSES)("DESIGN 6: %s 는 텍스트와 아이콘으로 그려진다", (status) => {
    const { badge, icon } = render1(status);
    expect(badge?.textContent).toBe(status);
    expect(icon).toBeTruthy();
    expect(icon?.getAttribute("aria-hidden")).toBe("true");
  });

  it("DESIGN 6: running 은 회전, failed 는 destructive", () => {
    expect(render1("running").icon?.getAttribute("class")).toContain("animate-spin");
    cleanup();
    expect(render1("queued").icon?.getAttribute("class") ?? "").not.toContain("animate-spin");
    cleanup();
    expect(render1("failed").badge?.getAttribute("data-variant")).toBe("destructive");
    cleanup();
    expect(render1("succeeded").badge?.getAttribute("data-variant")).toBe("secondary");
  });
});
