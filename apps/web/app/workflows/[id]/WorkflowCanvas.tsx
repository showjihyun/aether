"use client";

import type { WorkflowResponse } from "@aether/sdk";
import {
  Background,
  Controls,
  Handle,
  type Edge as FlowEdge,
  type Node as FlowNode,
  type NodeProps,
  Position,
  ReactFlow,
} from "@xyflow/react";
// 기본 테마(`dist/style.css`)는 쓰지 않습니다 - 색·선폭은 globals.css 가 `--xy-*` 를 토큰으로 덮습니다.
import "@xyflow/react/dist/base.css";

import { NODE_KIND_ICON, type NodeKind } from "@/components/NodeKindIcon";
import { layoutGraph } from "@/lib/workflowLayout";

type ApiNode = WorkflowResponse["nodes"][number];
type ApiEdge = WorkflowResponse["edges"][number];

const CARD_WIDTH = 192;
const CARD_HEIGHT = 64;

type CardData = { id: string; kind: NodeKind };

/** 모든 종류가 같은 카드입니다(DESIGN 6절) - 뜻은 아이콘과 **종류 이름 + 노드 id** 가 전달합니다. */
function WorkflowNodeCard({ data }: NodeProps<FlowNode<CardData>>) {
  const Icon = NODE_KIND_ICON[data.kind];
  return (
    <div
      data-slot="workflow-node"
      className="flex w-48 items-center gap-3 rounded-lg border bg-card px-3 py-2 text-card-foreground"
    >
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <Icon aria-hidden="true" className="size-4 shrink-0" />
      <div className="flex min-w-0 flex-col">
        <span className="text-xs text-muted-foreground">{data.kind}</span>
        <span className="truncate font-mono text-xs">{data.id}</span>
      </div>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}

const nodeTypes = { workflow: WorkflowNodeCard };

/**
 * 넘겨받은 노드·간선만 그립니다. 이 컴포넌트는 SDK 를 부르지 않고 아무것도 저장하지 않습니다 -
 * 배치는 매번 `layoutGraph` 가 계산합니다(spec 0007 D-9). 끌기·연결·선택은 꺼져 있습니다(P5-6).
 */
export function WorkflowCanvas({ nodes, edges }: { nodes: ApiNode[]; edges: ApiEdge[] }) {
  const positions = layoutGraph(nodes, edges);

  const flowNodes: FlowNode<CardData>[] = nodes.map((node) => ({
    id: node.id,
    type: "workflow",
    position: positions[node.id]!,
    data: { id: node.id, kind: node.kind },
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    // jsdom 처럼 측정이 없는 곳에서도 간선이 붙도록 핸들 위치를 알려 줍니다(SSR 용 속성).
    handles: [
      { type: "target", position: Position.Left, x: 0, y: CARD_HEIGHT / 2, width: 1, height: 1 },
      { type: "source", position: Position.Right, x: CARD_WIDTH, y: CARD_HEIGHT / 2, width: 1, height: 1 },
    ],
  }));

  const flowEdges: FlowEdge[] = edges.map((edge, index) => ({
    // 응답에 간선 식별자가 없습니다(C-7) - 화면 안의 키일 뿐이고 저장되지 않습니다.
    id: `e${index}:${edge.source}->${edge.target}`,
    source: edge.source,
    target: edge.target,
    label: edge.label ?? undefined,
  }));

  return (
    <div className="h-[32rem] w-full rounded-lg border">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        fitView
        minZoom={0.2}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
