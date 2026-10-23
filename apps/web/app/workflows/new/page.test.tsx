import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("../actions", () => ({ createWorkflowAction: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import NewWorkflowPage from "./page";

beforeAll(() => {
  class RO {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = RO;
  (SVGElement.prototype as unknown as { getBBox: () => object }).getBBox = () => ({
    x: 0, y: 0, width: 40, height: 16,
  });
  globalThis.DOMMatrixReadOnly ??= class {
    m22 = 1;
  } as unknown as typeof DOMMatrixReadOnly;
});
afterEach(cleanup);

describe("/workflows/new (P5-6; DESIGN 5절)", () => {
  it("api 를 부르지 않는 화면이다 - 편집기가 열리고 저장 안내가 있다", () => {
    render(<NewWorkflowPage />);
    expect(screen.getByRole("heading", { name: "새 Workflow" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "저장" })).toBeTruthy();
    expect(screen.getByTestId("save-note")).toBeTruthy();
  });
});
