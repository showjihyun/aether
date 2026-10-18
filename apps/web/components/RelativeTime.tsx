import { EMPTY_CELL, formatRelative } from "@/lib/format";

/** DESIGN.md 6절: 상대 시간을 보이고 `title` 에 절대 시간(ISO). 서버에서 한 번 그립니다. */
export function RelativeTime({ iso }: { iso: string | null }) {
  if (!iso) return <>{EMPTY_CELL}</>;
  return (
    <time dateTime={iso} title={iso}>
      {formatRelative(iso, new Date())}
    </time>
  );
}
