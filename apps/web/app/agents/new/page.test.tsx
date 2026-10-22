import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../actions", () => ({ createAgentAction: vi.fn(), updateAgentAction: vi.fn() }));

import NewAgentPage from "./page";

afterEach(cleanup);

describe("/agents/new", () => {
  it("R-1: 생성 폼이 그려진다 (이름 칸이 있다)", () => {
    render(<NewAgentPage />);
    expect(screen.getByLabelText("이름")).toBeTruthy();
    expect(screen.getByLabelText("시스템 프롬프트")).toBeTruthy();
    expect(screen.getByTestId("save-note")).toBeTruthy();
  });

  it("저장하지 않고 목록으로 돌아가는 길(취소)이 있다", () => {
    render(<NewAgentPage />);
    expect(screen.getByRole("link", { name: "취소" }).getAttribute("href")).toBe("/agents");
  });
});
