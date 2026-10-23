import { Skeleton } from "@/components/ui/skeleton";

/** DESIGN.md 7절 로딩: 머리 한 줄과 캔버스와 같은 높이의 skeleton. */
export default function Loading() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true">
      <Skeleton className="h-6 w-64" />
      <Skeleton className="h-[32rem] w-full" />
    </div>
  );
}
