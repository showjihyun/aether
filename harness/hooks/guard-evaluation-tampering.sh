#!/usr/bin/env bash
# guard-evaluation-tampering.sh — PreToolUse hook.
# 평가·게이트를 규정하는 파일을 에이전트가 임의로 고치는 것을 차단합니다.
# exit 0: 허용(경고는 stderr) / exit 2: 차단(stderr 사유가 에이전트에게 전달됨)
set -euo pipefail

# 보호·경고 패턴과 경로 판정 함수는 hooks/lib/guard-lib.sh 가 소유합니다.
# 사후 검출(detect-guarded-change.sh)이 **같은 목록과 같은 일치 규칙**을 써야 하기
# 때문입니다. 목록이 갈라지면 한쪽이 막는 것을 다른 쪽이 보지 못하고, 그 틈이
# 아무 신호도 내지 않습니다. 프로젝트 고유 추가분도 그 파일에 적습니다.

# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
COMMON_LIB="${HARNESS_DIR}/scripts/lib/common.sh"
DETECT_LIB="${HARNESS_DIR}/scripts/lib/detect-stack.sh"
GUARD_LIB="${SCRIPT_DIR}/lib/guard-lib.sh"

emit() { printf '%s\n' "$*" >&2; }

# 공용 판정 자산입니다. 없으면 보호 목록도 일치 규칙도 없어 가드가 성립하지 않습니다.
# 그 상태를 조용히 통과시키지 않고 사실을 알린 뒤 넘깁니다. 여기서 차단하면 파일 하나가
# 사라진 것만으로 모든 편집이 막혀 복구조차 못 하게 됩니다.
if [[ -f "${GUARD_LIB}" ]]; then
  # shellcheck source=lib/guard-lib.sh
  source "${GUARD_LIB}"
else
  emit "[harness] 경고: ${GUARD_LIB} 가 없어 보호 목록을 만들지 못했습니다. 이 호출은 아무것도 막지 않습니다."
  exit 0
fi

usage() {
  cat <<'USAGE'
사용법: guard-evaluation-tampering.sh [--help] [--list]

Claude Code 의 PreToolUse hook 으로 등록해 사용합니다. hook JSON 을 stdin 으로 받고
tool_input.file_path 를 보호 목록과 대조합니다.

보호 목록 = 코어 목록(이 스크립트 상단) + **로드된 모든** 언어 팩의 목록.
언어 팩 목록은 스택 감지 결과에 의존하지 않습니다. 감지에 의존하면 스택 미감지 저장소,
monorepo, kind 오판정에서 다른 언어의 평가 설정 파일이 조용히 무방비가 되기 때문입니다.
팩 패턴 이름은 언어 간에 겹치지 않으므로 합집합의 오탐 비용은 없습니다.

동작:
  - 차단 대상과 일치하면 exit 2 로 도구 호출을 막고 사유를 stderr 에 출력합니다.
  - 경고 대상과 일치하면 exit 0 으로 허용하되 stderr 에 경고를 남깁니다.
  - 어느 목록에도 없으면 아무것도 출력하지 않고 exit 0 합니다.
  - 팩을 하나도 로드하지 못했거나 팩이 계약을 어기면 그 사실을 stderr 에 남깁니다.
    보호 목록이 줄어든 상태를 조용히 통과시키지 않습니다.

옵션:
  --list   합쳐진 보호 목록과 감지된 스택·kind 를 출력합니다.

환경 변수:
  HARNESS_ALLOW_GUARDED_EDIT=1   차단을 1회 우회합니다. 사람 승인이나 harness-promote
                                 절차를 거친 변경에만 사용합니다.
  CLAUDE_PROJECT_DIR             프로젝트 루트. 없으면 스스로 탐색합니다.

이 hook 은 프로젝트의 harness.config 를 읽지 않습니다. 그 파일은 bash 이므로 읽으면
가드 프로세스 안에서 임의 명령이 실행되고, 한 줄로 가드를 무력화할 수 있기 때문입니다.
USAGE
}

MODE="hook"
case "${1:-}" in
  --help|-h)
    usage
    exit 0
    ;;
  --list)
    MODE="list"
    ;;
esac

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

PROJECT_ROOT="$(resolve_project_root)"

# --- 언어 팩 패턴 병합 --------------------------------------------------------------
# 감지를 하지 않고 로드된 모든 팩의 패턴을 합칩니다. 감지는 --list 표시용으로만 뒤에서 수행합니다.
# 팩은 이 프로세스에서 한 번만 로드하므로, 아래 프로세스 치환은 이미 로드된 함수와 배열을 물려받습니다.
LANG_STATUS="언어 팩 없음 (코어 목록만 적용)"
LANG_LOADED=0
if [[ -f "${DETECT_LIB}" ]]; then
  # shellcheck source=../scripts/lib/detect-stack.sh
  if source "${DETECT_LIB}" 2>/dev/null && declare -F harness_lang_load_packs >/dev/null 2>&1; then
    harness_lang_load_packs || true
    _pack_count=0
    if declare -p HARNESS_LANG_PACKS >/dev/null 2>&1; then
      _pack_count="${#HARNESS_LANG_PACKS[@]}"
    fi
    if [[ "${_pack_count}" -gt 0 ]]; then
      LANG_LOADED=1
      LANG_STATUS="팩 ${_pack_count}개 병합: ${HARNESS_LANG_PACKS[*]}"
      while IFS= read -r _p; do
        [[ -n "${_p}" ]] && HARNESS_PROTECTED_PATTERNS+=("${_p}")
      done < <(lang_all_protected_patterns 2>/dev/null || true)
      while IFS= read -r _p; do
        [[ -n "${_p}" ]] && HARNESS_WARN_PATTERNS+=("${_p}")
      done < <(lang_all_warn_patterns 2>/dev/null || true)
    else
      emit "[harness] 경고: 언어 팩을 하나도 로드하지 못했습니다. 언어별 평가 설정 파일(lint·타입·테스트 러너·아키텍처 규칙)이 보호되지 않습니다."
      emit "  확인: ./harness/hooks/guard-evaluation-tampering.sh --list"
    fi
  else
    emit "[harness] 경고: ${DETECT_LIB} 를 로드하지 못했습니다. 코어 목록만 적용합니다."
  fi
else
  emit "[harness] 경고: ${DETECT_LIB} 가 없습니다. 코어 목록만 적용합니다."
fi

if [[ "${HARNESS_LANG_PACK_PROBLEMS:-0}" -gt 0 ]]; then
  emit "[harness] 경고: 계약을 어긴 언어 팩 ${HARNESS_LANG_PACK_PROBLEMS}개를 비활성화했습니다. 그 언어의 보호 패턴이 적용되지 않습니다."
fi

if [[ "${MODE}" == "list" ]]; then
  _stack="(미측정)"; _kind="(미측정)"
  if [[ "${LANG_LOADED}" -eq 1 ]]; then
    _stack="$(detect_stack "${PROJECT_ROOT}" 2>/dev/null || true)"
    _kind="$(detect_kind "${PROJECT_ROOT}" "${_stack}" 2>/dev/null || true)"
  fi
  printf 'project_root: %s\n' "${PROJECT_ROOT}"
  printf 'language_packs: %s\n' "${LANG_STATUS}"
  printf 'detected_stack: %s (kind: %s)  ← 기본 verify 단계 선택용. 보호 목록에는 영향을 주지 않습니다.\n' \
    "${_stack:-unknown}" "${_kind:-unknown}"
  printf 'blocked:\n'
  printf '  %s\n' ${HARNESS_PROTECTED_PATTERNS[@]+"${HARNESS_PROTECTED_PATTERNS[@]}"}
  printf 'warned:\n'
  printf '  %s\n' ${HARNESS_WARN_PATTERNS[@]+"${HARNESS_WARN_PATTERNS[@]}"}
  exit 0
fi

read_stdin_payload() {
  if [[ -t 0 ]]; then
    printf '%s' ""
  else
    cat || true
  fi
}

# json_unescape <문자열> — JSON 문자열 리터럴의 이스케이프를 풉니다.
#
# 이것이 없으면 가드가 실질적으로 무력해집니다. Windows 경로는 페이로드에
# "C:\\WorkSpace\\...\\verify.sh" 로 옵니다(JSON 에서 백슬래시는 \\ 로 이스케이프됩니다).
# 풀지 않으면 to_relative 가 \ 하나하나를 / 로 바꿔 "C://WorkSpace//...//verify.sh" 가 되고,
# 루트 접두사 제거가 실패하며, '/' 를 포함한 모든 패턴(harness/scripts/*.sh, harness/rules/*,
# harness/hooks/*, evaluation/*, .harness/*)이 빗나갑니다.
# 파일명만 보는 패턴(harness.config)은 계속 걸리므로 가드가 살아 있는 것처럼 보입니다.
# jq 가 있으면 jq -r 이 이미 풀어 주므로 이 경로는 폴백에서만 씁니다.
# 근거: 2026-09-05 라운드, HLD-1 보고 + 직접 재현(슬래시 경로 exit 2 / 이스케이프 경로 exit 0).
#
# \u 시퀀스는 처리하지 않습니다. 경로에 거의 오지 않고, 처리하려면 fork 가 필요해
# hook 의 시간 예산(1초)을 해칩니다. 걸리지 않는 경우가 생기면 후보로 남깁니다.
json_unescape() {
  local s="${1-}"
  # \\ 를 먼저 자리표시자로 치웁니다. 그러지 않으면 "C:\\new" 의 \\ 와 n 이
  # 붙어 \n 으로 읽혀 개행이 됩니다.
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
    # 값 안의 \" 도 넘겨야 하므로 (\\.|[^"\\])* 로 읽고, 앞에서부터 키와 첫 콜론만 떼어냅니다.
    raw="$(printf '%s' "${payload}" \
      | grep -oE "\"${grep_key}\"[[:space:]]*:[[:space:]]*\"(\\\\.|[^\"\\\\])*\"" \
      | head -n 1 \
      | sed -E 's/^"[^"]*"[[:space:]]*:[[:space:]]*"//; s/"$//' || true)"
    value="$(json_unescape "${raw}")"
  fi
  printf '%s' "${value}"
}

# to_relative 와 matches_any 는 hooks/lib/guard-lib.sh 에 있습니다.
# 여기에 복제본을 두지 마십시오. 갈라진 복제본이 verify 를 통과하는 문제는
# improvement-log/2026-09-05-002 가 기록한 유형입니다.

PAYLOAD="$(read_stdin_payload)"
FILE_PATH="$(json_field "${PAYLOAD}" '.tool_input.file_path' 'file_path')"
if [[ -z "${FILE_PATH}" ]]; then
  FILE_PATH="$(json_field "${PAYLOAD}" '.tool_input.notebook_path' 'notebook_path')"
fi

# --- 셸 명령 검사 -------------------------------------------------------------
# file_path 만 보면 가드가 Edit 계열 도구에만 걸립니다. 셸 한 줄이면 그대로 우회됩니다.
#   printf '{"status":"pass"}' > .harness/verify.json
#   sed -i 's/threshold=90/threshold=0/' harness.config
# 그래서 명령 문자열도 봅니다. 다만 읽기는 막지 않습니다. cat·grep·git diff 로 보호
# 파일을 보는 것은 정상 작업이므로, **변경을 일으키는 구문과 함께 나타날 때만** 막습니다.
# 완전한 셸 파서가 아니므로 우회는 여전히 가능합니다. 이 검사는 실수와 손쉬운
# 지름길을 막는 것이지 적대적 회피를 막는 것이 아닙니다. 그 한계는 README 에 적었습니다.
SHELL_COMMAND="$(json_field "${PAYLOAD}" '.tool_input.command' 'command')"
if [[ -z "${FILE_PATH}" && -n "${SHELL_COMMAND}" ]]; then
  # 명령 전체에서 경로를 찾으면 오탐이 큽니다.
  # `bash harness/scripts/verify.sh >/dev/null` 은 보호 파일을 실행할 뿐인데도 걸립니다.
  # 그래서 **변경 구문이 실제로 겨냥하는 대상**만 뽑습니다.
  _targets="$(
    # `> 파일`, `>> 파일` 의 리다이렉션 대상. `2>&1` 은 대상이 &1 이라 걸리지 않습니다.
    printf '%s' "${SHELL_COMMAND}" | grep -oE '>>?[[:space:]]*[^|&;<>[:space:]]+' | sed -E 's/^>>?[[:space:]]*//'
    # `tee [-a] 파일`
    printf '%s' "${SHELL_COMMAND}" | grep -oE '\btee\b([[:space:]]+-[a-zA-Z]+)*[[:space:]]+[^|&;<>[:space:]]+' | sed -E 's/.*[[:space:]]//'
    # 제자리 편집(sed -i, perl -pi)은 대상이 인자 어디에나 오므로 경로 같은 토큰을 전부 봅니다.
    if printf '%s' "${SHELL_COMMAND}" | grep -qE '\bsed\b[^|;]*[[:space:]]-i|\bperl\b[^|;]*[[:space:]]-[a-z]*i'; then
      printf '%s' "${SHELL_COMMAND}" | tr '[:space:]' '\n' | grep -E '[./]' || true
    fi
    # 같은 일을 다른 이름으로 하는 명령들. cp 로 보호 파일을 덮어쓰는 경로가 실제로
    # 열려 있었고, 한 세션에서 10건이 그렇게 통과했습니다. 대상이 인자 어디에 오는지
    # 형태가 제각각이라 제자리 편집과 같은 방식으로 경로 같은 토큰을 전부 봅니다.
    # 보호 파일을 읽어서 다른 곳으로 복사하는 경우까지 걸리지만, 근거 없이 여는
    # 것보다 닫는 쪽이 맞습니다.
    #
    # 이 목록은 닫히지 않습니다. python -c, node -e, make, 임의 스크립트는 여전히
    # 통과합니다. 열거로 닫으려 하지 마십시오. 남는 경로는 사후 검출
    # (detect-guarded-change.sh)과 CI(.github/workflows/harness.yml)가 담당합니다.
    if printf '%s' "${SHELL_COMMAND}" | grep -qE '\b(cp|mv|install|truncate|dd|rsync|ln)\b'; then
      printf '%s' "${SHELL_COMMAND}" | tr '[:space:]' '\n' | grep -E '[./]' || true
    fi
  )"
  _hit=""
  while IFS= read -r _tok; do
    [[ -n "${_tok}" ]] || continue
    _rel="$(to_relative "${PROJECT_ROOT}" "${_tok}")"
    _rel="${_rel#./}"
    if _m="$(matches_any "${_rel}" "${_rel##*/}" ${HARNESS_PROTECTED_PATTERNS[@]+"${HARNESS_PROTECTED_PATTERNS[@]}"})"; then
      _hit="${_rel}|${_m}"
      break
    fi
  done <<< "${_targets}"
  if [[ -n "${_hit}" ]]; then
    if [[ "${HARNESS_ALLOW_GUARDED_EDIT:-}" == "1" ]]; then
      guard_log_event "${PROJECT_ROOT}" bypass "${_hit%%|*}" "셸 명령, 패턴 ${_hit##*|}, HARNESS_ALLOW_GUARDED_EDIT=1"
      emit "[harness] HARNESS_ALLOW_GUARDED_EDIT=1 로 보호 파일을 건드리는 셸 명령을 허용했습니다: ${_hit%%|*}"
      exit 0
    fi
    guard_log_event "${PROJECT_ROOT}" block "${_hit%%|*}" "셸 명령, 패턴 ${_hit##*|}"
    emit "[harness] 셸 명령을 차단했습니다: 보호 대상 ${_hit%%|*} 을(를) 변경하려 합니다 (패턴 ${_hit##*|})."
    emit "명령: ${SHELL_COMMAND}"
    emit "평가·게이트 파일을 셸로 우회해 고치는 것은 Edit 로 고치는 것과 같습니다."
    emit "다음 조치: 이번 실패는 대상 코드에서 고치고, 기준 자체가 잘못되었다면 improvement candidate 를 남깁니다."
    emit "승인된 변경이라면 HARNESS_ALLOW_GUARDED_EDIT=1 을 붙여 다시 실행합니다."
    exit 2
  fi
fi

# 파일 경로가 없는 도구 호출은 이 hook 의 관심사가 아닙니다.
if [[ -z "${FILE_PATH}" ]]; then
  exit 0
fi

REL_PATH="$(to_relative "${PROJECT_ROOT}" "${FILE_PATH}")"
BASE_NAME="${REL_PATH##*/}"

MATCHED=""
if MATCHED="$(matches_any "${REL_PATH}" "${BASE_NAME}" ${HARNESS_PROTECTED_PATTERNS[@]+"${HARNESS_PROTECTED_PATTERNS[@]}"})"; then
  if [[ "${HARNESS_ALLOW_GUARDED_EDIT:-}" == "1" ]]; then
    guard_log_event "${PROJECT_ROOT}" bypass "${REL_PATH}" "파일 편집, 패턴 ${MATCHED}, HARNESS_ALLOW_GUARDED_EDIT=1"
    emit "[harness] HARNESS_ALLOW_GUARDED_EDIT=1 로 보호 파일 변경을 허용했습니다: ${REL_PATH} (패턴 ${MATCHED})"
    emit "이 변경은 사람 승인 또는 harness-promote 절차의 기록으로 남겨야 합니다."
    exit 0
  fi
  guard_log_event "${PROJECT_ROOT}" block "${REL_PATH}" "파일 편집, 패턴 ${MATCHED}"
  emit "[harness] 변경을 차단했습니다: ${REL_PATH}"
  emit "이 경로는 평가·게이트를 규정하는 보호 대상입니다(일치 패턴: ${MATCHED})."
  emit "평가 기준을 스스로 고쳐 통과시키는 것은 개선이 아니라 평가 조작입니다."
  emit "다음 조치:"
  emit "  1. 이번 실패는 대상 코드에서 고칩니다."
  emit "  2. 기준 자체가 잘못되었다고 판단하면 improvement candidate 를 남깁니다(harness/subagents/harness-reviewer.md)."
  emit "  3. 기준 변경은 harness-promote 절차와 사람 검토를 거쳐 적용합니다."
  emit "  4. 승인된 변경이라면 HARNESS_ALLOW_GUARDED_EDIT=1 을 붙여 다시 실행합니다."
  exit 2
fi

if MATCHED="$(matches_any "${REL_PATH}" "${BASE_NAME}" ${HARNESS_WARN_PATTERNS[@]+"${HARNESS_WARN_PATTERNS[@]}"})"; then
  guard_log_event "${PROJECT_ROOT}" warn "${REL_PATH}" "패턴 ${MATCHED}"
  emit "[harness] 경고: ${REL_PATH} 는 평가 결과에 영향을 줄 수 있는 파일입니다(일치 패턴: ${MATCHED})."
  emit "검증 명령, 임계값, 테스트 범위를 약화시키는 변경인지 확인하고, 그렇다면 되돌립니다."
  exit 0
fi

exit 0
