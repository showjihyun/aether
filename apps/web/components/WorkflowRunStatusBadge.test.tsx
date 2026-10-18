import type { WorkflowRunStatus } from "@aether/sdk";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { WorkflowRunStatusBadge } from "./WorkflowRunStatusBadge";

afterEach(cleanup);

// SDK 타입과 키 집합이 다르면 **타입 검사**가 깨집니다(누락도 초과도). 새 상태가 생기면
// 여기가 먼저 빨개지므로 badge 매핑을 잊을 수 없습니다 — DESIGN 6절.
const ALL = {
  queued: true,
  running: true,
  waiting_run: true,
  waiting_approval: true,
  waiting_timer: true,
  succeeded: true,
  failed: true,
  cancelled: true,
} satisfies Record<WorkflowRunStatus, true>;
const STATUSES = Object.keys(ALL) as WorkflowRunStatus[];

function render1(status: WorkflowRunStatus) {
  const { container } = render(<WorkflowRunStatusBadge status={status} />);
  const badge = container.querySelector("[data-slot='badge']");
  const icon = badge?.querySelector("svg");
  return { badge, icon, cls: icon?.getAttribute("class") ?? "" };
}

describe("WorkflowRunStatusBadge", () => {
  it.each(STATUSES)("spec 0006 DESIGN 6: %s 는 텍스트와 아이콘으로 그려진다", (status) => {
    const { badge, icon } = render1(status);
    expect(badge?.textContent).toBe(status);
    expect(icon).toBeTruthy();
    expect(icon?.getAttribute("aria-hidden")).toBe("true");
  });

  it("DESIGN 6: 기다림 셋은 전부 outline 이고 아이콘이 서로 다르다 (색이 아니라 모양으로 구분)", () => {
    const run = render1("waiting_run");
    cleanup();
    const approval = render1("waiting_approval");
    cleanup();
    const timer = render1("waiting_timer");
    for (const r of [run, approval, timer]) expect(r.badge?.getAttribute("data-variant")).toBe("outline");
    expect(new Set([run.cls, approval.cls, timer.cls]).size).toBe(3);
    // DESIGN 6절이 Hand 를 "사람을 기다림" 으로 고정했습니다.
    expect(approval.cls).toContain("lucide-hand");
  });

  it("DESIGN 6: running 만 회전하고 failed 는 destructive", () => {
    expect(render1("running").cls).toContain("animate-spin");
    cleanup();
    expect(render1("queued").cls).not.toContain("animate-spin");
    cleanup();
    expect(render1("failed").badge?.getAttribute("data-variant")).toBe("destructive");
  });
});
