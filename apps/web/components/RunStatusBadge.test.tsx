import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RunStatusBadge, type RunStatus } from "./RunStatusBadge";

const STATUSES: RunStatus[] = [
  "queued",
  "running",
  "waiting",
  "succeeded",
  "failed",
  "cancelled",
  "timed_out",
];

describe("RunStatusBadge", () => {
  it.each(STATUSES)("renders the %s status as text with an icon", (status) => {
    const { container, getByText } = render(<RunStatusBadge status={status} />);

    expect(getByText(status)).toBeTruthy();
    expect(container.querySelector("[data-slot='badge'] svg")).toBeTruthy();
  });
});
