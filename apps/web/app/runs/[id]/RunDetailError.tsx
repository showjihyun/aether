import { DetailError } from "@/components/DetailError";

/** `/runs/{id}` 의 오류. 모양과 404 분기는 `DetailError` 가 소유합니다 — `/knowledge/{id}` 가
 * 같은 상황(없는 id)을 만나 공용으로 올렸습니다(MVP-2c 리뷰 2026-10-18). 문구는 그대로입니다. */
export function RunDetailError({ error }: { error: unknown }) {
  return (
    <DetailError
      error={error}
      notFoundTitle="Run 을 찾을 수 없습니다"
      notFoundAction="목록에서 다른 Run 을 고르세요."
      errorTitle="Run 을 불러오지 못했습니다"
      backLabel="Run 목록으로"
      backHref="/runs"
    />
  );
}
