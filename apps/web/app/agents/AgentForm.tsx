"use client";

import { CircleAlert, CircleCheck } from "lucide-react";
import Link from "next/link";
import { useId, useState, type FormEvent } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

import { createAgentAction, updateAgentAction } from "./actions";

type Props =
  | { mode: "create" }
  | {
      mode: "edit";
      agentId: string;
      name: string;
      version: number;
      systemPrompt: string;
      modelId: string;
    };

/**
 * 저장 자리에서 하는 말(spec 0007 R-12, 2.8). 사용자가 "고쳤는데 돌던 것이 안 바뀐다" 를
 * 놀라움으로 만나지 않게 합니다.
 */
const NOTE_EDIT =
  "저장하면 새 버전이 만들어지고, 돌고 있는 Run 은 이전 버전을 계속 씁니다.";
const NOTE_CREATE =
  "저장하면 첫 버전(v1)이 만들어집니다. 이후 고칠 때마다 새 버전이 만들어지고, 돌고 있는 Run 은 이전 버전을 계속 씁니다.";

const SAVE_THREW = "저장에 실패했습니다. 잠시 뒤 다시 시도하고, 계속되면 web 로그를 보세요.";

/**
 * Agent 생성·수정 폼(P5-4 - Phase 5 의 첫 쓰기 경로).
 *
 * 입력 검증은 **서버 액션이** 합니다 - 이 폼은 브라우저 검증(`required` 등)을 두지 않아 실패
 * 문장의 출처가 하나입니다. 실패는 **폼 위 alert** 로, 성공은 status 로 보이고, 실패해도 입력은
 * 지우지 않습니다(고친 글을 잃지 않습니다). 액션의 반환 문장은 텍스트로만 그립니다.
 */
export function AgentForm(props: Props) {
  const editing = props.mode === "edit";
  const ids = { name: useId(), prompt: useId(), model: useId() };

  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState(editing ? props.systemPrompt : "");
  const [model, setModel] = useState(editing ? props.modelId : "");
  const [version, setVersion] = useState(editing ? props.version : null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<{ agentId: string; version: number } | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    setSaved(null);

    let result;
    try {
      result = editing
        ? await updateAgentAction(props.agentId, prompt, model)
        : await createAgentAction(name, prompt, model);
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
    setSaved({ agentId: result.agentId, version: result.version });
  }

  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">{editing ? props.name : "새 Agent"}</h2>
        {version !== null ? <Badge variant="outline">{`v${version}`}</Badge> : null}
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

      {saved ? (
        <Alert role="status">
          <CircleCheck aria-hidden="true" />
          <AlertTitle>{`저장했습니다 - v${saved.version}`}</AlertTitle>
          <AlertDescription>
            <div className="flex gap-2">
              <Link href="/agents" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
                Agent 목록으로
              </Link>
              <Link
                href={`/agents/${saved.agentId}/chat`}
                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              >
                대화 열기
              </Link>
            </div>
          </AlertDescription>
        </Alert>
      ) : null}

      <form onSubmit={(event) => void onSubmit(event)} noValidate className="flex flex-col gap-4">
        {!editing ? (
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
              이름은 Agent 마다 하나이고, 만든 뒤에는 고칠 수 없습니다.
            </p>
          </div>
        ) : null}

        <div className="flex flex-col gap-2">
          <Label htmlFor={ids.prompt}>시스템 프롬프트</Label>
          <Textarea
            id={ids.prompt}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={10}
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor={ids.model}>모델 id</Label>
          <Input
            id={ids.model}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            autoComplete="off"
          />
          <p className="text-xs text-muted-foreground">비워 두면 배포 설정의 모델을 씁니다.</p>
        </div>

        <div className="flex flex-col gap-2">
          <p data-testid="save-note" className="text-xs text-muted-foreground">
            {editing ? NOTE_EDIT : NOTE_CREATE}
          </p>
          <div className="flex gap-2">
            <Button type="submit" disabled={saving}>
              {saving ? "저장 중..." : "저장"}
            </Button>
            <Link href="/agents" className={cn(buttonVariants({ variant: "outline" }))}>
              취소
            </Link>
          </div>
        </div>
      </form>
    </div>
  );
}
