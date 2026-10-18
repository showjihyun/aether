import { AetherHttpError } from "@aether/sdk";
import { CircleAlert } from "lucide-react";
import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** DESIGN.md 7절 오류(상세 화면 판). 첫 문장이 할 수 있는 일이고 원문은 접힌 `details` 안입니다.
 * 분기는 상태 코드 **필드**로 합니다(문구를 파싱하지 않습니다). */
export function RunDetailError({ error }: { error: unknown }) {
  const notFound = error instanceof AetherHttpError && error.status === 404;
  const message = error instanceof Error ? error.message : String(error);

  return (
    <Alert variant="destructive">
      <CircleAlert aria-hidden="true" />
      <AlertTitle>{notFound ? "Run 을 찾을 수 없습니다" : "Run 을 불러오지 못했습니다"}</AlertTitle>
      <AlertDescription>
        {notFound ? (
          <>
            <p>목록에서 다른 Run 을 고르세요.</p>
            <Link
              href="/runs"
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-2")}
            >
              Run 목록으로
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
