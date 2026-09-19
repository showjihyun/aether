#!/usr/bin/env bash
# guard-eval-blind.sh — PreToolUse hook.
# improvement-log 2026-09-17-001: 대표 task 를 새 세션으로 실행하는 동안, 실행
# 에이전트가 evaluation/tasks(합격 기준)나 evaluation/runs(지난 판정 근거·평가자가
# 심은 결함)를 스스로 읽어 blind 조건이 깨진 사고가 있었다(REP-5, REP-8-r2). 이
# 스크립트는 저장소 루트에 마커 파일 `.eval-blind` 가 있을 때만 그 두 경로를
# 차단한다 — 평상시 작업(리뷰, 회귀 재현 등)은 이 경로를 자유롭게 읽어야 하므로
# 상시로 막지 않는다.
#
# 입력 형식과 파싱 관례(jq 있으면 jq, 없으면 grep 폴백)는
# harness/hooks/guard-evaluation-tampering.sh 의 read_stdin_payload · json_field 를
# 참고했다(번들 파일 자체는 고치지 않는다).
#
# 사용:
#   scripts/guard-eval-blind.sh                # Claude Code PreToolUse hook, stdin=hook JSON
#   scripts/guard-eval-blind.sh --root <경로>   # 테스트용: 저장소 루트를 바꿔 지정
#
# 종료 코드:
#   0 — 마커 없음 / 대상 경로 아님 / 입력을 해석하지 못함(훅 오류가 도구 호출을 막지 않게).
#   2 — 마커가 있고 evaluation/tasks 또는 evaluation/runs 를 참조함(차단, stderr 사유).
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
      emit "guard-eval-blind: unknown argument: $1"
      exit 2
      ;;
  esac
done
ROOT="${ROOT%/}"

MARKER_PATH="${ROOT}/.eval-blind"
LOG_PATH="${ROOT}/.eval-blind.log"

# 마커가 없으면 평상시 작업입니다. stdin 조차 읽지 않고 곧바로 통과시킵니다.
if [[ ! -f "${MARKER_PATH}" ]]; then
  exit 0
fi

read_stdin_payload() {
  if [[ -t 0 ]]; then
    printf '%s' ""
  else
    cat || true
  fi
}

PAYLOAD="$(read_stdin_payload)"
if [[ -z "${PAYLOAD}" ]]; then
  emit "[harness] guard-eval-blind: stdin 이 비어 있어 검사를 건너뜁니다."
  exit 0
fi

if command -v jq >/dev/null 2>&1; then
  if ! printf '%s' "${PAYLOAD}" | jq -e . >/dev/null 2>&1; then
    emit "[harness] guard-eval-blind: hook 입력 JSON 을 해석하지 못해 검사를 건너뜁니다."
    exit 0
  fi
fi

# json_unescape <문자열> — JSON 문자열 리터럴의 이스케이프를 풉니다. jq 가 없을 때만
# 쓰는 grep 폴백 경로에서만 필요합니다(jq -r 은 이미 풀어서 내놓습니다). 근거와 구현은
# harness/hooks/guard-evaluation-tampering.sh 의 동명 함수와 같습니다 — Windows 경로가
# "evaluation\\tasks\\..." 로 이스케이프되어 오므로 풀지 않으면 역슬래시 표기를 잡지 못합니다.
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

# 검사 대상 필드. 있는 것만 봅니다.
FIELD_NAMES=(file_path path pattern command glob notebook_path)
FIELD_VALUES=()
for _name in "${FIELD_NAMES[@]}"; do
  FIELD_VALUES+=("$(json_field "${PAYLOAD}" ".tool_input.${_name}" "${_name}")")
done

# is_blind_path <값> — evaluation/tasks 또는 evaluation/runs 를 슬래시·역슬래시
# 두 표기 모두로 참조하는지 봅니다. evaluation/README.md 같은 그 밖의 evaluation/
# 경로는 이 두 접두사와 일치하지 않으므로 걸리지 않습니다.
is_blind_path() {
  local v="$1"
  case "${v}" in
    *evaluation/tasks*) return 0 ;;
    *evaluation/runs*) return 0 ;;
    *'evaluation\tasks'*) return 0 ;;
    *'evaluation\runs'*) return 0 ;;
  esac
  return 1
}

HIT_FIELD=""
HIT_VALUE=""
for _i in "${!FIELD_NAMES[@]}"; do
  _v="${FIELD_VALUES[$_i]}"
  [[ -n "${_v}" ]] || continue
  if is_blind_path "${_v}"; then
    HIT_FIELD="${FIELD_NAMES[$_i]}"
    HIT_VALUE="${_v}"
    break
  fi
done

if [[ -z "${HIT_FIELD}" ]]; then
  exit 0
fi

# 차단마다 한 줄을 남깁니다 — blind 조건이 실제로 작동했다는 증거입니다
# (improvement-log 2026-09-17-001 의 regression_check).
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || printf 'unknown')"
printf '%s\t%s\t%s=%s\n' "${TS}" "${TOOL_NAME}" "${HIT_FIELD}" "${HIT_VALUE}" >> "${LOG_PATH}"

emit "[harness] 평가 실행 중에는 task 정의와 지난 판정을 읽지 않습니다: ${HIT_VALUE} — 이 실행의 blind 조건입니다(improvement-log 2026-09-17-001)."
exit 2
