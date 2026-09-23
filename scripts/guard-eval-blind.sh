#!/usr/bin/env bash
# guard-eval-blind.sh — PreToolUse hook.
# improvement-log 2026-09-17-001: 대표 task 를 새 세션으로 실행하는 동안, 실행
# 에이전트가 evaluation/tasks(합격 기준)나 evaluation/runs(지난 판정 근거·평가자가
# 심은 결함)를 스스로 읽어 blind 조건이 깨진 사고가 있었다(REP-5, REP-8-r2).
#
# improvement-log 2026-09-22-001: 2026-09-21 REP-4 6차 실행에서는 그 두 경로가
# 아니어도 기준이 새는 것을 확인했다 — 실행 에이전트가 루트 evaluation/README.md
# (task ID·판정 요약)를 읽고, improvement-log/ 를 주제어로 검색해 기존 후보에
# 복제된 합격 기준·관측 방법을 읽었다. 이 스크립트는 저장소 루트에 마커 파일
# `.eval-blind` 가 있을 때만 다음 두 범주를 차단한다 — 평상시 작업(리뷰, 회귀
# 재현 등)은 이 경로를 자유롭게 읽어야 하므로 상시로 막지 않는다.
#
#   1. 루트 evaluation/ 전체(경로 성분 evaluation). harness/evaluation(번들의
#      rubric·템플릿)과 packages/evaluation(제품 패키지)은 막지 않는다.
#   2. 루트 improvement-log/ 의 마커 이전 항목. harness/improvement-log(번들의
#      schema·템플릿·README)는 막지 않는다. 마커 뒤에 새로 생긴 파일(실행자가
#      improvement-log.sh new 로 발급한 후보)은 REP-7 합격 기준이 후보 1건
#      생성을 요구하므로 막지 않는다. improvement-log.sh list 는 기존 항목의
#      symptom 요약을 출력해 새므로 막지만, new·validate 는 자기 후보만
#      다루므로 막지 않는다.
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
#   2 — 마커가 있고 위 두 범주 중 하나를 참조함(차단, stderr 사유).
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

# 검사 대상 필드. 있는 것만 봅니다. file_path·path·notebook_path 는 값 전체가 경로이고,
# command·pattern·glob 은 경로가 자유 텍스트 안에 섞여 옵니다 — 두 종류는 판정 방식이
# 다르므로 아래에서 따로 다룹니다.
FIELD_NAMES=(file_path path pattern command glob notebook_path)
PATH_LIKE_FIELD_NAMES=" file_path path notebook_path "
FIELD_VALUES=()
for _name in "${FIELD_NAMES[@]}"; do
  FIELD_VALUES+=("$(json_field "${PAYLOAD}" ".tool_input.${_name}" "${_name}")")
done

# normalize_slashes <값> — 역슬래시를 슬래시로 바꿔 매칭만 단순하게 만듭니다(실제
# 파일시스템 접근에는 원래 ROOT 를 그대로 씁니다 — Git Bash 는 혼용 구분자를 받아들입니다).
normalize_slashes() {
  printf '%s' "${1//\\//}"
}

# resolve_under_root <값> — 상대경로면 ROOT 를 붙이고, 절대경로(드라이브 문자 포함)면
# 그대로 둡니다. mtime 비교를 위한 실제 파일시스템 경로를 만듭니다.
resolve_under_root() {
  local v; v="$(normalize_slashes "$1")"
  case "$v" in
    /*|[A-Za-z]:*) printf '%s' "$v" ;;
    *) printf '%s/%s' "${ROOT}" "$v" ;;
  esac
}

# is_pre_marker_file <파일경로> — 파일이 존재하고 그 수정 시각이 .eval-blind 의
# 수정 시각보다 이르거나 같으면 참입니다. 존재하지 않으면(아직 안 생긴 후보) 거짓입니다.
is_pre_marker_file() {
  local p="$1" fmt mmt
  [[ -f "$p" ]] || return 1
  fmt="$(stat -c %Y -- "$p" 2>/dev/null || true)"
  mmt="$(stat -c %Y -- "${MARKER_PATH}" 2>/dev/null || true)"
  [[ -n "$fmt" && -n "$mmt" ]] || return 1
  (( fmt <= mmt ))
}

# is_root_evaluation_path <값> — 경로 전체가 루트 evaluation/ 를 가리키는지 봅니다.
# harness/evaluation·packages/evaluation 아래는 제외합니다(경로 성분 기준, AR-8 근거는
# 아니고 evaluation/README.md 등 접두사 뒤 성분이 evaluation 인지로 판단합니다).
is_root_evaluation_path() {
  local v; v="$(normalize_slashes "$1")"
  if [[ "$v" =~ (^|/)harness/evaluation(/|$) ]]; then
    return 1
  fi
  if [[ "$v" =~ (^|/)packages/evaluation(/|$) ]]; then
    return 1
  fi
  [[ "$v" =~ (^|/)evaluation(/|$) ]]
}

# is_root_improvement_log_path <값> — 경로 전체가 루트 improvement-log/ 를
# 가리키는지 봅니다. harness/improvement-log 아래는 제외합니다.
is_root_improvement_log_path() {
  local v; v="$(normalize_slashes "$1")"
  if [[ "$v" =~ (^|/)harness/improvement-log(/|$) ]]; then
    return 1
  fi
  [[ "$v" =~ (^|/)improvement-log(/|$) ]]
}

# is_improvement_log_dir_itself <값> — 값이 improvement-log 디렉터리 자체를
# 가리키고 그 아래 특정 파일까지는 지정하지 않았는지 봅니다(예: Grep 도구의 path).
is_improvement_log_dir_itself() {
  local v; v="$(normalize_slashes "$1")"
  v="${v%/}"
  [[ "$v" == "improvement-log" || "$v" == */improvement-log ]]
}

# text_has_root_evaluation_ref <텍스트> — command·pattern·glob 처럼 경로가 자유
# 텍스트 안에 섞여 오는 필드에서 루트 evaluation/ 참조를 찾습니다. harness/evaluation·
# packages/evaluation 부분 문자열을 먼저 지우고 남은 것에서 찾습니다.
text_has_root_evaluation_ref() {
  local v stripped
  v="$(normalize_slashes "$1")"
  stripped="${v//harness\/evaluation/}"
  stripped="${stripped//packages\/evaluation/}"
  [[ "$stripped" =~ (^|[^A-Za-z0-9_.-])evaluation(/|[^A-Za-z0-9_.-]|$) ]]
}

# text_has_root_improvement_log_ref <텍스트> — 위와 같은 방식으로 루트
# improvement-log/ 참조를 찾습니다. harness/improvement-log 는 먼저 지웁니다.
text_has_root_improvement_log_ref() {
  local v stripped
  v="$(normalize_slashes "$1")"
  stripped="${v//harness\/improvement-log/}"
  [[ "$stripped" =~ (^|[^A-Za-z0-9_.-])improvement-log(/|[^A-Za-z0-9_.-]|$) ]]
}

# improvement_log_referenced_files <텍스트> — "improvement-log/<파일명>.<확장자>"
# 형태로 명시된 파일명만 한 줄씩 뽑습니다(디렉터리 전체 참조는 파일명이 없어 안 뽑힙니다).
improvement_log_referenced_files() {
  local v; v="$(normalize_slashes "$1")"
  printf '%s\n' "$v" \
    | grep -oE 'improvement-log/[A-Za-z0-9_.-]+\.[A-Za-z0-9]+' \
    | sed -E 's#^improvement-log/##'
}

# check_command_like_improvement_log <텍스트> — 루트 improvement-log/ 참조가 있을 때,
# 명시된 파일명이 전부 마커 뒤에 생긴 파일이면 허용(거짓)하고, 디렉터리 전체를 훑거나
# 판정하기 어려우면 차단(참)합니다.
check_command_like_improvement_log() {
  local v="$1"
  text_has_root_improvement_log_ref "$v" || return 1
  local file resolved any_file=0 allow_all=1
  while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    any_file=1
    resolved="${ROOT}/improvement-log/${file}"
    if [[ ! -f "$resolved" ]] || is_pre_marker_file "$resolved"; then
      allow_all=0
    fi
  done < <(improvement_log_referenced_files "$v")
  if [[ "$any_file" -eq 1 && "$allow_all" -eq 1 ]]; then
    return 1
  fi
  return 0
}

# is_improvement_log_list_invocation <텍스트> — improvement-log.sh 의 list 하위
# 명령 호출인지 봅니다. new·validate 는 이 패턴에 걸리지 않습니다.
is_improvement_log_list_invocation() {
  [[ "$1" =~ improvement-log\.sh[[:space:]]+list([[:space:]]|$) ]]
}

# field_is_blind <필드이름> <값> — 이 필드 값이 blind 조건 위반인지 판정합니다.
field_is_blind() {
  local field="$1" v="$2" resolved
  [[ -n "$v" ]] || return 1

  if is_improvement_log_list_invocation "$v"; then
    return 0
  fi

  if [[ "${PATH_LIKE_FIELD_NAMES}" == *" ${field} "* ]]; then
    if is_root_evaluation_path "$v"; then
      return 0
    fi
    if is_root_improvement_log_path "$v"; then
      if is_improvement_log_dir_itself "$v"; then
        return 0
      fi
      resolved="$(resolve_under_root "$v")"
      if is_pre_marker_file "$resolved"; then
        return 0
      fi
    fi
    return 1
  fi

  if text_has_root_evaluation_ref "$v"; then
    return 0
  fi
  if check_command_like_improvement_log "$v"; then
    return 0
  fi
  return 1
}

HIT_FIELD=""
HIT_VALUE=""
for _i in "${!FIELD_NAMES[@]}"; do
  _name="${FIELD_NAMES[$_i]}"
  _v="${FIELD_VALUES[$_i]}"
  [[ -n "${_v}" ]] || continue
  if field_is_blind "${_name}" "${_v}"; then
    HIT_FIELD="${_name}"
    HIT_VALUE="${_v}"
    break
  fi
done

if [[ -z "${HIT_FIELD}" ]]; then
  exit 0
fi

# 차단마다 한 줄을 남깁니다 — blind 조건이 실제로 작동했다는 증거입니다
# (improvement-log 2026-09-17-001 · 2026-09-22-001 의 regression_check).
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || printf 'unknown')"
printf '%s\t%s\t%s=%s\n' "${TS}" "${TOOL_NAME}" "${HIT_FIELD}" "${HIT_VALUE}" >> "${LOG_PATH}"

emit "[harness] 평가 실행 중에는 evaluation/ 전체와 improvement-log/ 의 기존 항목을 읽지 않습니다: ${HIT_VALUE} — 이 실행의 blind 조건입니다(improvement-log 2026-09-17-001, 2026-09-22-001). 새 개선 후보를 발급하고 쓰는 것(harness/scripts/improvement-log.sh new, 그리고 마커 뒤에 생긴 파일 읽기·쓰기)은 계속 허용됩니다 — 막은 것은 기존 항목과 평가 문서를 읽는 것뿐입니다."
exit 2
