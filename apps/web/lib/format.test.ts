import { describe, expect, it } from "vitest";

import { formatDuration, formatRelative, shortId } from "./format";

describe("shortId", () => {
  it("DESIGN 6절: 앞 8자 + 줄임표", () => {
    expect(shortId("0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b")).toBe("0198a1b2…");
  });
});

describe("formatRelative", () => {
  const now = new Date("2026-10-18T12:00:00Z");

  it("DESIGN 6절: 상대 시간 (3분 전)", () => {
    expect(formatRelative("2026-10-18T11:57:00Z", now)).toBe("3분 전");
    expect(formatRelative("2026-10-18T09:00:00Z", now)).toBe("3시간 전");
    expect(formatRelative("2026-10-16T12:00:00Z", now)).toBe("2일 전");
    expect(formatRelative("2026-10-18T11:59:50Z", now)).toBe("방금");
  });
});

describe("formatDuration", () => {
  it("DESIGN 6절: 소요 시간은 1m 12s", () => {
    expect(formatDuration("2026-10-18T10:00:00Z", "2026-10-18T10:01:12Z")).toBe("1m 12s");
    expect(formatDuration("2026-10-18T10:00:00Z", "2026-10-18T10:00:07Z")).toBe("7s");
    expect(formatDuration("2026-10-18T10:00:00Z", "2026-10-18T11:02:03Z")).toBe("1h 2m 3s");
  });

  it("끝나지 않았거나 시작하지 않았으면 대시", () => {
    expect(formatDuration("2026-10-18T10:00:00Z", null)).toBe("—");
    expect(formatDuration(null, null)).toBe("—");
  });
});
