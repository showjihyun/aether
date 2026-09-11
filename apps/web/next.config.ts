import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // AR-1: apps/web 은 packages/sdk 를 통해서만 apps/api 의 HTTP 계약을 압니다.
  // sdk 는 Phase 0 에 빌드 단계가 없으므로(main → ./src/index.ts) Next 가 소스를
  // 직접 트랜스파일해야 합니다.
  transpilePackages: ["@aether/sdk"],
  // infra/docker/web.Dockerfile 의 런타임 이미지가 필요로 하는 최소 산출물
  // (server.js + 추적된 node_modules)만 만듭니다(spec 0001 2.7, plan P0-5 순서 1).
  output: "standalone",
};

export default nextConfig;
