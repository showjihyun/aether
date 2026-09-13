# apps/worker (Data Plane). 빌드 컨텍스트는 저장소 루트입니다 — api.Dockerfile 과 같은 이유
# (spec 0001 2.7, plan P0-5 순서 1). `aether_api` 를 import 하지 않습니다(spec 2.6) —
# 이 이미지도 `apps/api` 소스를 담지만 그것은 uv workspace 설치의 부산물일 뿐,
# `aether_worker` 코드가 그것을 참조하지 않는다는 사실은 AR-7 계약(api-arch)이 판정합니다.

FROM ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 AS uv

FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS runtime

COPY --from=uv /uv /uvx /usr/local/bin/

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
