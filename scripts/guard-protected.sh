#!/usr/bin/env bash
# guard-protected.sh — PreToolUse hook 래퍼.
#
# improvement-log 2026-09-23-001: 보호 파일은 에이전트가 쓸 수 없고 사람이 커밋한다.
# 그런데 2026-09-24~25 라운드에서 사람이 실행해야 했던 블록 12회 중 3회가 조용히
# 실패했고(브랜치 불일치, gh 버그), 블록 내용은 대부분 실행 기록(evaluation/runs/**)
# 이었다 — 그것은 게이트가 아니라 증거다. 게이트(합격 기준·harness.config·CI 워크플로·
# 훅 설정)와 증거를 같은 취급으로 묶어 둔 것이 마찰의 원인이다.
#
# 이 래퍼는 stdin 의 hook JSON 이 참조하는 보호 경로가 **오직** 루트 evaluation/runs/
# 아래일 때만 직접 허용한다(그 예외를 지나갈 때마다 .harness/guard-evidence-allow.log
# 에 한 줄을 남긴다). 그 밖의 모든 경우는 번들 harness/hooks/guard-evaluation-tampering.sh
# 에 stdin 을 그대로 넘겨 위임하고, 그 종료 코드와 stderr 를 그대로 전달한다 — 번들 가드의
# 목록·메시지를 다시 만들지 않는다. 한 명령이 증거 경로와 게이트 경로를 함께 건드리면
# 판정하기 어려우므로 위임한다(즉 막는다).
#
# harness/ 아래는 읽기만 한다 — 번들 가드 자체를 고치지 않는다.
#
# 입력 형식과 파싱 관례(jq 있으면 jq, 없으면 grep 폴백)는 scripts/guard-eval-blind.sh 와
# harness/hooks/guard-evaluation-tampering.sh 의 read_stdin_payload · json_field 를 그대로
# 따른다(번들 파일 자체는 고치지 않는다).
#
# 보호 패턴 목록과 경로 정규화·일치 판정(to_relative · matches_any)은
# harness/hooks/lib/guard-lib.sh 의 정본을 그대로 source 해서 쓴다 — 여기에 목록을
# 복제하면 한쪽만 갱신되어 틈이 생긴다(improvement-log/2026-09-05-002 유형).
#
# 사용:
#   scripts/guard-protected.sh                # Claude Code PreToolUse hook, stdin=hook JSON
#   scripts/guard-protected.sh --root <경로>   # 테스트용: 저장소 루트를 바꿔 지정
#
# 종료 코드:
#   0 — 증거 전용 예외로 허용, 또는 번들 가드에 위임한 결과가 허용.
#   2 — 번들 가드에 위임한 결과가 차단(stderr 사유는 번들 가드가 낸 그대로).
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
      emit "guard-protected: unknown argument: $1"
      exit 2
      ;;
  esac
done
ROOT="${ROOT%/}"

BUNDLE_GUARD="${ROOT}/harness/hooks/guard-evaluation-tampering.sh"
GUARD_LIB="${ROOT}/harness/hooks/lib/guard-lib.sh"
ALLOW_LOG="${ROOT}/.harness/guard-evidence-allow.log"

read_stdin_payload() {
  if [[ -t 0 ]]; then
    printf '%s' ""
  else
    cat || true
  fi
}

PAYLOAD="$(read_stdin_payload)"
if [[ -z "${PAYLOAD}" ]]; then
  # hook 오류(빈 입력)가 도구 호출을 막으면 안 됩니다. 위임할 것도 없습니다.
  exit 0
fi

# json_unescape <문자열> — 근거와 구현은 harness/hooks/guard-evaluation-tampering.sh 의
# 동명 함수와 같습니다. Windows 경로("C:\\WorkSpace\\...")를 풀지 않으면 '/' 를 포함한
# 패턴이 전부 빗나갑니다.
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

# --- 위임(번들 가드에 stdin 을 그대로 넘김) ------------------------------------------
delegate() {
  if [[ ! -f "${BUNDLE_GUARD}" ]]; then
    emit "[harness] guard-protected: 번들 가드 ${BUNDLE_GUARD} 가 없어 검사를 건너뜁니다."
    return 0
  fi
  local ec=0
  set +e
  printf '%s' "${PAYLOAD}" | CLAUDE_PROJECT_DIR="${ROOT}" bash "${BUNDLE_GUARD}"
  ec=$?
  set -e
  return "${ec}"
}

# guard-lib.sh 가 없으면 보호 패턴도 정규화·일치 함수도 없어 증거 판정을 할 수 없습니다.
# 이때는 판정하기 어려운 쪽 — 위임 — 을 택합니다.
if [[ ! -f "${GUARD_LIB}" ]]; then
  emit "[harness] guard-protected: ${GUARD_LIB} 가 없어 증거 판정을 건너뛰고 위임합니다."
  delegate
  exit $?
fi

# shellcheck source=/dev/null
source "${GUARD_LIB}"

# normalize_slashes <값> — 역슬래시를 슬래시로 바꿔 매칭만 단순하게 만듭니다.
normalize_slashes() {
  printf '%s' "${1//\\//}"
}

# is_root_evaluation_runs_path <rel> — 루트 evaluation/runs/ 아래를 정확히 가리키는지.
# harness/evaluation·packages/evaluation 은 먼저 제외합니다.
is_root_evaluation_runs_path() {
  local v; v="$(normalize_slashes "$1")"
  if [[ "$v" =~ (^|/)harness/evaluation(/|$) ]]; then
    return 1
  fi
  if [[ "$v" =~ (^|/)packages/evaluation(/|$) ]]; then
    return 1
  fi
  [[ "$v" =~ (^|/)evaluation/runs(/|$) ]]
}

# classify_token <값> — 값이 참조하는 보호 경로를 분류해 전역 플래그를 올립니다.
#   evidence: 루트 evaluation/runs/ 아래(오직 그 경우만)
#   other:    그 밖의 어떤 보호 패턴이든(코어 목록 기준)
# 둘 다 아니면 아무 것도 올리지 않습니다(관심 밖 — 위임해도 결국 허용됩니다).
SAW_EVIDENCE=0
SAW_OTHER=0
EVIDENCE_VALUE=""

classify_token() {
  local raw="$1" v rel base matched
  [[ -n "${raw}" ]] || return 0
  v="$(normalize_slashes "${raw}")"
  v="${v#./}"
  rel="$(to_relative "${ROOT}" "${v}")"
  base="${rel##*/}"
  if matched="$(matches_any "${rel}" "${base}" "${HARNESS_PROTECTED_PATTERNS[@]}")"; then
    if [[ "${matched}" == "evaluation/*" ]] && is_root_evaluation_runs_path "${rel}"; then
      SAW_EVIDENCE=1
      [[ -n "${EVIDENCE_VALUE}" ]] || EVIDENCE_VALUE="${raw}"
    else
      SAW_OTHER=1
    fi
  fi
}

# --- 경로 그대로인 필드: 값 전체가 경로입니다 -----------------------------------------
for _field in file_path path notebook_path; do
  _v="$(json_field "${PAYLOAD}" ".tool_input.${_field}" "${_field}")"
  classify_token "${_v}"
done

# --- 자유 텍스트 필드: 경로가 문장 안에 섞여 옵니다 -----------------------------------
for _field in command pattern glob; do
  _v="$(json_field "${PAYLOAD}" ".tool_input.${_field}" "${_field}")"
  [[ -n "${_v}" ]] || continue
  while IFS= read -r _tok; do
    _tok="${_tok//[\'\"();,]/}"
    classify_token "${_tok}"
  done < <(printf '%s' "${_v}" | tr '[:space:]' '\n' | grep -E '[./]' || true)
done

if [[ "${SAW_EVIDENCE}" -eq 1 && "${SAW_OTHER}" -eq 0 ]]; then
  mkdir -p "$(dirname -- "${ALLOW_LOG}")" 2>/dev/null || true
  TS="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || printf 'unknown')"
  printf '%s\t%s\t%s\n' "${TS}" "${TOOL_NAME}" "${EVIDENCE_VALUE}" >> "${ALLOW_LOG}" 2>/dev/null || true
  exit 0
fi

delegate
exit $?
