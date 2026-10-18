import { AetherHttpError } from "@aether/sdk";
import { CircleAlert } from "lucide-react";
import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** 서버 컴포넌트가 쓸 api 키가 없을 때.
 *
 * 중계(브라우저 경로)는 이 경우 503 과 함께 "키를 주입하세요" 를 말합니다(`lib/relay.ts`).
 * 서버 경로가 같은 상황에서 401 을 그냥 오류로 그리면 "api 가 떠 있는지 확인" 이라는
 * **틀린 다음 행동**이 나옵니다 — 가장 흔한 개발 실수(키를 안 넣음)에 대해 그렇습니다.
 * 두 경로가 같은 말을 하게 둡니다(MVP-2p 리뷰 2026-10-18).
 */
export function MissingApiKey() {
  return (
    <Alert variant="destructive">
      <CircleAlert aria-hidden="true" />
      <AlertTitle>api 키가 없습니다</AlertTitle>
      <AlertDescription>
        <p>
          web 컨테이너에 api 키를 주입하세요 — <code className="font-mono text-xs">AETHER_WEB_API_KEY</code>
          (`infra/docker/.env.example` 참고). 발급은 api 컨테이너에서 한 번만 출력됩니다.
        </p>
      </AlertDescription>
    </Alert>
  );
}

/** DESIGN.md 7절 빈 결과: 가운데 정렬, `text-muted-foreground` 한 줄.
 *
 * 7절은 "다음 행동 `button` 하나" 도 요구하지만, 목록이 처음부터 빈 경우 갈 곳이
 * 없습니다 — 생성 화면이 MVP 범위에 없습니다(DESIGN 9절: 없는 것을 있을 것처럼 그리지
 * 않습니다). 그래서 첫 쪽에서는 한 줄만 보입니다. 반면 **커서 쪽이 비어 있는 경우**는
 * 막다른 길이므로 "처음부터 보기" 를 붙입니다. MVP-2a 리뷰 2026-10-18.
 */
export function ListEmpty({ message, restartHref }: { message: string; restartHref?: string }) {
  return (
    <div className="py-12 text-center">
      <p className="text-sm text-muted-foreground">{message}</p>
      {restartHref ? (
        <Link
          href={restartHref}
          className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-3")}
        >
          처음부터 보기
        </Link>
      ) : null}
    </div>
  );
}

/** DESIGN.md 7절·7.1 오류. 깨진 커서면 다음 행동은 "처음부터 보기", 아니면 새로고침 안내. */
export function ListError({
  message,
  restartHref,
  brokenCursor,
}: {
  message: string;
  restartHref: string;
  brokenCursor: boolean;
}) {
  return (
    <Alert variant="destructive">
      <CircleAlert aria-hidden="true" />
      <AlertTitle>목록을 불러오지 못했습니다</AlertTitle>
      <AlertDescription>
        {/* DESIGN 7: 메시지는 **사용자가 할 수 있는 일**을 말하고, 기술 세부는 접습니다.
            SDK 의 원문(`aether-sdk: GET /runs?cursor=… failed with status …`)을 그대로
            보이면 사용자가 할 수 있는 일이 아무것도 적혀 있지 않습니다. */}
        {brokenCursor ? (
          <>
            <p>이 쪽으로 가는 주소가 더 이상 유효하지 않습니다.</p>
            <Link href={restartHref} className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-2")}>
              처음부터 보기
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

/** DESIGN.md 7.1: `next_cursor` 가 없으면 버튼 자체가 없습니다.
 *
 * 라벨이 "다음 쪽" 인 이유: 이것은 **쪽 교체**입니다(`?cursor=` 로 서버가 다음 쪽을 다시
 * 그립니다). 앞 쪽에 이어 붙이지 않으므로 "더 보기" 는 하는 일과 다른 말이 됩니다.
 * 이어 붙이려면 클라이언트 상태가 필요하고, DESIGN 7.1 이 무한 스크롤을 거부한 이유
 * (스크롤 복원·키보드 접근성·"끝" 표시가 전부 새 결정)가 그대로 적용됩니다. 쪽 교체는
 * 링크이므로 뒤로 가기가 **이전 쪽**이 되고 새 규약이 필요하지 않습니다.
 * MVP-2a 리뷰 2026-10-18 — DESIGN 7.1 에 적었습니다.
 */
export function LoadMore({ basePath, nextCursor }: { basePath: string; nextCursor?: string | null }) {
  if (!nextCursor) return null;
  return (
    <div className="mt-4 flex justify-center">
      <Link
        href={`${basePath}?cursor=${encodeURIComponent(nextCursor)}`}
        className={buttonVariants({ variant: "outline" })}
      >
        다음 쪽
      </Link>
    </div>
  );
}

/** DESIGN.md 7절 로딩: 실제 표와 같은 열 수·행 높이의 skeleton. */
export function TableSkeleton({ columns, rows = 5 }: { columns: number; rows?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-busy="true">
      {Array.from({ length: rows }, (_, row) => (
        <div key={row} className="grid gap-4" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
          {Array.from({ length: columns }, (_, col) => (
            <Skeleton key={col} className="h-8" />
          ))}
        </div>
      ))}
    </div>
  );
}

/** DESIGN.md 7.1: 깨진 커서는 `422` 입니다.
 *
 * 상태는 SDK 의 **필드**에서 읽습니다. 사람이 읽는 메시지를 정규식으로 파싱하면 SDK 가
 * 문구를 바꾸는 순간 이 분기가 조용히 깨지고, 그 사실을 아무 테스트도 잡지 못합니다
 * (화면 테스트가 같은 문자열을 손으로 베껴 쓰게 되므로). MVP-2a 리뷰 2026-10-18.
 */
export function isBrokenCursor(error: unknown): boolean {
  return error instanceof AetherHttpError && error.status === 422;
}
