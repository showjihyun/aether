#!/usr/bin/env bash
# stop-verify-gate.sh — Stop hook. 검증 없이 작업을 종료하는 것을 차단합니다.
# exit 0: 종료 허용 / exit 2: 종료 차단(stderr 사유가 에이전트에게 전달됨)
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
COMMON_LIB="${HARNESS_DIR}/scripts/lib/common.sh"
VERIFY_REL=".harness/verify.json"

emit() { printf '%s\n' "$*" >&2; }

usage() {
  cat <<'USAGE'
사용법: stop-verify-gate.sh [--help]

Claude Code 의 Stop hook 으로 등록해 사용합니다. hook JSON 을 stdin 으로 받습니다.

동작:
  - stop_hook_active 가 true 이면 즉시 통과합니다(무한 루프 방지).
  - HARNESS_SKIP_STOP_GATE=1 이면 통과하되 stderr 에 우회 사실을 남깁니다.
  - .harness/verify.json 이 없거나 status 가 pass 가 아니면 exit 2 로 종료를 차단합니다.
  - 마지막 검증이 --only 부분 실행이었으면 차단합니다.
  - 검증 이후 작업 트리가 바뀌었으면(지문 불일치) 차단합니다.

환경 변수:
  HARNESS_SKIP_STOP_GATE=1   게이트를 우회합니다(위험).
  CLAUDE_PROJECT_DIR         프로젝트 루트. 없으면 스스로 탐색합니다.
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

# lib/common.sh 가 있으면 사용하고, 없어도 hook 은 동작해야 합니다.
if [[ -f "${COMMON_LIB}" ]]; then
  # shellcheck source=../scripts/lib/common.sh
  source "${COMMON_LIB}" || true
fi

fallback_find_project_root() {
  local dir="${1:-${PWD}}"
  while [[ "${dir}" != "/" && -n "${dir}" ]]; do
    if [[ -e "${dir}/.git" || -f "${dir}/harness.config" || -d "${dir}/harness" ]]; then
      printf '%s\n' "${dir}"
      return 0
    fi
    dir="$(dirname -- "${dir}")"
  done
  printf '%s\n' "${1:-${PWD}}"
  return 0
}

resolve_project_root() {
  if [[ -n "${CLAUDE_PROJECT_DIR:-}" && -d "${CLAUDE_PROJECT_DIR}" ]]; then
    printf '%s\n' "${CLAUDE_PROJECT_DIR}"
    return 0
  fi
  if declare -F find_project_root >/dev/null 2>&1; then
    local root=""
    root="$(find_project_root 2>/dev/null || true)"
    if [[ -n "${root}" && -d "${root}" ]]; then
      printf '%s\n' "${root}"
      return 0
    fi
  fi
  fallback_find_project_root "$(cd -- "${HARNESS_DIR}/.." && pwd)"
}

read_stdin_payload() {
  if [[ -t 0 ]]; then
    printf '%s' ""
  else
    cat || true
  fi
}

# json_bool <payload> <key> — true/false 문자열을 출력합니다.
json_bool() {
  local payload="$1" key="$2" value=""
  if command -v jq >/dev/null 2>&1; then
    value="$(printf '%s' "${payload}" | jq -r --arg k "${key}" '(.[$k] // false) | tostring' 2>/dev/null || true)"
  fi
  if [[ -z "${value}" || "${value}" == "null" ]]; then
    if printf '%s' "${payload}" | grep -qE "\"${key}\"[[:space:]]*:[[:space:]]*true"; then
      value="true"
    else
      value="false"
    fi
  fi
  printf '%s' "${value}"
}

# json_string <file> <key> — 최상위 문자열 값을 출력합니다.
json_string() {
  local file="$1" key="$2" value=""
  [[ -f "${file}" ]] || return 0
  if command -v jq >/dev/null 2>&1; then
    value="$(jq -r --arg k "${key}" '.[$k] // empty' "${file}" 2>/dev/null || true)"
  fi
  if [[ -z "${value}" ]]; then
    # jq 가 없을 때: steps 배열 앞부분(최상위 영역)에서 먼저 찾고, 없으면 파일 전체에서 찾습니다.
    local content="" head=""
    content="$(cat -- "${file}")"
    head="${content%%\"steps\"*}"
    value="$(printf '%s' "${head}" | grep -oE "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -n 1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/' || true)"
    if [[ -z "${value}" ]]; then
      value="$(printf '%s' "${content}" | grep -oE "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -n 1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/' || true)"
    fi
  fi
  printf '%s' "${value}"
}

# json_raw <file> <key> — 최상위 값을 따옴표 없이 출력합니다.
# json_string 과 달리 불리언·숫자도 읽습니다. partial 과 ran_steps 가 그 형태입니다.
json_raw() {
  local file="$1" key="$2" value="" content="" head=""
  [[ -f "${file}" ]] || return 0
  if command -v jq >/dev/null 2>&1; then
    value="$(jq -r --arg k "${key}" 'if has($k) then (.[$k] | tostring) else empty end' "${file}" 2>/dev/null || true)"
  fi
  if [[ -z "${value}" ]]; then
    content="$(cat -- "${file}")"
    head="${content%%\"steps\"*}"
    # 앞에서부터 키와 첫 콜론만 떼어냅니다. '.*:' 로 쓰면 탐욕적 매칭이
    # 값 안의 콜론(예: 2026-09-05T02:44:43Z)까지 먹어 값이 잘립니다.
    value="$(printf '%s' "${head}" \
      | grep -oE "\"${key}\"[[:space:]]*:[[:space:]]*(\"[^\"]*\"|[^,[:space:]}]+)" \
      | head -n 1 | sed -E 's/^"[^"]*"[[:space:]]*:[[:space:]]*//; s/^"//; s/"$//' || true)"
  fi
  printf '%s' "${value}"
}

# 작업 트리 지문. lib/common.sh 가 있으면 그쪽 정본을 씁니다.
# common.sh 의 harness_tree_fingerprint 와 **같은 입력**을 해시해야 합니다.
# 다르면 verify 가 기록한 지문과 게이트가 계산한 지문이 영원히 어긋나 모든 종료가 막힙니다.
fallback_tree_fingerprint() {
  local root="${1:-$PWD}" hasher="" h="" p="" line="" meta="" blob=""
  git -C "${root}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
  for h in sha1sum shasum md5sum cksum; do
    if command -v "${h}" >/dev/null 2>&1; then hasher="${h}"; break; fi
  done
  [[ -n "${hasher}" ]] || return 0
  local -A _dirty=()
  while IFS= read -r -d '' p; do _dirty["${p}"]=1; done \
    < <(git -C "${root}" diff --name-only -z 2>/dev/null)
  {
    while IFS= read -r -d '' line; do
      meta="${line%%$'\t'*}"
      p="${line#*$'\t'}"
      [[ -f "${root}/${p}" ]] || continue
      if [[ -n "${_dirty[$p]:-}" ]]; then
        blob="$(git -C "${root}" hash-object -- "${root}/${p}" 2>/dev/null || printf 'unhashable')"
      else
        blob="${meta#* }"; blob="${blob%% *}"
      fi
      printf '%s %s\n' "${p}" "${blob}"
    done < <(git -C "${root}" ls-files -s -z 2>/dev/null)
    while IFS= read -r -d '' p; do
      [[ -f "${root}/${p}" ]] || continue
      printf '%s %s\n' "${p}" "$(git -C "${root}" hash-object -- "${root}/${p}" 2>/dev/null || printf 'unhashable')"
    done < <(git -C "${root}" ls-files -o --exclude-standard -z 2>/dev/null)
  } | LC_ALL=C sort | "${hasher}" | awk '{print $1}'
}

tree_fingerprint_of() {
  if declare -F harness_tree_fingerprint >/dev/null 2>&1; then
    harness_tree_fingerprint "$1"
  else
    fallback_tree_fingerprint "$1"
  fi
}

# failed_step_ids <file> — 실패한 step id 목록을 공백으로 이어 출력합니다.
failed_step_ids() {
  local file="$1"
  [[ -f "${file}" ]] || return 0
  if command -v jq >/dev/null 2>&1; then
    jq -r '[.steps[]? | select(.status != "pass") | .id] | join(", ")' "${file}" 2>/dev/null || true
    return 0
  fi
  # jq 가 없을 때: id 와 그 뒤에 오는 status 를 순서대로 짝지어 실패한 step 만 남깁니다.
  grep -oE '"(id|status)"[[:space:]]*:[[:space:]]*"[^"]*"' "${file}" 2>/dev/null \
    | sed -E 's/"([a-z_]+)"[[:space:]]*:[[:space:]]*"([^"]*)"/\1=\2/' \
    | awk -F= '
        $1 == "id" { id = $2; next }
        $1 == "status" && id != "" {
          if ($2 != "pass") { out = out (out == "" ? "" : ", ") id }
          id = ""
        }
        END { print out }
      ' || true
}

PAYLOAD="$(read_stdin_payload)"

# 1. 무한 루프 방지: 이 hook 때문에 이미 한 번 종료가 막힌 상태면 다시 막지 않습니다.
if [[ "$(json_bool "${PAYLOAD}" "stop_hook_active")" == "true" ]]; then
  exit 0
fi

# 2. 명시적 우회.
if [[ "${HARNESS_SKIP_STOP_GATE:-}" == "1" ]]; then
  emit "[harness] HARNESS_SKIP_STOP_GATE=1 로 verify 게이트를 우회했습니다. 이 종료는 검증되지 않았습니다."
  exit 0
fi

PROJECT_ROOT="$(resolve_project_root)"
VERIFY_JSON="${PROJECT_ROOT}/${VERIFY_REL}"

# 3. 검증 결과가 없는 경우.
if [[ ! -f "${VERIFY_JSON}" ]]; then
  emit "[harness] 종료를 차단했습니다: ${VERIFY_REL} 가 없습니다."
  emit "이번 작업에서 검증이 한 번도 실행되지 않았습니다."
  emit "다음 조치: ./harness/scripts/verify.sh 를 실행하고, 실패가 있으면 고친 뒤 다시 종료를 시도합니다."
  emit "검증이 불가능한 작업이라면 HARNESS_SKIP_STOP_GATE=1 로 우회하되 그 사유를 남깁니다."
  exit 2
fi

STATUS="$(json_string "${VERIFY_JSON}" "status")"

if [[ "${STATUS}" != "pass" ]]; then
  FAILED="$(failed_step_ids "${VERIFY_JSON}")"
  emit "[harness] 종료를 차단했습니다: ${VERIFY_REL} 의 status 가 '${STATUS:-unknown}' 입니다."
  if [[ -n "${FAILED}" ]]; then
    emit "실패한 단계: ${FAILED}"
  fi
  emit "다음 조치: 실패한 단계의 로그(.harness/logs/)를 읽고 원인을 고친 뒤 ./harness/scripts/verify.sh 를 다시 실행합니다."
  emit "테스트나 lint 규칙을 약화시켜 통과시키지 않습니다."
  exit 2
fi

# 4. 부분 실행. --only 로 일부 단계만 돈 결과는 완료 근거가 아닙니다.
#    이 검사가 없으면 5단계 중 1단계만 돌린 pass 가 전량 통과와 구별되지 않습니다.
PARTIAL="$(json_raw "${VERIFY_JSON}" "partial")"
if [[ "${PARTIAL}" == "true" ]]; then
  RAN="$(json_raw "${VERIFY_JSON}" "ran_steps")"
  DEFINED="$(json_raw "${VERIFY_JSON}" "defined_steps")"
  emit "[harness] 종료를 차단했습니다: 마지막 검증이 부분 실행이었습니다 (${RAN:-?}/${DEFINED:-?} 단계)."
  emit "--only 로 거른 결과는 완료 근거가 아닙니다. 실행되지 않은 단계는 통과한 것이 아닙니다."
  emit "다음 조치: ./harness/scripts/verify.sh 를 옵션 없이 실행합니다."
  exit 2
fi

# 5. 신선도. 검증한 뒤 파일을 고치고 종료하면 그 결과는 이 작업의 것이 아닙니다.
FINISHED_AT="$(json_raw "${VERIFY_JSON}" "finished_at")"
RECORDED_TREE="$(json_raw "${VERIFY_JSON}" "tree")"

if [[ -z "${FINISHED_AT}" ]]; then
  emit "[harness] 종료를 차단했습니다: ${VERIFY_REL} 에 신선도 근거가 없습니다."
  emit "이 파일은 finished_at 과 tree 를 기록하기 이전 버전의 verify.sh 가 만든 것입니다."
  emit "다음 조치: ./harness/scripts/verify.sh 를 다시 실행합니다."
  exit 2
fi

CURRENT_TREE="$(tree_fingerprint_of "${PROJECT_ROOT}")"
if [[ -n "${RECORDED_TREE}" && -n "${CURRENT_TREE}" && "${RECORDED_TREE}" != "${CURRENT_TREE}" ]]; then
  emit "[harness] 종료를 차단했습니다: 검증 이후 작업 트리가 바뀌었습니다."
  emit "마지막 검증: ${FINISHED_AT} (당시 지문 ${RECORDED_TREE:0:12}, 현재 ${CURRENT_TREE:0:12})"
  emit "그 결과는 지금의 변경을 검증한 것이 아닙니다."
  emit "다음 조치: ./harness/scripts/verify.sh 를 다시 실행합니다."
  exit 2
fi

exit 0
