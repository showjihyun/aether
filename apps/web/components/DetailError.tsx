import { AetherHttpError } from "@aether/sdk";
import { CircleAlert } from "lucide-react";
import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** DESIGN.md 7절 오류(**하나를 열었을 때**의 판). 목록의 `ListError` 와 다른 점은 404 입니다.
 *
 * 분기는 상태 코드 **필드**로 합니다 — 문구를 파싱하지 않습니다(MVP-2a 리뷰 2026-10-18).
 * 404 는 "없다" 이고 다음 행동은 목록으로 돌아가기입니다. 일반 오류 문구("api 가 떠 있는지
 * 확인") 를 그 자리에 쓰면 **떠 있는 api** 에 대해 틀린 지시가 됩니다. `/runs/{id}` 가 먼저
 * 그렇게 했고, `/knowledge/{id}` 가 같은 상황을 만나 이 컴포넌트로 묶었습니다
 * (MVP-2c 리뷰 2026-10-18).
 */
export function DetailError({
  error,
  notFoundTitle,
  notFoundAction,
  errorTitle,
  backLabel,
  backHref,
}: {
  error: unknown;
  notFoundTitle: string;
  notFoundAction: string;
  errorTitle: string;
  backLabel: string;
  backHref: string;
}) {
  const notFound = error instanceof AetherHttpError && error.status === 404;
  const message = error instanceof Error ? error.message : String(error);

  return (
    <Alert variant="destructive">
      <CircleAlert aria-hidden="true" />
      <AlertTitle>{notFound ? notFoundTitle : errorTitle}</AlertTitle>
      <AlertDescription>
        {notFound ? (
          <>
            <p>{notFoundAction}</p>
            <Link
              href={backHref}
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-2")}
            >
              {backLabel}
            </Link>
          </>
        ) : (
          <p>api 가 떠 있는지 확인한 뒤 새로고침 하세요.</p>
        )}
        <details className="mt-2">
          <summary className="cursor-pointer text-xs">기술 정보</summary>
          <pre className="mt-1 whitespace-pre-wrap font-mono text-xs">{message}</pre>
        </details>
      </AlertDescription>
    </Alert>
  );
}
