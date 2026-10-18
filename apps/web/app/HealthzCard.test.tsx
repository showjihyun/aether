import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { HealthzCard } from "./HealthzCard";

describe("HealthzCard", () => {
  afterEach(cleanup);

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

  it("keeps the default title, and shows a custom title and api address only when given", () => {
    const { rerender } = render(<HealthzCard status="ok" service="api" version="dev" />);
    expect(screen.getByText("aether")).toBeTruthy();
    expect(screen.queryByText("브라우저 api 주소")).toBeNull();

    rerender(<HealthzCard status="ok" service="api" version="dev" title="연결" apiAddress="/api/aether" />);
    expect(screen.getByText("연결")).toBeTruthy();
    expect(screen.getByText("/api/aether")).toBeTruthy();
  });

  it("shows the api address next to the error too", () => {
    render(<HealthzCard status="error" message="fetch failed" apiAddress="/api/aether" />);

    expect(screen.getByText("/api/aether")).toBeTruthy();
  });
});
