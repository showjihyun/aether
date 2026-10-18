import { relay } from "@/lib/relay";

// 중계 정책(허용 목록·키 주입·헤더 걸러내기)은 lib/relay.ts 에 있습니다.
export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ path: string[] }> };

async function handle(request: Request, { params }: Ctx): Promise<Response> {
  const { path } = await params;
  return relay(request, path);
}

export const GET = handle;
// 허용 목록 밖 메서드는 relay 가 405 로 끊습니다(업스트림을 부르지 않습니다).
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
