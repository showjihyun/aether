# apps/api (Control Plane). 빌드 컨텍스트는 저장소 루트입니다 —
# `uv sync --all-packages` 가 uv workspace 전체(apps/*, packages/*)를 봐야 합니다
# (spec 0001 2.7, plan P0-5 순서 1). `docker build -f infra/docker/api.Dockerfile .`
# 형태가 아니라 compose 의 `build.context: ../..` 로 호출됩니다.
#
# 이 이미지는 `api` 서비스(uvicorn)와 `migrate` 서비스(alembic, command 오버라이드)
# 둘 다에 씁니다 — 둘 다 같은 uv workspace 설치가 필요하기 때문입니다(spec 2.7).

# 확인: uv 버전은 이 세션에서 로컬로 쓴 0.11.2 로 고정. digest 는
# `docker buildx imagetools inspect ghcr.io/astral-sh/uv:0.11.2` 로 얻었습니다.
FROM ghcr.io/astral-sh/uv:0.11.2@sha256:c4f5de312ee66d46810635ffc5df34a1973ba753e7241ce3a08ef979ddd7bea5 AS uv

# 확인: Python 버전은 .python-version(3.12)과 맞춥니다. Debian slim — psycopg[binary]
# 는 자체 libpq 를 번들하므로 추가 시스템 패키지가 필요 없습니다.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS runtime

COPY --from=uv /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# uv workspace 전체를 복사합니다(.dockerignore 가 .git·node_modules·.venv·__pycache__ 등을 제외).
COPY . .

RUN uv sync --all-packages --frozen --no-dev

# spec 2.3: version 은 빌드 인자 → 이미지 env. `AETHER_` 접두사라 Settings 가 그대로 읽습니다.
ARG AETHER_VERSION=dev
ENV AETHER_VERSION=${AETHER_VERSION}

# non-root. R-6 계열 위생: 컨테이너가 루트로 뜨지 않습니다.
RUN groupadd --gid 1000 aether \
    && useradd --uid 1000 --gid aether --no-create-home --shell /usr/sbin/nologin aether \
    && chown -R aether:aether /app

USER aether

EXPOSE 8000

# slim 이미지에 curl 이 없으므로 이미지 안 python(venv)으로 확인합니다(세션 계약).
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=10 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz', timeout=2).status == 200 else 1)"]

# `migrate` 서비스는 compose 의 command 오버라이드로 이 ENTRYPOINT 없이 alembic 을 부릅니다.
CMD ["uvicorn", "aether_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
