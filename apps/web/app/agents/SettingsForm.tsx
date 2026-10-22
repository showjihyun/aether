"use client";

import { CircleAlert, CircleCheck } from "lucide-react";
import Link from "next/link";
import { useId, useState, type FormEvent, type ReactNode } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

import { updateAgentSettingsAction } from "./actions";

interface Props {
  agentId: string;
  name: string;
  version: number;
  modelId: string;
  tools: string[];
  mcpServers: { name: string; transport: "stdio" | "http"; ref: string }[];
  contextBudgetTokens: number | null;
  knowledge: string[];
  knowledgeTopK: number | null;
  memoryEnabled: boolean;
}

/** 저장 자리에서 하는 말(spec 0007 R-12, 2.8) - `AgentForm` 과 같은 문장입니다. */
const NOTE_EDIT = "저장하면 새 버전이 만들어지고, 돌고 있는 Run 은 이전 버전을 계속 씁니다.";
const SAVE_THREW = "저장에 실패했습니다. 잠시 뒤 다시 시도하고, 계속되면 web 로그를 보세요.";

function Panel({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h3>{title}</h3>
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">{children}</CardContent>
    </Card>
  );
}

/**
 * Agent 설정 패널 넷(P5-7, spec 0007 D-5) - Model·Tools·Context·Memory.
 *
 * 네 패널은 **하나의 저장**으로 모입니다(서버 액션 하나 = `PUT /agents/{id}` 하나 = 새 Version 하나).
 * 패널마다 저장하면 패널 수만큼 Version 이 생깁니다. Policy(도구 허용 목록)는 **여기 없습니다** -
 * 화면에서 넓히지 않고(R-11), 읽을 api 도 아직 없어 자리표시도 두지 않습니다(DESIGN 9절).
 * 입력 검증은 서버 액션이 합니다(`AgentForm` 과 같은 이유) - 실패해도 입력은 지우지 않습니다.
 */
export function SettingsForm(props: Props) {
  const ids = {
    model: useId(),
    tools: useId(),
    mcp: useId(),
    mcpHint: useId(),
    budget: useId(),
    knowledge: useId(),
    topK: useId(),
    memory: useId(),
  };

  const [model, setModel] = useState(props.modelId);
  const [tools, setTools] = useState(props.tools.join("\n"));
  const [mcp, setMcp] = useState(props.mcpServers.map((s) => `${s.name} ${s.transport} ${s.ref}`).join("\n"));
  const [budget, setBudget] = useState(props.contextBudgetTokens === null ? "" : String(props.contextBudgetTokens));
  const [knowledge, setKnowledge] = useState(props.knowledge.join("\n"));
  const [topK, setTopK] = useState(props.knowledgeTopK === null ? "" : String(props.knowledgeTopK));
  const [memory, setMemory] = useState(props.memoryEnabled);
  const [version, setVersion] = useState(props.version);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<number | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    setSaved(null);

    let result;
    try {
      result = await updateAgentSettingsAction(
        props.agentId,
        model,
        tools,
        mcp,
        budget,
        knowledge,
        topK,
        memory ? "true" : "false",
      );
    } catch {
      // 던진 오류의 문구는 보이지 않습니다(서버 내부 정보가 섞일 수 있습니다).
      setError(SAVE_THREW);
      setSaving(false);
      return;
    }
    setSaving(false);
    if (!result.ok) {
      setError(result.message);
      return;
    }
    setVersion(result.version);
    setSaved(result.version);
  }

  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">{props.name}</h2>
        <Badge variant="outline">{`v${version}`}</Badge>
      </div>

      {error ? (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>저장하지 못했습니다</AlertTitle>
          <AlertDescription>
            <p>{error}</p>
          </AlertDescription>
        </Alert>
      ) : null}

      {saved !== null ? (
        <Alert role="status">
          <CircleCheck aria-hidden="true" />
          <AlertTitle>{`저장했습니다 - v${saved}`}</AlertTitle>
        </Alert>
      ) : null}

      <form onSubmit={(event) => void onSubmit(event)} noValidate className="flex flex-col gap-4">
        <Panel title="Model" description="이 Agent 가 쓰는 모델입니다.">
          <div className="flex flex-col gap-2">
            <Label htmlFor={ids.model}>모델 id</Label>
            <Input id={ids.model} value={model} onChange={(e) => setModel(e.target.value)} autoComplete="off" />
            <p className="text-xs text-muted-foreground">비워 두면 배포 설정의 모델을 씁니다.</p>
          </div>
        </Panel>

        <Panel title="Tools" description="Agent 가 부를 수 있는 도구와 연결할 MCP 서버입니다.">
          <div className="flex flex-col gap-2">
            <Label htmlFor={ids.tools}>도구 이름</Label>
            <Textarea id={ids.tools} value={tools} onChange={(e) => setTools(e.target.value)} rows={4} />
            <p className="text-xs text-muted-foreground">한 줄에 하나, 같은 이름은 두 번 쓸 수 없습니다.</p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor={ids.mcp}>MCP 서버</Label>
            <Textarea
              id={ids.mcp}
              value={mcp}
              onChange={(e) => setMcp(e.target.value)}
              rows={3}
              aria-describedby={ids.mcpHint}
            />
            <p id={ids.mcpHint} data-testid="mcp-hint" className="text-xs text-muted-foreground">
              한 줄에 하나: 이름 transport(stdio 또는 http) ref. ref 는 배포 설정이 실제 명령·주소로 푸는
              키입니다 - 절대 URL 이나 자격증명을 넣지 마세요.
            </p>
          </div>
        </Panel>

        <Panel title="Context" description="모델을 부를 때마다 조립되는 입력의 크기와 Knowledge 입니다.">
          <div className="flex flex-col gap-2">
            <Label htmlFor={ids.budget}>컨텍스트 예산(토큰)</Label>
            <Input
              id={ids.budget}
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              inputMode="numeric"
              autoComplete="off"
            />
            <p className="text-xs text-muted-foreground">1 이상의 정수. 비워 두면 배포 설정의 예산을 씁니다.</p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor={ids.knowledge}>Knowledge 이름</Label>
            <Textarea
              id={ids.knowledge}
              value={knowledge}
              onChange={(e) => setKnowledge(e.target.value)}
              rows={3}
            />
            <p className="text-xs text-muted-foreground">검색할 Knowledge Set 의 이름, 한 줄에 하나입니다.</p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor={ids.topK}>검색 상위 k</Label>
            <Input
              id={ids.topK}
              value={topK}
              onChange={(e) => setTopK(e.target.value)}
              inputMode="numeric"
              autoComplete="off"
            />
            <p className="text-xs text-muted-foreground">1 이상의 정수. 비워 두면 기본값(5)을 씁니다.</p>
          </div>
        </Panel>

        <Panel title="Memory" description="성공한 실행의 답변을 다음 실행에 이어 줄지 정합니다.">
          <div className="flex items-center gap-2">
            <input
              id={ids.memory}
              type="checkbox"
              checked={memory}
              onChange={(e) => setMemory(e.target.checked)}
              className="size-4"
            />
            <Label htmlFor={ids.memory}>Memory 켜기</Label>
          </div>
        </Panel>

        <div className="flex flex-col gap-2">
          <p data-testid="preserved-note" className="text-xs text-muted-foreground">
            이 화면은 시스템 프롬프트와 실행 정책(제한 시간·최대 단계·재시도)을 바꾸지 않습니다 - 저장해도
            현재 값 그대로입니다.
          </p>
          <p data-testid="save-note" className="text-xs text-muted-foreground">
            {NOTE_EDIT}
          </p>
          <div className="flex gap-2">
            <Button type="submit" disabled={saving}>
              {saving ? "저장 중..." : "저장"}
            </Button>
            <Link href={`/agents/${props.agentId}/edit`} className={cn(buttonVariants({ variant: "outline" }))}>
              프롬프트 편집으로
            </Link>
          </div>
        </div>
      </form>
    </div>
  );
}
