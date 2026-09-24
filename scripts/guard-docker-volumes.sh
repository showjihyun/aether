#!/usr/bin/env bash
# guard-docker-volumes.sh — PreToolUse hook.
# improvement-log 2026-09-22-003: 2026-09-23 REP-4 평가 실행에서 실행자가 격리
# 프로젝트(`-p`) 없이 기본 개발 compose 프로젝트로 스택을 띄웠다가 정리하며
# `docker compose ... down -v` 를 실행해, 실행 전부터 있던 개발 볼륨
# `docker_postgres_data`·`docker_redis_data` 를 지웠다. 되돌릴 수 없었다.
# `scripts/smoke.sh` 는 `-p aether-smoke` 로 격리해 이미 떠 있는 개발 스택을
# 건드리지 않는다고 주석에 적고 있는데, 에이전트가 compose 를 직접 부를 때
# 적용되는 장치는 없었다. 이 hook 은 마커 파일에 의존하지 않고 항상 검사한다 —
# 평가 실행뿐 아니라 평소 작업에서도 개발 볼륨을 잃으면 안 된다.
#
# 막는 것:
#   1. `docker compose … down …` 에 `-v`/`--volumes` 가 있고 격리 프로젝트 지정
#      (`-p <이름>`·`--project-name <이름>`·`--project-name=<이름>`·명령 앞
#      `COMPOSE_PROJECT_NAME=<이름>`)이 없는 경우. 이름이 compose 의 기본
#      프로젝트 이름인 `docker` 이면 명시했더라도 격리로 인정하지 않는다.
#   2. `docker volume rm …` 의 대상 중 `docker_` 로 시작하는 볼륨 이름이 있는 경우.
#   3. `docker volume prune …`·`docker system prune …` 에 `--volumes` 가 있는 경우.
#
# 입력 형식과 파싱 관례(jq 있으면 jq, 없으면 grep 폴백)는 scripts/guard-eval-blind.sh
# 를 따랐다(그 스크립트 자체는 고치지 않는다).
#
# 사용:
#   scripts/guard-docker-volumes.sh                # Claude Code PreToolUse hook, stdin=hook JSON
#   scripts/guard-docker-volumes.sh --root <경로>   # 테스트용: 저장소 루트를 바꿔 지정
#
# 종료 코드:
#   0 — 대상 도구가 아님 / 대상 명령이 아님 / 입력을 해석하지 못함(훅 오류가 도구
#       호출을 막지 않게).
#   2 — 위 세 범주 중 하나에 해당(차단, stderr 사유).
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
DEFAULT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
ROOT="${DEFAULT_ROOT}"

emit() { printf '%s\n' "$*" >&2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    *)
      emit "guard-docker-volumes: unknown argument: $1"
      exit 2
      ;;
  esac
done
ROOT="${ROOT%/}"

LOG_PATH="${ROOT}/.harness/guard-volume-events.log"

read_stdin_payload() {
  if [[ -t 0 ]]; then
    printf '%s' ""
  else
    cat || true
  fi
}

PAYLOAD="$(read_stdin_payload)"
if [[ -z "${PAYLOAD}" ]]; then
  emit "[harness] guard-docker-volumes: stdin 이 비어 있어 검사를 건너뜁니다."
  exit 0
fi

if command -v jq >/dev/null 2>&1; then
  if ! printf '%s' "${PAYLOAD}" | jq -e . >/dev/null 2>&1; then
    emit "[harness] guard-docker-volumes: hook 입력 JSON 을 해석하지 못해 검사를 건너뜁니다."
    exit 0
  fi
fi

# json_unescape <문자열> — JSON 문자열 리터럴의 이스케이프를 풉니다.
json_unescape() {
  local s="${1-}"
  s="${s//\\\\/$'\001'}"
  s="${s//\\\"/\"}"
  s="${s//\\\//\/}"
  s="${s//\\n/$'\n'}"
  s="${s//\\t/$'\t'}"
  s="${s//\\r/$'\r'}"
  s="${s//$'\001'/\\}"
  printf '%s' "${s}"
}

# json_field <payload> <jq-path> <grep-key> — 문자열 값을 출력합니다.
json_field() {
  local payload="$1" jq_path="$2" grep_key="$3" value="" raw=""
  if command -v jq >/dev/null 2>&1; then
    value="$(printf '%s' "${payload}" | jq -r "${jq_path} // empty" 2>/dev/null || true)"
  fi
  if [[ -z "${value}" ]]; then
    raw="$(printf '%s' "${payload}" \
      | grep -oE "\"${grep_key}\"[[:space:]]*:[[:space:]]*\"(\\\\.|[^\"\\\\])*\"" \
      | head -n 1 \
      | sed -E 's/^"[^"]*"[[:space:]]*:[[:space:]]*"//; s/"$//' || true)"
    value="$(json_unescape "${raw}")"
  fi
  printf '%s' "${value}"
}

TOOL_NAME="$(json_field "${PAYLOAD}" '.tool_name' 'tool_name')"
[[ -n "${TOOL_NAME}" ]] || TOOL_NAME="(알수없음)"

COMMAND="$(json_field "${PAYLOAD}" '.tool_input.command' 'command')"
[[ -n "${COMMAND}" ]] || exit 0

# has_isolated_project <명령> — `-p <이름>`, `--project-name <이름>`,
# `--project-name=<이름>`, 명령 앞 `COMPOSE_PROJECT_NAME=<이름>` 중 하나로 격리
# 프로젝트를 지정했고, 그 이름이 compose 기본 프로젝트 이름 `docker` 가 아니면 참입니다.
has_isolated_project() {
  local v="$1" name=""
  if [[ "$v" =~ (^|[[:space:]])COMPOSE_PROJECT_NAME=([^[:space:]]+) ]]; then
    name="${BASH_REMATCH[2]}"
  elif [[ "$v" =~ --project-name=([^[:space:]]+) ]]; then
    name="${BASH_REMATCH[1]}"
  elif [[ "$v" =~ --project-name[[:space:]]+([^[:space:]]+) ]]; then
    name="${BASH_REMATCH[1]}"
  elif [[ "$v" =~ (^|[[:space:]])-p[[:space:]]+([^[:space:]]+) ]]; then
    name="${BASH_REMATCH[2]}"
  fi
  [[ -n "$name" && "$name" != "docker" ]]
}

# is_compose_down_with_volumes <명령> — `docker compose … down …` 에 `-v`/`--volumes`
# 가 있는지 봅니다(down 이후 토큰만 확인 — down 앞의 -v 는 다른 옵션일 수 있습니다).
is_compose_down_with_volumes() {
  local v="$1"
  [[ "$v" =~ docker[[:space:]]+compose ]] || return 1
  [[ "$v" =~ (^|[[:space:]])down([[:space:]]|$) ]] || return 1
  local after="${v#*down}"
  [[ "$after" =~ (^|[[:space:]])(-v|--volumes)([[:space:]]|$) ]]
}

# is_volume_rm_with_docker_prefixed <명령> — `docker volume rm …` 의 인자 중
# `docker_` 로 시작하는 이름이 있으면 참입니다.
is_volume_rm_with_docker_prefixed() {
  local v="$1"
  [[ "$v" =~ docker[[:space:]]+volume[[:space:]]+rm([[:space:]]|$) ]] || return 1
  local after="${v#*volume}"
  after="${after#*rm}"
  [[ "$after" =~ (^|[[:space:]])docker_[A-Za-z0-9_.-]* ]]
}

# is_prune_with_volumes <명령> — `docker volume prune …`·`docker system prune …`
# 에 `--volumes` 가 있으면 참입니다.
is_prune_with_volumes() {
  local v="$1"
  [[ "$v" =~ docker[[:space:]]+(volume|system)[[:space:]]+prune ]] || return 1
  [[ "$v" =~ --volumes ]]
}

REASON=""
if is_compose_down_with_volumes "${COMMAND}" && ! has_isolated_project "${COMMAND}"; then
  REASON="compose_down_volumes_default_project"
elif is_volume_rm_with_docker_prefixed "${COMMAND}"; then
  REASON="volume_rm_docker_prefixed"
elif is_prune_with_volumes "${COMMAND}"; then
  REASON="prune_with_volumes"
fi

if [[ -z "${REASON}" ]]; then
  exit 0
fi

mkdir -p "$(dirname -- "${LOG_PATH}")"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || printf 'unknown')"
printf '%s\t%s\t%s\n' "${TS}" "${TOOL_NAME}" "${COMMAND}" >> "${LOG_PATH}"

emit "[harness] 기본 compose 프로젝트의 볼륨 삭제를 막았습니다: ${COMMAND} — 기본 프로젝트의 볼륨(docker_postgres_data 등)은 개발 데이터이며 지우면 되돌릴 수 없습니다. -p <이름> 으로 격리 프로젝트를 지정하고 그 프로젝트만 내리십시오. scripts/smoke.sh 가 이 방식입니다(-p aether-smoke). 근거: improvement-log 2026-09-22-003."
exit 2
