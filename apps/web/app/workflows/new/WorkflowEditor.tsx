"use client";

import {
  Background,
  Controls,
  Handle,
  type Connection,
  type Edge as FlowEdge,
  type Node as FlowNode,
  type NodeProps,
  Position,
  ReactFlow,
} from "@xyflow/react";
import { CircleAlert, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useId, useMemo, useState, type FormEvent } from "react";
// 기본 테마(`dist/style.css`)는 쓰지 않습니다 - 색·선폭은 globals.css 가 `--xy-*` 를 토큰으로 덮습니다.
import "@xyflow/react/dist/base.css";

import { NODE_KIND_ICON, type NodeKind } from "@/components/NodeKindIcon";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { layoutGraph } from "@/lib/workflowLayout";
import { violationSentence } from "@/lib/workflowViolations";

import { createWorkflowAction, type WorkflowViolation } from "../actions";
import { nextNodeId, serializeGraph, type EditorEdge, type EditorNode } from "./graph";

const KINDS = Object.keys(NODE_KIND_ICON) as NodeKind[];

const CARD_WIDTH = 192;
const CARD_HEIGHT = 64;

/**
 * 저장 자리에서 하는 말(spec 0007 D-8, R-12). "저장했는데 돌던 것이 안 바뀐다" 를 놀라움으로
 * 만나지 않게 합니다.
 */
const NOTE_SAVE =
  "저장하면 Workflow 가 Version 1 로 만들어지고, 이후 수정은 새 Version 을 만듭니다 — 돌고 있는 Run 은 이전 Version 을 계속 씁니다.";
// spec 0007 D-9, R-12: 좌표는 저장되지 않습니다.
const NOTE_LAYOUT = "배치는 자동이라 열 때마다 달라질 수 있습니다. 노드 위치는 저장되지 않습니다.";
const SAVE_THREW = "저장에 실패했습니다. 잠시 뒤 다시 시도하고, 계속되면 web 로그를 보세요.";

const SELECT_CLASS =
  "h-9 rounded-md border bg-background px-3 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-ring";

type CardData = {
  id: string;
  kind: NodeKind;
  sentences: string[];
  onDelete: (id: string) => void;
};

/** 모든 종류가 같은 카드입니다(DESIGN 6절) - 위반 문장은 **카드 위**에 붙습니다. */
function EditorNodeCard({ data }: NodeProps<FlowNode<CardData>>) {
  const Icon = NODE_KIND_ICON[data.kind];
  return (
    <div data-slot="workflow-node" data-node-id={data.id} className="relative w-48">
      {data.sentences.length > 0 ? (
        <div className="absolute bottom-full z-10 mb-1 flex w-48 flex-col gap-1">
          {data.sentences.map((sentence, index) => (
            <p
              key={index}
              data-slot="node-violation"
              className="rounded-md border bg-card px-2 py-1 text-xs text-destructive"
            >
              {sentence}
            </p>
          ))}
        </div>
      ) : null}
      <div className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2 text-card-foreground">
        <Handle type="target" position={Position.Left} />
        <Icon aria-hidden="true" className="size-4 shrink-0" />
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-xs text-muted-foreground">{data.kind}</span>
          <span className="truncate font-mono text-xs">{data.id}</span>
        </div>
        <button
          type="button"
          aria-label={`노드 ${data.id} 삭제`}
          className="nodrag nopan rounded-md p-1 text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
          onClick={() => data.onDelete(data.id)}
        >
          <X aria-hidden="true" className="size-4" />
        </button>
        <Handle type="source" position={Position.Right} />
      </div>
    </div>
  );
}

const nodeTypes = { workflow: EditorNodeCard };

/**
 * Workflow 편집기(P5-6) - 노드 추가·연결·삭제와 저장. 구조만 만듭니다: 종류별 설정 칸은 없습니다
 * (plan 0007 개정 4). 그래서 `AGENT` 같은 노드는 저장이 `400` 으로 거부되고 그 사유가 노드 위에 보입니다.
 *
 * - 좌표는 상태에 없습니다: 배치는 매번 `layoutGraph` 가 계산하고(D-9) 액션으로도 `localStorage` 로도
 *   가지 않습니다.
 * - 저장은 서버 액션 하나입니다. 실패(`400` 포함)해도 입력은 지우지 않습니다(7.2).
 * - 위반은 `node_id` 가 이 캔버스의 노드이면 그 카드 위에, 아니면 그래프 수준 자리(`alert`)에
 *   보입니다. 간선에는 붙이지 않습니다(응답에 간선 식별자가 없습니다, C-7).
 */
export function WorkflowEditor() {
  const router = useRouter();
  const ids = { name: useId(), kind: useId(), from: useId(), to: useId() };

  const [name, setName] = useState("");
  const [nodes, setNodes] = useState<EditorNode[]>([]);
  const [edges, setEdges] = useState<EditorEdge[]>([]);
  const [kind, setKind] = useState<NodeKind>(KINDS[0]!);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [violations, setViolations] = useState<WorkflowViolation[]>([]);

  function addNode() {
    setNodes((current) => [...current, { id: nextNodeId(current, kind), kind }]);
  }

  function deleteNode(id: string) {
    setNodes((current) => current.filter((node) => node.id !== id));
    setEdges((current) => current.filter((edge) => edge.source !== id && edge.target !== id));
    setFrom((current) => (current === id ? "" : current));
    setTo((current) => (current === id ? "" : current));
  }

  function addEdge(source: string, target: string) {
    setEdges((current) =>
      current.some((edge) => edge.source === source && edge.target === target)
        ? current
        : [...current, { source, target }],
    );
  }

  function removeEdge(source: string, target: string) {
    setEdges((current) => current.filter((edge) => !(edge.source === source && edge.target === target)));
  }

  function onConnect(connection: Connection) {
    if (connection.source && connection.target) addEdge(connection.source, connection.target);
  }

  const nodeIds = new Set(nodes.map((node) => node.id));
  const onCard = (v: WorkflowViolation) => v.nodeId !== null && nodeIds.has(v.nodeId);
  const graphLevel = violations.filter((v) => !onCard(v));

  const positions = useMemo(() => layoutGraph(nodes, edges), [nodes, edges]);

  const flowNodes: FlowNode<CardData>[] = nodes.map((node) => ({
    id: node.id,
    type: "workflow",
    position: positions[node.id]!,
    data: {
      id: node.id,
      kind: node.kind,
      sentences: violations
        .filter((v) => v.nodeId === node.id)
        .map((v) => violationSentence(v.reason)),
      onDelete: deleteNode,
    },
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    draggable: false,
    // jsdom 처럼 측정이 없는 곳에서도 간선이 붙도록 핸들 위치를 알려 줍니다(SSR 용 속성).
    handles: [
      { type: "target", position: Position.Left, x: 0, y: CARD_HEIGHT / 2, width: 1, height: 1 },
      { type: "source", position: Position.Right, x: CARD_WIDTH, y: CARD_HEIGHT / 2, width: 1, height: 1 },
    ],
  }));

  const flowEdges: FlowEdge[] = edges.map((edge, index) => ({
    // 화면 안의 키일 뿐입니다(C-7 - 간선 식별자는 저장되지도 응답에 있지도 않습니다).
    id: `e${index}:${edge.source}->${edge.target}`,
    source: edge.source,
    target: edge.target,
  }));

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    setViolations([]);

    let result;
    try {
      result = await createWorkflowAction(name, serializeGraph(nodes, edges));
    } catch {
      // 던진 오류의 문구는 보이지 않습니다(서버 내부 정보가 섞일 수 있습니다).
      setError(SAVE_THREW);
      setSaving(false);
      return;
    }
    setSaving(false);
    if (!result.ok) {
      setError(result.message);
      setViolations(result.violations ?? []);
      return;
    }
    router.push(`/workflows/${result.workflowId}`);
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">새 Workflow</h2>

      {error ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>저장하지 못했습니다</AlertTitle>
          <AlertDescription>
            <p>{error}</p>
          </AlertDescription>
        </Alert>
      ) : null}

      {graphLevel.length > 0 ? (
        <div
          role="alert"
          data-slot="graph-violations"
          className="flex flex-col gap-1 rounded-lg border bg-card px-4 py-3 text-sm text-destructive"
        >
          <p className="font-medium">그래프 전체에 대한 사유</p>
          <ul className="list-disc pl-5">
            {graphLevel.map((v, index) => (
              <li key={index}>{violationSentence(v.reason)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex flex-wrap items-end gap-6">
        <div className="flex items-end gap-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor={ids.kind}>노드 종류</Label>
            <select
              id={ids.kind}
              className={SELECT_CLASS}
              value={kind}
              onChange={(e) => setKind(e.target.value as NodeKind)}
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </div>
          <Button type="button" variant="outline" onClick={addNode}>
            노드 추가
          </Button>
        </div>

        <div className="flex items-end gap-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor={ids.from}>연결 시작</Label>
            <select
              id={ids.from}
              className={SELECT_CLASS}
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            >
              <option value="">선택</option>
              {nodes.map((node) => (
                <option key={node.id} value={node.id}>
                  {node.id}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor={ids.to}>연결 끝</Label>
            <select
              id={ids.to}
              className={SELECT_CLASS}
              value={to}
              onChange={(e) => setTo(e.target.value)}
            >
              <option value="">선택</option>
              {nodes.map((node) => (
                <option key={node.id} value={node.id}>
                  {node.id}
                </option>
              ))}
            </select>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={from === "" || to === ""}
            onClick={() => addEdge(from, to)}
          >
            연결
          </Button>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">{NOTE_LAYOUT}</p>
      <div className="h-[32rem] w-full rounded-lg border">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          nodesDraggable={false}
          elementsSelectable={false}
          onConnect={onConnect}
          fitView
          minZoom={0.2}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      {edges.length > 0 ? (
        <ul data-slot="edge-list" className="flex flex-col gap-1 text-sm">
          {edges.map((edge) => (
            <li key={`${edge.source}->${edge.target}`} className="flex items-center gap-2">
              <span className="font-mono text-xs">{`${edge.source} → ${edge.target}`}</span>
              <button
                type="button"
                aria-label={`${edge.source} → ${edge.target} 연결 끊기`}
                className="text-xs underline underline-offset-4"
                onClick={() => removeEdge(edge.source, edge.target)}
              >
                연결 끊기
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <form onSubmit={(event) => void onSubmit(event)} noValidate className="flex max-w-2xl flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor={ids.name}>이름</Label>
          <Input
            id={ids.name}
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={200}
            autoComplete="off"
          />
          <p className="text-xs text-muted-foreground">
            이름은 Workflow 마다 하나이고, 만든 뒤에는 고칠 수 없습니다.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <p data-testid="save-note" className="text-xs text-muted-foreground">
            {NOTE_SAVE}
          </p>
          <div>
            <Button type="submit" disabled={saving}>
              {saving ? "저장 중..." : "저장"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
