import { TableSkeleton } from "@/components/ListStates";

/** DESIGN.md 7절 로딩: 노드 표와 같은 열 수(6)의 skeleton. */
export default function Loading() {
  return <TableSkeleton columns={6} />;
}
