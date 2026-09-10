import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HealthzCard } from "./HealthzCard";

describe("HealthzCard", () => {
  it("shows status, service and version when ok", () => {
    render(<HealthzCard status="ok" service="api" version="dev" />);

    expect(screen.getByText("ok").textContent).toBe("ok");
    expect(screen.getByText("api").textContent).toBe("api");
    expect(screen.getByText("dev").textContent).toBe("dev");
  });

  it("shows an error message when the api call failed", () => {
    render(<HealthzCard status="error" message="fetch failed" />);

    expect(screen.getByRole("alert").textContent).toContain("fetch failed");
  });
});
