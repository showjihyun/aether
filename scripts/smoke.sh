#!/usr/bin/env bash
# smoke.sh — spec 0002 2.11 (P1-9): compose 로 전체 스택을 띄우고 agent 생성 -> run ->
# succeeded -> trace 파일 등장까지 한 번에 확인합니다. 개발자의 compose 스택과 격리된
# 프로젝트(`-p aether-smoke`)에서 돕니다 — 이미 떠 있는 개발 스택을 건드리지 않고,
# 끝나면 스스로 정리합니다(trap).
#
# 사용:
#   scripts/smoke.sh              # 이미지를 빌드하며 시나리오만
#   scripts/smoke.sh --bench      # 시나리오 뒤 성능 측정(spec 2.13)까지
#   SMOKE_NO_BUILD=1 scripts/smoke.sh   # CI 캐시 경로 — compose.ci.yaml 이미지를 그대로 씀
#
# 비밀값: 임시 `.env`(mktemp, 랜덤 값)를 쓰고 실행 뒤 지웁니다. 원문 키·비밀값은 어떤
# 출력에도 남기지 않습니다(AGENTS.md Trust).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
cd "$ROOT"

# Windows Git Bash 가 `docker compose exec` 로 넘기는 컨테이너 쪽 인자(예: 명령 이름이
# 단일 문자 "-" 인 stdin 스크립트 실행)를 호스트 경로로 오인해 바꾸지 않게 합니다
# (spec 0002 2.11). compose 파일 인자·env-file 인자는 전부 **상대 경로**로만 다뤄
# 이 설정과 무관하게 올바르게 해석되도록 합니다(레포 밖 절대경로를 넘기지 않음).
export MSYS_NO_PATHCONV=1

BENCH=0
for arg in "$@"; do
  case "$arg" in
    --bench) BENCH=1 ;;
    *)
      echo "smoke: unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

OTEL_DIR="infra/docker/out/otel-smoke"
BENCH_OUT="infra/docker/out/smoke-bench.json"
CLIENT_SCRIPT="scripts/smoke_client.py"

# 호스트에서 JSON 을 다룰 파이썬을 고릅니다 — 이름만으로 고르지 않고 실제로 동작하는지
# 확인합니다. Windows 에서는 "python3" 가 Microsoft Store 스텁으로 깔려 있어 존재는
# 하되(`command -v` 성공) 실행하면 아무 것도 안 하고 0 이 아닌 코드로 끝나는 경우가
# 있습니다(실측). `import sys` 하나로 왕복해 실제로 파이썬을 실행하는지까지 봅니다.
HOST_PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import sys" >/dev/null 2>&1; then
    HOST_PYTHON="$candidate"
    break
  fi
done
if [ -z "$HOST_PYTHON" ]; then
  echo "smoke: no working python interpreter found on host (tried python3, python)" >&2
  exit 1
fi

# --bench 의 환경 메타데이터는 지금(스택을 띄우기 전) 구해 둡니다 — 바뀌지 않는
# 값이고, bench 의 200 회 순차 요청 뒤로 미루면 오래 걸리는 명령 뒤에야 실행됩니다.
GIT_COMMIT="$(git rev-parse --short HEAD)"
OS_INFO="$(uname -srm)"

# 임시 .env — infra/docker/.env 를 쓰지 않습니다(개발 스택과 격리, spec 2.11). 상대
# 경로로 만들어 두면 --env-file 인자가 절대경로 변환에 기대지 않고, 이름을 `.env.*`
# 로 두면 만에 하나 정리가 실패해도 .gitignore(`.env.*`)에 이미 걸립니다.
TMP_ENV="$(mktemp ./.env.smoke.XXXXXX)"

# COMPOSE 는 배열로 둡니다 — 인자에 공백이 섞여도(예: 사용자 홈 경로) 안전합니다.
COMPOSE=(docker compose -p aether-smoke --env-file "$TMP_ENV" \
  -f infra/docker/compose.yaml -f infra/docker/compose.smoke.yaml)
BUILD_FLAG="--build"
if [ "${SMOKE_NO_BUILD:-}" = "1" ]; then
  COMPOSE+=(-f infra/docker/compose.ci.yaml)
  BUILD_FLAG="--no-build"
fi

STARTED_STACK=0

cleanup() {
  local exit_code=$?
  trap - EXIT
  if [ "$exit_code" -ne 0 ] && [ "$STARTED_STACK" -eq 1 ]; then
    echo "smoke: failing — recent logs (api, worker, migrate):" >&2
    "${COMPOSE[@]}" logs --no-color --tail 80 api worker migrate >&2 || true
  fi
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f "$TMP_ENV"
  exit "$exit_code"
}
trap cleanup EXIT

# 임시 .env 를 만듭니다 — .env.example 의 실제 키 값만 옮기고, `<generate>` 자리는
# 일회용 랜덤 값으로 채웁니다. 모델 어댑터는 항상 fake 로 강제합니다(spec 0002 C-7,
# R-6) — 판정은 네트워크 없이 갑니다. 비밀값은 stdout/stderr 어디에도 쓰지 않습니다.
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    AETHER_MODEL_ADAPTER=*) printf 'AETHER_MODEL_ADAPTER=fake\n' ;;
    AETHER_MODEL_API_KEY=*) printf 'AETHER_MODEL_API_KEY=\n' ;;
    *'=<generate>')
      key="${line%%=*}"
      printf '%s=%s\n' "$key" "$(openssl rand -hex 24)"
      ;;
    *) printf '%s\n' "$line" ;;
  esac
done <infra/docker/.env.example >"$TMP_ENV"

# spec 0002 2.9: Linux CI 에서 Docker 가 없는 디렉터리를 root 소유로 만들면 uid 10001
# 의 collector 가 못 씁니다 — 미리 만들고 누구나 쓰게 합니다. 이전 실행의 spans.jsonl
# 은 지워 이번 실행의 trace_id 폴링이 과거 파일에 속지 않게 합니다.
mkdir -p "$OTEL_DIR"
chmod 0777 "$OTEL_DIR"
rm -f "${OTEL_DIR}/spans.jsonl"

echo "smoke: starting stack (project=aether-smoke, build=${BUILD_FLAG})..." >&2
STARTED_STACK=1
"${COMPOSE[@]}" up -d --wait "$BUILD_FLAG" postgres redis migrate otel-collector api worker

# spec 0001 2.9: 키는 원문이 stdout 에 한 번만 나갑니다 — 그 줄만 잡고 개행을 정리합니다.
SMOKE_API_KEY="$("${COMPOSE[@]}" exec -T api aether-api keys create --label smoke 2>/dev/null | tr -d '\r\n')"
if [ -z "$SMOKE_API_KEY" ]; then
  echo "smoke: failed to issue an API key" >&2
  exit 1
fi
export SMOKE_API_KEY

echo "smoke: running scenario (create agent -> run -> succeeded)..." >&2
SCENARIO_JSON="$("${COMPOSE[@]}" exec -T -e SMOKE_API_KEY api python - scenario <"$CLIENT_SCRIPT")"

RUN_ID="$(printf '%s' "$SCENARIO_JSON" | "$HOST_PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
TRACE_ID="$(printf '%s' "$SCENARIO_JSON" | "$HOST_PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("trace_id") or "")')"

if [ -z "$TRACE_ID" ]; then
  echo "smoke: scenario succeeded without a trace_id — cannot verify collector output" >&2
  exit 1
fi

echo "smoke: waiting for trace ${TRACE_ID} in ${OTEL_DIR}/spans.jsonl..." >&2
TRACE_DEADLINE=$((SECONDS + 30))
TRACE_FOUND=0
while [ "$SECONDS" -lt "$TRACE_DEADLINE" ]; do
  if [ -f "${OTEL_DIR}/spans.jsonl" ] && grep -q "$TRACE_ID" "${OTEL_DIR}/spans.jsonl" 2>/dev/null; then
    TRACE_FOUND=1
    break
  fi
  sleep 1
done

if [ "$TRACE_FOUND" -ne 1 ]; then
  echo "smoke: trace ${TRACE_ID} did not appear in ${OTEL_DIR}/spans.jsonl within 30s" >&2
  exit 1
fi

ELAPSED=$SECONDS

if [ "$BENCH" -eq 1 ]; then
  echo "smoke: running bench (200 sequential run requests, warmup 20)..." >&2
  BENCH_JSON="$("${COMPOSE[@]}" exec -T -e SMOKE_API_KEY api python - bench <"$CLIENT_SCRIPT")"

  DOCKER_VERSION="$(docker version --format '{{.Server.Version}}')"
  MEASURED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  "$HOST_PYTHON" - "$BENCH_JSON" "$GIT_COMMIT" "$OS_INFO" "$DOCKER_VERSION" "$MEASURED_AT" "$BENCH_OUT" <<'PY'
import json
import sys

bench_json, commit, os_info, docker_version, measured_at, out_path = sys.argv[1:7]
summary = json.loads(bench_json)
summary.update(
    {
        "adapter": "fake",
        "commit": commit,
        "os": os_info,
        "docker": docker_version,
        "measured_at": measured_at,
    }
)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, sort_keys=True)
    f.write("\n")
PY
  echo "smoke: bench written to ${BENCH_OUT}" >&2
fi

echo "smoke: pass (run=${RUN_ID}, trace=${TRACE_ID}, ${ELAPSED}s)"
exit 0
