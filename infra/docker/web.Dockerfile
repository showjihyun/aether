# apps/web (Experience). 빌드 컨텍스트는 저장소 루트 — pnpm workspace 전체
# (apps/web, packages/sdk)가 필요합니다(spec 0001 2.7, plan P0-5 순서 1).
# API 없이 빌드가 성립해야 합니다: app/page.tsx 가 `export const dynamic =
# "force-dynamic"` 이라 빌드 시점에 api 를 부르지 않습니다(P0-3 plan 리뷰 F-4).

# 확인: Node 버전은 .nvmrc(24, 현재 LTS)와 맞춥니다.
ARG NODE_IMAGE=node:24-slim@sha256:2fe369e969550cde8e867afc3fe370b260140cab4a23d467074295b42163d553

FROM ${NODE_IMAGE} AS deps
WORKDIR /app
# 확인: pnpm 버전은 이 세션에서 로컬로 쓴 10.34.5 로 고정(root package.json 에
# packageManager 필드가 없어 corepack 이 자동으로 못 고릅니다).
RUN corepack enable && corepack prepare pnpm@10.34.5 --activate
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/sdk/package.json packages/sdk/package.json
RUN pnpm install --frozen-lockfile

FROM ${NODE_IMAGE} AS builder
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.34.5 --activate
COPY --from=deps /app /app
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm -F web run build
# `public/` 은 아직 없는 앱이라 COPY 대상이 없을 수 있습니다 — runner 단계의
# COPY 가 항상 성립하도록 빈 디렉터리라도 보장합니다.
RUN mkdir -p apps/web/public

FROM ${NODE_IMAGE} AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0
# node:24-slim 은 이미 non-root 사용자 `node`(uid/gid 1000)를 가지고 있습니다 —
# 새로 만들면 GID 충돌로 빌드가 실패합니다(관측: `groupadd: GID '1000' already exists`,
# exit 4). 그 사용자를 그대로 씁니다.

COPY --from=builder /app/apps/web/public ./apps/web/public
COPY --from=builder --chown=node:node /app/apps/web/.next/standalone ./
COPY --from=builder --chown=node:node /app/apps/web/.next/static ./apps/web/.next/static

ARG AETHER_VERSION=dev
ENV AETHER_VERSION=${AETHER_VERSION}

USER node

EXPOSE 3000

# Next standalone 서버가 뜬 뒤 `/` 를 node 의 전역 fetch 로 확인합니다(세션 계약).
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=10 \
    CMD ["node", "-e", "fetch('http://localhost:3000/').then((r) => process.exit(r.status === 200 ? 0 : 1)).catch(() => process.exit(1))"]

CMD ["node", "apps/web/server.js"]
