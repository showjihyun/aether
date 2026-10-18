/** DESIGN.md 6절 "도메인 → 표현 규약" 의 시간·ID 표기. 순수 함수입니다. */

export const EMPTY_CELL = "—";

/** ID 는 앞 8자 + `…`. */
export function shortId(id: string): string {
  return `${id.slice(0, 8)}…`;
}

/** 상대 시간(`3분 전`). 절대 시간은 호출하는 쪽이 `title` 에 ISO 로 둡니다. */
export function formatRelative(iso: string, now: Date): string {
  const seconds = Math.max(0, Math.floor((now.getTime() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "방금";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

/** 소요 시간(`1m 12s`). 시작하지 않았거나 끝나지 않았으면 대시. */
export function formatDuration(startedAt: string | null, finishedAt: string | null): string {
  if (!startedAt || !finishedAt) return EMPTY_CELL;
  const total = Math.max(
    0,
    Math.round((new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000),
  );
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}
