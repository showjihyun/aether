import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const updateAgentSettingsAction = vi.fn<(...args: string[]) => Promise<unknown>>();
const updateAgentAction = vi.fn<(...args: unknown[]) => Promise<unknown>>();
const createAgentAction = vi.fn<(...args: unknown[]) => Promise<unknown>>();
// 패널 넷의 저장이 모이는 곳은 액션 하나입니다 - 다른 액션이 불리면 아래 테스트가 잡습니다.
vi.mock("./actions", () => ({
  updateAgentSettingsAction: (...args: string[]) => updateAgentSettingsAction(...args),
  updateAgentAction: (...args: unknown[]) => updateAgentAction(...args),
  createAgentAction: (...args: unknown[]) => createAgentAction(...args),
}));

import { SettingsForm } from "./SettingsForm";

const AGENT_ID = "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b";
const PROPS = {
  agentId: AGENT_ID,
  name: "billing-helper",
  version: 3,
  modelId: "old-model",
  tools: ["search", "clock"],
  mcpServers: [{ name: "builtin", transport: "stdio" as const, ref: "builtin" }],
  contextBudgetTokens: 4096,
  knowledge: ["faq"],
  knowledgeTopK: 3,
  memoryEnabled: true,
};

beforeEach(() => {
  updateAgentSettingsAction.mockReset();
  updateAgentAction.mockReset();
  createAgentAction.mockReset();
});
afterEach(cleanup);

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}
function submit() {
  fireEvent.click(screen.getByRole("button", { name: /저장/ }));
}

describe("SettingsForm (spec 0007 D-5, R-1, R-12)", () => {
  it("D-5: 패널은 Model·Tools·Context·Memory 넷이다 (Policy 패널은 없다)", () => {
    render(<SettingsForm {...PROPS} />);
    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(headings).toEqual(["Model", "Tools", "Context", "Memory"]);
    expect(screen.queryByText(/Policy/i)).toBeNull();
  });

  it("현재 정의로 채워진다 (목록은 한 줄에 하나, MCP 는 이름 transport ref)", () => {
    render(<SettingsForm {...PROPS} />);
    expect(screen.getByLabelText<HTMLInputElement>("모델 id").value).toBe("old-model");
    expect(screen.getByLabelText<HTMLTextAreaElement>("도구 이름").value).toBe("search\nclock");
    expect(screen.getByLabelText<HTMLTextAreaElement>("MCP 서버").value).toBe("builtin stdio builtin");
    expect(screen.getByLabelText<HTMLInputElement>("컨텍스트 예산(토큰)").value).toBe("4096");
    expect(screen.getByLabelText<HTMLTextAreaElement>("Knowledge 이름").value).toBe("faq");
    expect(screen.getByLabelText<HTMLInputElement>("검색 상위 k").value).toBe("3");
    expect(screen.getByLabelText<HTMLInputElement>("Memory 켜기").checked).toBe(true);
    expect(screen.getByText("v3")).toBeTruthy();
  });

  it("null 칸은 빈 칸으로 채운다", () => {
    render(<SettingsForm {...PROPS} modelId="" contextBudgetTokens={null} knowledgeTopK={null} memoryEnabled={false} />);
    expect(screen.getByLabelText<HTMLInputElement>("컨텍스트 예산(토큰)").value).toBe("");
    expect(screen.getByLabelText<HTMLInputElement>("검색 상위 k").value).toBe("");
    expect(screen.getByLabelText<HTMLInputElement>("Memory 켜기").checked).toBe(false);
  });

  it("D-5: 네 패널의 값이 액션 하나의 한 번 호출로 모인다 (다른 액션은 불리지 않는다)", async () => {
    updateAgentSettingsAction.mockResolvedValue({ ok: true, agentId: AGENT_ID, version: 4 });
    render(<SettingsForm {...PROPS} />);

    fill("모델 id", "new-model");
    fill("도구 이름", "clock\ncalculator");
    fill("MCP 서버", "builtin stdio builtin\nremote http gw");
    fill("컨텍스트 예산(토큰)", "2048");
    fill("Knowledge 이름", "handbook");
    fill("검색 상위 k", "7");
    fireEvent.click(screen.getByLabelText("Memory 켜기"));
    submit();

    await waitFor(() => expect(updateAgentSettingsAction).toHaveBeenCalledTimes(1));
    expect(updateAgentSettingsAction).toHaveBeenCalledWith(
      AGENT_ID,
      "new-model",
      "clock\ncalculator",
      "builtin stdio builtin\nremote http gw",
      "2048",
      "handbook",
      "7",
      "false",
    );
    expect(updateAgentAction).not.toHaveBeenCalled();
    expect(createAgentAction).not.toHaveBeenCalled();
  });

  it("R-1: 성공하면 새 버전 번호를 말한다", async () => {
    updateAgentSettingsAction.mockResolvedValue({ ok: true, agentId: AGENT_ID, version: 4 });
    render(<SettingsForm {...PROPS} />);
    submit();

    const status = await screen.findByRole("status");
    expect(status.textContent).toContain("v4");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("실패하면 폼 위 alert 로 문장을 보이고 입력을 지우지 않는다", async () => {
    updateAgentSettingsAction.mockResolvedValue({ ok: false, message: "도구 이름이 중복되었습니다" });
    render(<SettingsForm {...PROPS} />);
    fill("도구 이름", "a\na");
    submit();

    expect((await screen.findByRole("alert")).textContent).toContain("도구 이름이 중복되었습니다");
    expect(screen.getByLabelText<HTMLTextAreaElement>("도구 이름").value).toBe("a\na");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("액션이 던져도 던진 문구를 보이지 않는다", async () => {
    updateAgentSettingsAction.mockRejectedValue(new Error("secret-internal-detail"));
    render(<SettingsForm {...PROPS} />);
    submit();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("저장에 실패했습니다");
    expect(document.body.innerHTML).not.toContain("secret-internal-detail");
  });

  it("R-12: 저장 자리에 새 버전이 만들어진다는 문장이 있다", () => {
    render(<SettingsForm {...PROPS} />);
    const note = screen.getByTestId("save-note").textContent ?? "";
    expect(note).toContain("새 버전이 만들어지고");
    expect(note).toContain("돌고 있는 Run 은 이전 버전을 계속 씁니다");
  });

  it("MCP 칸에는 자격증명·절대 URL 을 넣지 않는다는 안내가 있고, 키/비밀 입력칸은 없다", () => {
    render(<SettingsForm {...PROPS} />);
    expect(screen.getByTestId("mcp-hint").textContent).toContain("절대 URL");
    expect(document.querySelector("input[type=password]")).toBeNull();
    expect(screen.queryByLabelText(/키|토큰 값|비밀|URL 주소|api key/i)).toBeNull();
  });

  it("없는 이름 경고를 만들지 않는다 (api 가 생성 시 존재를 검증하지 않는다)", () => {
    render(<SettingsForm {...PROPS} tools={["no-such-tool"]} />);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText(/존재하지 않|찾을 수 없/)).toBeNull();
  });

  it("패널에 없는 칸(프롬프트·실행 정책)을 바꾸지 않는다고 말하고 그 편집 칸은 없다", () => {
    render(<SettingsForm {...PROPS} />);
    expect(screen.getByTestId("preserved-note").textContent).toContain("시스템 프롬프트");
    expect(screen.queryByLabelText(/timeout|max_steps|재시도|backoff/i)).toBeNull();
  });
});
