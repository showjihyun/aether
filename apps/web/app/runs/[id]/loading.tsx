import { Skeleton } from "@/components/ui/skeleton";

/** DESIGN.md 7절 로딩: 머리 카드와 탭 줄이 있는 자리에 같은 크기의 skeleton. */
export default function Loading() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true">
      <Skeleton className="h-32" />
      <Skeleton className="h-9 w-72" />
      <Skeleton className="h-24" />
    </div>
  );
}
