import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const createAgentAction = vi.fn<(name: string, prompt: string, model: string) => Promise<unknown>>();
const updateAgentAction = vi.fn<(id: string, prompt: string) => Promise<unknown>>();
vi.mock("./actions", () => ({
  createAgentAction: (name: string, prompt: string, model: string) =>
    createAgentAction(name, prompt, model),
  updateAgentAction: (id: string, prompt: string) => updateAgentAction(id, prompt),
}));

import { AgentForm } from "./AgentForm";

const AGENT_ID = "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b";
const EDIT = {
  mode: "edit" as const,
  agentId: AGENT_ID,
  name: "billing-helper",
  version: 3,
  systemPrompt: "old prompt",
};

beforeEach(() => {
  createAgentAction.mockReset();
  updateAgentAction.mockReset();
});
afterEach(cleanup);

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}
function submit() {
  fireEvent.click(screen.getByRole("button", { name: /저장|만들기/ }));
}

describe("AgentForm - 생성 (spec 0007 R-1)", () => {
  it("R-1: 제출하면 서버 액션을 그 인자(이름, 프롬프트, 모델 id)로 부른다", async () => {
    createAgentAction.mockResolvedValue({ ok: true, agentId: AGENT_ID, version: 1 });
    render(<AgentForm mode="create" />);

    fill("이름", "billing-helper");
    fill("시스템 프롬프트", "당신은 도우미입니다.");
    fill("모델 id", "gpt-x");
    submit();

    await waitFor(() => expect(createAgentAction).toHaveBeenCalledTimes(1));
    expect(createAgentAction).toHaveBeenCalledWith("billing-helper", "당신은 도우미입니다.", "gpt-x");
    expect(updateAgentAction).not.toHaveBeenCalled();
  });

  it("R-1: 성공하면 v1 로 저장했다고 말하고 목록·대화로 가는 길을 준다", async () => {
    createAgentAction.mockResolvedValue({ ok: true, agentId: AGENT_ID, version: 1 });
    render(<AgentForm mode="create" />);
    fill("이름", "a");
    fill("시스템 프롬프트", "p");
    submit();

    const status = await screen.findByRole("status");
    expect(status.textContent).toContain("v1");
    expect(screen.getByRole("link", { name: "Agent 목록으로" }).getAttribute("href")).toBe("/agents");
    expect(screen.getByRole("link", { name: "대화 열기" }).getAttribute("href")).toBe(
      `/agents/${AGENT_ID}/chat`,
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("R-12: 저장 자리에 새 버전이 만들어진다는 문장이 있다", () => {
    render(<AgentForm mode="create" />);
    const note = screen.getByTestId("save-note").textContent ?? "";
    expect(note).toContain("새 버전이 만들어지고");
    expect(note).toContain("돌고 있는 Run 은 이전 버전을 계속 씁니다");
  });
});

describe("AgentForm - 수정 (spec 0007 R-1, R-12, D-8)", () => {
  it("R-1: 현재 정의로 채워지고 이름은 고칠 수 없다 (name 은 불변 - 입력칸이 없다)", () => {
    render(<AgentForm {...EDIT} />);

    expect(screen.getByLabelText<HTMLTextAreaElement>("시스템 프롬프트").value).toBe("old prompt");
    // D-5: model.id 는 설정의 Model 패널이 한 곳에서 고칩니다 - 수정 폼에는 그 칸이 없습니다.
    expect(screen.queryByLabelText("모델 id")).toBeNull();
    expect(screen.queryByLabelText("이름")).toBeNull();
    expect(screen.getByText("billing-helper")).toBeTruthy();
    expect(screen.getByText("v3")).toBeTruthy();
  });

  it("R-1: 제출하면 updateAgentAction 을 (agentId, 프롬프트) 로만 부른다 - 모델 인자가 없다", async () => {
    updateAgentAction.mockResolvedValue({ ok: true, agentId: AGENT_ID, version: 4 });
    render(<AgentForm {...EDIT} />);

    fill("시스템 프롬프트", "new prompt");
    submit();

    await waitFor(() => expect(updateAgentAction).toHaveBeenCalledTimes(1));
    expect(updateAgentAction).toHaveBeenCalledWith(AGENT_ID, "new prompt");
    expect(createAgentAction).not.toHaveBeenCalled();
    expect((await screen.findByRole("status")).textContent).toContain("v4");
  });

  it("R-12: 저장 자리에 새 버전이 만들어진다는 문장이 있다", () => {
    render(<AgentForm {...EDIT} />);
    const note = screen.getByTestId("save-note").textContent ?? "";
    expect(note).toContain("저장하면 새 버전이 만들어지고, 돌고 있는 Run 은 이전 버전을 계속 씁니다");
  });

  it("D-8 / 모양: 검증 실패·409·네트워크 오류는 각각 다른 문장을 폼 위 alert 로 보인다", async () => {
    const messages = [
      "시스템 프롬프트를 입력하세요.",
      "누군가 먼저 저장했습니다. 이 화면을 새로고침한 뒤 다시 고치세요.",
      "api 에 닿지 못했습니다. api 가 떠 있는지 확인한 뒤 다시 시도하세요.",
    ];
    const seen: string[] = [];
    for (const message of messages) {
      updateAgentAction.mockResolvedValue({ ok: false, message });
      render(<AgentForm {...EDIT} />);
      submit();
      const alert = await screen.findByRole("alert");
      seen.push(alert.textContent ?? "");
      expect(alert.textContent).toContain(message);
      // 폼 위: alert 가 form 보다 문서에서 앞에 있다.
      const form = document.querySelector("form")!;
      expect(alert.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(screen.queryByRole("status")).toBeNull();
      cleanup();
    }
    expect(new Set(seen).size).toBe(3);
  });

  it("D-8: 실패해도 입력은 지워지지 않는다 (고친 글을 잃지 않는다)", async () => {
    updateAgentAction.mockResolvedValue({ ok: false, message: "누군가 먼저 저장했습니다." });
    render(<AgentForm {...EDIT} />);
    fill("시스템 프롬프트", "내가 고친 글");
    submit();

    await screen.findByRole("alert");
    expect(screen.getByLabelText<HTMLTextAreaElement>("시스템 프롬프트").value).toBe("내가 고친 글");
  });

  it("실패 뒤 다시 제출해 성공하면 alert 는 사라진다", async () => {
    updateAgentAction.mockResolvedValueOnce({ ok: false, message: "x 실패" });
    updateAgentAction.mockResolvedValueOnce({ ok: true, agentId: AGENT_ID, version: 4 });
    render(<AgentForm {...EDIT} />);
    submit();
    await screen.findByRole("alert");
    submit();
    await screen.findByRole("status");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("서버 액션이 던져도 화면이 깨지지 않고 alert 를 보인다 (던진 문구는 보이지 않는다)", async () => {
    updateAgentAction.mockRejectedValue(new Error("Server Action not found upstream-body-secret"));
    render(<AgentForm {...EDIT} />);
    submit();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).not.toContain("upstream-body-secret");
  });

  it("제출 중에는 버튼이 비활성이다 (두 번 저장되지 않는다)", async () => {
    let resolve!: (value: unknown) => void;
    updateAgentAction.mockReturnValue(new Promise((r) => (resolve = r)));
    render(<AgentForm {...EDIT} />);
    submit();

    await waitFor(() =>
      expect(screen.getByRole<HTMLButtonElement>("button", { name: /저장/ }).disabled).toBe(true),
    );
    submit();
    expect(updateAgentAction).toHaveBeenCalledTimes(1);
    resolve({ ok: true, agentId: AGENT_ID, version: 4 });
    await screen.findByRole("status");
  });

  it("DESIGN 6절: 서버가 준 문장도 텍스트로 렌더된다", async () => {
    updateAgentAction.mockResolvedValue({ ok: false, message: "<img src=x onerror=alert(1)>" });
    render(<AgentForm {...EDIT} />);
    submit();
    await screen.findByRole("alert");
    expect(document.querySelector("img")).toBeNull();
  });
});
