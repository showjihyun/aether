#!/usr/bin/env bash
# fetch-model.sh — spec 0006 D-5, D-12, R-9 (MVP-3, H-3): 모델 파일을 `ollama_models` 볼륨에
# **미리** 받아 둡니다. 네트워크가 있는 환경에서 사람이 한 번 실행합니다 - 부팅 경로(compose
# up, worker)는 모델을 받지 않습니다(DP-4). 받은 뒤에는 네트워크 없이 돕니다.
#
# 사용:
#   scripts/fetch-model.sh                      # 제품 기본 모델 qwen3.8:27b (17.7 GB)
#   scripts/fetch-model.sh --test-model         # 판정 전용 소형 모델 qwen2.5:0.5b (~400 MB)
#   scripts/fetch-model.sh --model <태그>       # 임의 모델
#   AETHER_FETCH_MODEL=<태그> scripts/fetch-model.sh
#   --project <이름>   볼륨이 속한 compose 프로젝트(기본 aether-dev = `aether up` 의 기본)
#   --env-file <경로>  compose 가 읽을 .env(기본: .env.example 로 만든 임시 파일)
#
# 우선순위: --model > --test-model > AETHER_FETCH_MODEL > 기본값. 멱등: 이미 있으면 받지
# 않고 그렇다고 출력합니다. 받지 못하면 0 이 아닌 코드로 끝납니다(조용한 성공 없음).
# 비밀값: 임시 .env 의 값은 어떤 출력에도 남기지 않고 끝나면 지웁니다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
cd "$ROOT"
export MSYS_NO_PATHCONV=1

DEFAULT_MODEL="qwen3.8:27b"
TEST_MODEL="qwen2.5:0.5b"

MODEL=""
USE_TEST=0
PROJECT="${AETHER_FETCH_PROJECT-aether-dev}"
ENV_FILE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --test-model) USE_TEST=1 ;;
    --model) MODEL="${2:-}"; shift ;;
    --project) PROJECT="${2-}"; shift ;;
    --env-file) ENV_FILE="${2:-}"; shift ;;
    *)
      echo "fetch-model: unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

if [ -z "$MODEL" ]; then
  if [ "$USE_TEST" -eq 1 ]; then
    MODEL="$TEST_MODEL"
  else
    MODEL="${AETHER_FETCH_MODEL:-$DEFAULT_MODEL}"
  fi
fi

# 프로젝트 이름은 볼륨의 주소입니다 - 비었거나 compose 기본 이름이면 엉뚱한 볼륨에 쓴다.
if ! [[ "$PROJECT" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || [ "$PROJECT" = "docker" ]; then
  echo "fetch-model: invalid --project: '${PROJECT}'" >&2
  exit 2
fi
if ! [[ "$MODEL" =~ ^[A-Za-z0-9][A-Za-z0-9._/:-]*$ ]]; then
  echo "fetch-model: invalid model tag: '${MODEL}'" >&2
  exit 2
fi

TMP_ENV=""
if [ -z "$ENV_FILE" ]; then
  TMP_ENV="$(mktemp ./.env.fetch.XXXXXX)"
  ENV_FILE="$TMP_ENV"
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      *'=<generate>') printf '%s=%s\n' "${line%%=*}" "$(openssl rand -hex 24)" ;;
      *'=<optional>') printf '%s=\n' "${line%%=*}" ;;
      *) printf '%s\n' "$line" ;;
    esac
  done <infra/docker/.env.example >"$TMP_ENV"
fi

COMPOSE=(docker compose -p "$PROJECT" --env-file "$ENV_FILE" \
  -f infra/docker/compose.yaml -f infra/docker/compose.llm.yaml)

WAS_RUNNING=""
STARTED=0

cleanup() {
  local exit_code=$?
  trap - EXIT
  # 이 스크립트가 켠 llm 만 끕니다(RAM). 볼륨은 지우지 않습니다.
  if [ "$STARTED" -eq 1 ] && [ -z "$WAS_RUNNING" ]; then
    "${COMPOSE[@]}" stop llm >/dev/null 2>&1 || true
  fi
  if [ -n "$TMP_ENV" ]; then rm -f "$TMP_ENV"; fi
  exit "$exit_code"
}
trap cleanup EXIT

# `ollama list` 첫 열이 정확히 같은 태그인가. 태그가 없으면 ollama 는 :latest 로 봅니다.
have_model() {
  local want="$MODEL" listing
  case "$want" in *:*) ;; *) want="${want}:latest" ;; esac
  listing="$("${COMPOSE[@]}" exec -T llm ollama list 2>/dev/null | tr -d '\r')" || return 1
  printf '%s\n' "$listing" | awk -v want="$want" 'NR>1 && $1==want {found=1} END {exit !found}'
}

WAS_RUNNING="$("${COMPOSE[@]}" ps -q llm 2>/dev/null | tr -d '\r\n' || true)"

echo "fetch-model: project=${PROJECT}, model=${MODEL}" >&2
# 이미 떠 있으면(예: e2e 가 방금 올린 스택) 다시 올리지 않습니다 - 네트워크 설정이 다른
# 스택을 건드리지 않기 위해서입니다.
if [ -z "$WAS_RUNNING" ]; then
  STARTED=1
  if ! "${COMPOSE[@]}" up -d --wait llm >&2; then
    echo "fetch-model: could not start the llm service (is Docker running? the ollama image needs a network once)." >&2
    exit 1
  fi
fi

if have_model; then
  echo "fetch-model: ${MODEL} is already present in the model volume - nothing to download."
  exit 0
fi

echo "fetch-model: pulling ${MODEL} (this needs network; the product itself never downloads at boot)..." >&2
if ! "${COMPOSE[@]}" exec -T llm ollama pull "$MODEL" >&2; then
  echo "fetch-model: pull of ${MODEL} failed. Check the network, then run again - it resumes and is idempotent." >&2
  exit 1
fi

if ! have_model; then
  echo "fetch-model: pull finished but ${MODEL} is not in the model volume - not treating this as success." >&2
  exit 1
fi
echo "fetch-model: ${MODEL} is now in the model volume (project=${PROJECT})."
exit 0
