import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { LoadMore } from "./ListStates";

afterEach(cleanup);

function href(ui: React.ReactElement): string | null | undefined {
  render(ui);
  return screen.getByRole("link", { name: "다음 쪽" }).getAttribute("href");
}

describe("LoadMore", () => {
  it("MVP-2a: 기존 호출(/agents, /runs)의 주소는 글자 그대로다", () => {
    expect(href(<LoadMore basePath="/agents" nextCursor="abc" />)).toBe("/agents?cursor=abc");
    cleanup();
    expect(href(<LoadMore basePath="/runs" nextCursor="a b/c" />)).toBe("/runs?cursor=a%20b%2Fc");
  });

  it("MVP-2c: basePath 에 이미 쿼리가 있으면 &, 없으면 ? 로 잇는다 (? 가 두 번 나오지 않는다)", () => {
    const h = href(<LoadMore basePath="/workflows?runsCursor=r1" nextCursor="d2" />);
    expect(h).toBe("/workflows?runsCursor=r1&cursor=d2");
    expect(h?.match(/\?/g)).toHaveLength(1);
  });

  it("MVP-2c: 쿼리 이름을 고를 수 있다 (두 번째 표의 runsCursor)", () => {
    expect(href(<LoadMore basePath="/workflows" param="runsCursor" nextCursor="r2" />)).toBe(
      "/workflows?runsCursor=r2",
    );
  });

  it("DESIGN 7.1: next_cursor 가 없으면 아무것도 그리지 않는다", () => {
    const { container } = render(<LoadMore basePath="/runs" nextCursor={null} />);
    expect(container.innerHTML).toBe("");
  });
});
