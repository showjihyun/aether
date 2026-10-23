// @vitest-environment node
import { AetherHttpError } from "@aether/sdk";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

interface SentGraph {
  name: string;
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
}
const createWorkflow = vi.fn<(body: SentGraph) => Promise<unknown>>();
const createClient = vi.fn<(options: { baseUrl: string; apiKey?: string }) => void>();
// `AetherHttpError` 는 실제 클래스를 통과시킵니다 - 액션의 `instanceof` 분기가 실제 SDK 오류에서도 성립해야 합니다.
vi.mock("@aether/sdk", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@aether/sdk")>()),
  createClient: (options: { baseUrl: string; apiKey?: string }) => {
    createClient(options);
    return { createWorkflow };
  },
}));

import { createWorkflowAction } from "./actions";

// 명백한 가짜 키와 가짜 내부 주소입니다.
const KEY = "aeth_test_not_a_real_key_0123456789";
const INTERNAL = "http://api.internal.invalid:8000";
const WORKFLOW_ID = "0198a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b";

const GRAPH = {
  nodes: [
    { id: "start-1", kind: "START" },
    { id: "end-1", kind: "END" },
  ],
  edges: [{ source: "start-1", target: "end-1" }],
};
const json = (value: unknown) => JSON.stringify(value);

function httpError(status: number, body?: unknown) {
  return new AetherHttpError(
    `aether-sdk: POST ${INTERNAL}/workflows failed with status ${status} upstream-body-secret`,
    status,
    "x",
    body,
  );
}

beforeEach(() => {
  createWorkflow.mockReset();
  createClient.mockClear();
  vi.stubEnv("AETHER_API_KEY", KEY);
  vi.stubEnv("AETHER_API_URL", INTERNAL);
});
afterEach(() => {
  vi.unstubAllEnvs();
});

describe("createWorkflowAction - 보내는 것 (spec 0007 R-2, D-2, D-9; DESIGN 7.3)", () => {
  it("R-2: 키를 SDK 에 넘기고, web 이 조립한 본문으로 createWorkflow 를 부른다", async () => {
    createWorkflow.mockResolvedValue({ id: WORKFLOW_ID, name: "n", current_version: 1 });

    const result = await createWorkflowAction("  triage  ", json(GRAPH));

    expect(createClient).toHaveBeenCalledWith({ baseUrl: INTERNAL, apiKey: KEY });
    expect(createWorkflow).toHaveBeenCalledWith({
      name: "triage",
      nodes: [
        { id: "start-1", kind: "START" },
        { id: "end-1", kind: "END" },
      ],
      edges: [{ source: "start-1", target: "end-1" }],
    });
    expect(result).toEqual({ ok: true, workflowId: WORKFLOW_ID, version: 1 });
  });

  it("D-9: 좌표 키가 브라우저 JSON 에 있어도 SDK 로 가는 본문에는 없다", async () => {
    createWorkflow.mockResolvedValue({ id: WORKFLOW_ID, name: "n", current_version: 1 });
    const withCoordinates = {
      nodes: [
        { id: "start-1", kind: "START", x: 10, y: 20, position: { x: 1, y: 2 } },
        { id: "end-1", kind: "END", positionAbsolute: { x: 3, y: 4 }, agent_id: "smuggled" },
      ],
      edges: [{ source: "start-1", target: "end-1", id: "e0", sourceHandle: "h" }],
    };

    await createWorkflowAction("w", json(withCoordinates));

    const sent = createWorkflow.mock.calls[0]![0];
    expect(Object.keys(sent.nodes[0]!).sort()).toEqual(["id", "kind"]);
    expect(Object.keys(sent.nodes[1]!).sort()).toEqual(["id", "kind"]);
    expect(Object.keys(sent.edges[0]!).sort()).toEqual(["source", "target"]);
    expect(JSON.stringify(sent)).not.toMatch(/position|"x"|"y"|sourceHandle/);
  });

  it("간선 label 은 문자열이면 보존한다(조건 분기가 쓴다)", async () => {
    createWorkflow.mockResolvedValue({ id: WORKFLOW_ID, name: "n", current_version: 1 });
    const graph = { ...GRAPH, edges: [{ source: "start-1", target: "end-1", label: "true" }] };

    await createWorkflowAction("w", json(graph));

    expect(createWorkflow.mock.calls[0]![0].edges).toEqual([
      { source: "start-1", target: "end-1", label: "true" },
    ]);
  });
});

describe("createWorkflowAction - 입력 검증은 SDK 앞에서 (spec 0007 D-2; DESIGN 7.3)", () => {
  const bad: Array<[string, unknown, unknown]> = [
    ["이름이 문자열이 아님", 42, json(GRAPH)],
    ["이름이 빔", "   ", json(GRAPH)],
    ["이름이 100자 초과", "a".repeat(101), json(GRAPH)],
    ["graphJson 이 문자열이 아님", "w", GRAPH],
    ["graphJson 이 빔", "w", ""],
    ["graphJson 이 JSON 이 아님", "w", "{not json"],
    ["graphJson 이 길이 상한 초과", "w", " ".repeat(200_001)],
    ["최상위가 배열", "w", "[]"],
    ["nodes 가 배열이 아님", "w", json({ nodes: {}, edges: [] })],
    ["edges 가 없음", "w", json({ nodes: GRAPH.nodes })],
    ["노드 id 가 모양을 어김(경로 조각)", "w", json({ nodes: [{ id: "../x", kind: "START" }], edges: [] })],
    ["노드 id 가 129자", "w", json({ nodes: [{ id: "a".repeat(129), kind: "START" }], edges: [] })],
    ["노드 id 가 문자열이 아님", "w", json({ nodes: [{ id: 1, kind: "START" }], edges: [] })],
    ["kind 가 열거형이 아님", "w", json({ nodes: [{ id: "a", kind: "SHELL" }], edges: [] })],
    ["kind 가 소문자", "w", json({ nodes: [{ id: "a", kind: "start" }], edges: [] })],
    ["노드가 객체가 아님", "w", json({ nodes: ["a"], edges: [] })],
    [
      "간선 source 가 그래프에 없는 노드",
      "w",
      json({ nodes: GRAPH.nodes, edges: [{ source: "ghost", target: "end-1" }] }),
    ],
    [
      "간선 target 이 그래프에 없는 노드",
      "w",
      json({ nodes: GRAPH.nodes, edges: [{ source: "start-1", target: "ghost" }] }),
    ],
    [
      "간선 label 이 문자열이 아님",
      "w",
      json({ nodes: GRAPH.nodes, edges: [{ source: "start-1", target: "end-1", label: 1 }] }),
    ],
    [
      "노드가 201개",
      "w",
      json({ nodes: Array.from({ length: 201 }, (_, i) => ({ id: `n${i}`, kind: "AGENT" })), edges: [] }),
    ],
    [
      "간선이 401개",
      "w",
      json({
        nodes: GRAPH.nodes,
        edges: Array.from({ length: 401 }, () => ({ source: "start-1", target: "end-1" })),
      }),
    ],
  ];

  it.each(bad)("D-2: %s -> SDK 도 createClient 도 부르지 않고 문장으로 돌려준다", async (_label, name, graph) => {
    const result = await createWorkflowAction(name as string, graph as string);

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.message.length).toBeGreaterThan(0);
    expect(createClient).not.toHaveBeenCalled();
    expect(createWorkflow).not.toHaveBeenCalled();
  });

  it("노드 id 가 중복이어도 액션은 막지 않는다 - 그 판정은 api 의 duplicate_node_id 몫이다", async () => {
    createWorkflow.mockRejectedValue(
      httpError(400, {
        detail: "invalid_workflow_graph",
        violations: [{ reason: "duplicate_node_id", node_id: "a" }],
      }),
    );

    const result = await createWorkflowAction(
      "w",
      json({ nodes: [{ id: "a", kind: "START" }, { id: "a", kind: "END" }], edges: [] }),
    );

    expect(createWorkflow).toHaveBeenCalledTimes(1);
    expect(result.ok).toBe(false);
  });

  it("api 키가 없으면 createWorkflow 를 부르지 않고 주입 방법을 말한다", async () => {
    vi.stubEnv("AETHER_API_KEY", "  ");

    const result = await createWorkflowAction("w", json(GRAPH));

    expect(result.ok).toBe(false);
    expect(!result.ok && result.message).toContain("AETHER_WEB_API_KEY");
    expect(createWorkflow).not.toHaveBeenCalled();
  });
});

describe("createWorkflowAction - 거부와 실패 (spec 0007 R-4, C-7; DESIGN 6·7.2절)", () => {
  it("R-4: 400 invalid_workflow_graph -> 위반 목록(reason, nodeId)을 돌려준다. 던지지 않는다", async () => {
    createWorkflow.mockRejectedValue(
      httpError(400, {
        detail: "invalid_workflow_graph",
        violations: [
          { reason: "agent_node_without_agent", node_id: "agent-1" },
          { reason: "no_start", node_id: null },
        ],
      }),
    );

    const result = await createWorkflowAction("w", json(GRAPH));

    expect(result).toMatchObject({
      ok: false,
      violations: [
        { reason: "agent_node_without_agent", nodeId: "agent-1" },
        { reason: "no_start", nodeId: null },
      ],
    });
    expect(!result.ok && result.message.length).toBeGreaterThan(0);
  });

  it("400 이어도 본문이 약속한 모양이 아니면 위반을 지어내지 않고 상태 코드를 말하는 일반 문장이다", async () => {
    const bodies: unknown[] = [
      undefined,
      "<html>",
      { detail: "other" },
      { detail: "invalid_workflow_graph" },
      { detail: "invalid_workflow_graph", violations: "x" },
    ];
    for (const body of bodies) {
      createWorkflow.mockRejectedValue(httpError(400, body));
      const result = await createWorkflowAction("w", json(GRAPH));
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.violations ?? []).toEqual([]);
        expect(result.message).toContain("400");
      }
    }
  });

  it("모양이 어긋난 위반 항목은 버린다(reason 이 문자열이 아니거나 node_id 가 문자열·null 이 아님)", async () => {
    createWorkflow.mockRejectedValue(
      httpError(400, {
        detail: "invalid_workflow_graph",
        violations: [
          { reason: 1, node_id: "a" },
          { reason: "orphan_node", node_id: 5 },
          "x",
          { reason: "orphan_node", node_id: "a" },
        ],
      }),
    );

    const result = await createWorkflowAction("w", json(GRAPH));

    expect(result).toMatchObject({ ok: false, violations: [{ reason: "orphan_node", nodeId: "a" }] });
  });

  it.each([401, 403])("%i -> 키를 다시 주입하라는 문장", async (status) => {
    createWorkflow.mockRejectedValue(httpError(status));
    const result = await createWorkflowAction("w", json(GRAPH));
    expect(result.ok).toBe(false);
    expect(!result.ok && result.message).toContain("키");
  });

  it("그 밖의 상태(422·500) -> 상태 코드만 보이고 본문은 보이지 않는다", async () => {
    for (const status of [422, 500]) {
      createWorkflow.mockRejectedValue(httpError(status, { detail: "upstream-body-secret" }));
      const result = await createWorkflowAction("w", json(GRAPH));
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.message).toContain(String(status));
        expect(result.violations ?? []).toEqual([]);
      }
    }
  });

  it("네트워크 오류 -> api 에 닿지 못했다는 문장", async () => {
    createWorkflow.mockRejectedValue(new TypeError("fetch failed"));
    const result = await createWorkflowAction("w", json(GRAPH));
    expect(result.ok).toBe(false);
    expect(!result.ok && result.message).toContain("닿지 못했");
  });

  it("어떤 실패 문장에도 키·내부 URL·업스트림 본문·SDK 원문이 없다", async () => {
    const failures: unknown[] = [
      httpError(400, { detail: "invalid_workflow_graph", violations: [] }),
      httpError(401),
      httpError(403),
      httpError(422, { detail: "upstream-body-secret" }),
      httpError(500),
      new TypeError(`fetch failed ${INTERNAL} ${KEY}`),
    ];
    for (const failure of failures) {
      createWorkflow.mockRejectedValue(failure);
      const result = await createWorkflowAction("w", json(GRAPH));
      const text = JSON.stringify(result);
      expect(text).not.toContain(KEY);
      expect(text).not.toContain("internal.invalid");
      expect(text).not.toContain("upstream-body-secret");
      expect(text).not.toContain("aether-sdk");
    }
  });
});
