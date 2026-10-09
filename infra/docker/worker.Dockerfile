# apps/worker (Data Plane). 빌드 컨텍스트는 저장소 루트입니다 — api.Dockerfile 과 같은 이유
# (spec 0001 2.7, plan P0-5 순서 1). `aether_api` 를 import 하지 않습니다(spec 2.6) —
# 이 이미지도 `apps/api` 소스를 담지만 그것은 uv workspace 설치의 부산물일 뿐,
# `aether_worker` 코드가 그것을 참조하지 않는다는 사실은 AR-7 계약(api-arch)이 판정합니다.
#
# spec 0003 2.3, D-8 (P2-5): 참조 Filesystem MCP Server(`@modelcontextprotocol/
# server-filesystem`, npm)를 **이미지 빌드 시점에** 넣습니다 — worker 가 stdio 로
# 붙는 대상은 이 프로세스가 직접 띄우는 서브프로세스이므로(spec 2.2, `shlex.split`
# 로 명령을 그대로 실행, spec 2.9) 같은 이미지 안에 Node 런타임과 그 패키지가
# 있어야 합니다. 실행 시점에 `npx` 로 내려받지 않습니다 — Air-Gapped 에서 동작하지
# 않고 공급망 관점에서도 매 실행마다 외부 코드를 받는 것은 받을 수 없습니다.
# 버전은 여기 정확히 고정합니다(`2026.8.31`, 2026-09-29 확인) — 갱신은 Dependabot
# 밖이라 사람이 주기적으로 봅니다(spec C-5, docs 초안은 구현자 보고 참고).
FROM node:26-slim@sha256:ec7758ee051e457b468b32bde57b0879010b325bb9862718e9615225ce4aaae1 AS mcp-filesystem

RUN npm install --global --no-fund --no-audit @modelcontextprotocol/server-filesystem@2026.8.31

FROM ghcr.io/astral-sh/uv:0.12.24@sha256:3af4716e991d6956a41e573eab705d0ee08500cd829ed30293eb8472f372c65a AS uv

FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS runtime

COPY --from=uv /uv /uvx /usr/local/bin/

# Node 26 바이너리가 libatomic.so.1 에 동적으로 링크합니다(Node 22 는 그렇지 않았음) —
# 이 베이스에는 없어 바이너리만 복사한 Node 가 "libatomic.so.1: cannot open shared
# object file" 로 즉시 죽습니다(실측, smoke 단계). 패키지만 넣고 바로 지웁니다.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# D-8: Node 런타임 실행 파일과, npm 전역 설치가 만든 패키지 트리(그 패키지 자신의
# `node_modules` 안에 `@modelcontextprotocol/sdk` 등 전이 의존까지 포함)만 옮깁니다
# — 베이스 이미지가 함께 담은 `npm`/`corepack` 은 옮기지 않아 이미지가 커지지
# 않습니다. `mcp-server-filesystem` bin 심볼릭 링크(`/usr/local/bin/` 안, 상대
# 경로로 `../lib/node_modules/...` 를 가리킴, 실측 확인)는 Node 의 ESM 로더가
# 심볼릭 링크 경로 자체를 import 기준(base)으로 삼아 전이 의존 해석에 실패하는
# 경우가 있어(실측, `ERR_MODULE_NOT_FOUND`) 쓰지 않습니다 — worker 는 항상 실제
# 경로(`/usr/local/lib/node_modules/.../dist/index.js`)를 직접 `node` 로 실행합니다
# (compose 의 `AETHER_MCP_SERVERS` 기본값 참고).
COPY --from=mcp-filesystem /usr/local/bin/node /usr/local/bin/node
COPY --from=mcp-filesystem /usr/local/lib/node_modules/@modelcontextprotocol \
    /usr/local/lib/node_modules/@modelcontextprotocol

# spec 0003 R-7 (smoke): Filesystem 서버에게 허용할 디렉터리와, 실제로 읽어
# `succeeded` 까지 가는 고정 파일을 빌드 시점에 만들어 둡니다 — 오프라인
# 판정(D-8)이 런타임에 아무것도 받지 않고도 성립해야 하기 때문입니다.
RUN mkdir -p /srv/mcp-filesystem \
    && printf 'aether smoke fixture — read via Filesystem MCP Server (spec 0003 R-7)\n' \
        > /srv/mcp-filesystem/smoke.txt \
    && chmod -R a+rX /srv/mcp-filesystem

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

COPY . .

RUN uv sync --all-packages --frozen --no-dev

ARG AETHER_VERSION=dev
ENV AETHER_VERSION=${AETHER_VERSION}

RUN groupadd --gid 1000 aether \
    && useradd --uid 1000 --gid aether --no-create-home --shell /usr/sbin/nologin aether \
    && chown -R aether:aether /app

USER aether

# HTTP 포트를 열지 않습니다 — Redis Streams 소비자입니다(spec 2.6). HEALTHCHECK 는
# 이미지가 아니라 compose(infra/docker/compose.yaml)가 소유합니다(spec 0002 2.14) —
# Redis 접속 정보(AETHER_REDIS_URL)가 compose 조립 시점에만 정해지기 때문입니다.

CMD ["aether-worker"]
