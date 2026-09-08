#!/usr/bin/env bash
# detect-guarded-change.sh — PostToolUse hook. 보호 파일이 실제로 바뀌었는지 사후에 봅니다.
#
# 왜 사전 차단만으로는 부족한가
#   PreToolUse 가드는 명령 문자열을 보고 "바꿀 것 같은가" 를 추정합니다. 그 추정은 두 방향으로
#   틀립니다. cp·mv·python -c·make·임의 스크립트는 놓치고(미탐), 인용부호 안의 경로나
#   heredoc 본문은 잘못 잡습니다(오탐). 열거로는 닫히지 않습니다. bash 를 허용하는 순간
#   전부 허용한 것이고, 쓰기가 hook 이 읽을 수 없는 프로그램 안에서 일어날 수도 있습니다.
#   근거: improvement-log/2026-09-05-004, 2026-09-05-005.
#
# 이 hook 은 추정하지 않습니다
#   도구 호출이 끝난 뒤 보호 파일의 내용 해시를 직접 비교합니다. 무엇이 바꿨는지와
#   무관하게 바뀐 사실이 드러나므로 미탐이 없고, 명령을 파싱하지 않으므로 오탐도 없습니다.
#   대신 막지는 못합니다. 강제력은 낮고 관측은 완전합니다. 둘은 대체 관계가 아니라 짝입니다.
#
# 이 hook 이 보장하지 않는 것
#   저장소 밖에서 도는 검사가 아니면 결정적인 우회는 여전히 가능합니다. hook 자체를
#   등록에서 빼면 이 검출도 사라집니다. 실제 무결성 보장은 CI 가 담당합니다.
#
# exit 0 만 씁니다. PostToolUse 는 이미 일어난 일을 되돌리지 못하므로 차단이 의미 없습니다.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
GUARD_LIB="${SCRIPT_DIR}/lib/guard-lib.sh"
DETECT_LIB="${HARNESS_DIR}/scripts/lib/detect-stack.sh"

emit() { printf '%s\n' "$*" >&2; }

usage() {
  cat <<'USAGE'
사용법: detect-guarded-change.sh [--help] [--status]

Claude Code 의 PostToolUse hook 으로 등록해 사용합니다.

동작:
  - 보호 파일의 내용 해시를 .harness/guard-snapshot.tsv 와 비교합니다.
  - 처음 실행이면 스냅숏만 만들고 아무것도 보고하지 않습니다.
  - 변경을 발견하면 stderr 로 알리고 .harness/guard-events.log 에 append 합니다.
  - git 저장소가 아니면 아무것도 하지 않습니다. 해시할 기준이 없습니다.

옵션:
  --status  현재 감시 중인 보호 파일 수와 기록 경로를 출력합니다.

환경 변수:
  CLAUDE_PROJECT_DIR            프로젝트 루트.
  HARNESS_DETECT_SKIP_PACKS=1   언어 팩 패턴 병합을 건너뜁니다(빠르지만 좁아집니다).
USAGE
}

MODE="hook"
case "${1:-}" in
  --help|-h) usage; exit 0 ;;
  --status) MODE="status" ;;
esac

[[ -f "${GUARD_LIB}" ]] || exit 0
# shellcheck source=lib/guard-lib.sh
source "${GUARD_LIB}"

resolve_project_root() {
  if [[ -n "${CLAUDE_PROJECT_DIR:-}" && -d "${CLAUDE_PROJECT_DIR}" ]]; then
    printf '%s\n' "${CLAUDE_PROJECT_DIR}"
    return 0
  fi
  git rev-parse --show-toplevel 2>/dev/null || printf '%s\n' "$(cd -- "${HARNESS_DIR}/.." && pwd)"
}

ROOT="$(resolve_project_root)"
git -C "${ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# --- 언어 팩 패턴 병합 -----------------------------------------------------------
# 사전 차단과 같은 목록을 봐야 합니다. 목록이 다르면 한쪽이 막는 것을 다른 쪽이 보지 못합니다.
#
# 팩 5개를 source 하는 데 이 플랫폼에서 약 0.38초가 듭니다. 이 hook 은 도구 호출마다
# 도므로 그 비용을 매번 내지 않습니다. 병합 결과를 캐시하고, 캐시보다 새 lang.sh 나
# guard-lib.sh 가 있을 때만 다시 만듭니다. 신선도 판정은 [[ -nt ]] 라 fork 가 없습니다.
# 캐시를 지우면 다음 실행이 다시 만듭니다. 캐시가 낡으면 좁아지는 것이 아니라
# 다시 계산되므로, 실패 방향이 fail-closed 입니다.
PATTERN_CACHE="${ROOT}/.harness/guard-patterns.cache"

pattern_cache_fresh() {
  local f
  [[ -f "${PATTERN_CACHE}" ]] || return 1
  [[ "${GUARD_LIB}" -nt "${PATTERN_CACHE}" ]] && return 1
  for f in "${HARNESS_DIR}"/language/*/lang.sh; do
    [[ -f "${f}" ]] || continue
    [[ "${f}" -nt "${PATTERN_CACHE}" ]] && return 1
  done
  return 0
}

if [[ "${HARNESS_DETECT_SKIP_PACKS:-}" != "1" ]]; then
  if pattern_cache_fresh; then
    while IFS= read -r _p; do
      [[ -n "${_p}" ]] && HARNESS_PROTECTED_PATTERNS+=("${_p}")
    done < "${PATTERN_CACHE}"
  elif [[ -f "${DETECT_LIB}" ]]; then
    if source "${DETECT_LIB}" 2>/dev/null && declare -F harness_lang_load_packs >/dev/null 2>&1; then
      harness_lang_load_packs || true
      _pack_patterns="$(lang_all_protected_patterns 2>/dev/null || true)"
      while IFS= read -r _p; do
        [[ -n "${_p}" ]] && HARNESS_PROTECTED_PATTERNS+=("${_p}")
      done <<< "${_pack_patterns}"
      if mkdir -p "${ROOT}/.harness" 2>/dev/null; then
        printf '%s\n' "${_pack_patterns}" >> "${PATTERN_CACHE}.tmp" 2>/dev/null || true
        mv -f "${PATTERN_CACHE}.tmp" "${PATTERN_CACHE}" 2>/dev/null || true
      fi
    fi
  fi
fi

# --- 감시 대상 열거 ---------------------------------------------------------------
# git 이 아는 파일만 봅니다. 추적 파일은 index blob 해시를 그대로 쓰고(파일을 읽지 않습니다),
# index 와 다른 파일과 미추적 파일만 실제 내용을 해시합니다. lib/common.sh 의
# harness_tree_fingerprint 와 같은 전략이며, fork 수는 보통 3회 안쪽입니다.
is_watched() {
  local rel="$1" base="${1##*/}"
  matches_any "${rel}" "${base}" ${HARNESS_DETECT_EXCLUDE_PATTERNS[@]+"${HARNESS_DETECT_EXCLUDE_PATTERNS[@]}"} >/dev/null && return 1
  matches_any "${rel}" "${base}" ${HARNESS_PROTECTED_PATTERNS[@]+"${HARNESS_PROTECTED_PATTERNS[@]}"} >/dev/null
}

current_state() {
  local p line meta blob
  local -A dirty=()
  while IFS= read -r -d '' p; do dirty["${p}"]=1; done \
    < <(git -C "${ROOT}" diff --name-only -z 2>/dev/null)
  while IFS= read -r -d '' line; do
    meta="${line%%$'\t'*}"
    p="${line#*$'\t'}"
    is_watched "${p}" || continue
    [[ -f "${ROOT}/${p}" ]] || { printf '%s\t%s\n' "${p}" "deleted"; continue; }
    if [[ -n "${dirty[$p]:-}" ]]; then
      blob="$(git -C "${ROOT}" hash-object -- "${ROOT}/${p}" 2>/dev/null || printf 'unhashable')"
    else
      blob="${meta#* }"; blob="${blob%% *}"
    fi
    printf '%s\t%s\n' "${p}" "${blob}"
  done < <(git -C "${ROOT}" ls-files -s -z 2>/dev/null)
  while IFS= read -r -d '' p; do
    is_watched "${p}" || continue
    [[ -f "${ROOT}/${p}" ]] || continue
    printf '%s\t%s\n' "${p}" "$(git -C "${ROOT}" hash-object -- "${ROOT}/${p}" 2>/dev/null || printf 'unhashable')"
  done < <(git -C "${ROOT}" ls-files -o --exclude-standard -z 2>/dev/null)
}

STATE_DIR="${ROOT}/.harness"
SNAP_PATH="${STATE_DIR}/guard-snapshot.tsv"
NOW="$(current_state | LC_ALL=C sort)"

if [[ "${MODE}" == "status" ]]; then
  printf 'project_root: %s\n' "${ROOT}"
  printf 'watched_files: %s\n' "$(printf '%s' "${NOW}" | grep -c . || true)"
  printf 'snapshot: %s\n' "${SNAP_PATH}"
  printf 'events: %s\n' "${STATE_DIR}/guard-events.log"
  exit 0
fi

mkdir -p "${STATE_DIR}" 2>/dev/null || exit 0

save_snapshot() { printf '%s\n' "${NOW}" >> "${SNAP_PATH}.tmp" 2>/dev/null || true; }

# 처음 실행이면 기준만 만듭니다. 기준이 없는 상태를 변경으로 보고하면 첫 호출이 전부 경보가 됩니다.
if [[ ! -f "${SNAP_PATH}" ]]; then
  : > "${SNAP_PATH}.tmp" 2>/dev/null || exit 0
  save_snapshot
  mv -f "${SNAP_PATH}.tmp" "${SNAP_PATH}" 2>/dev/null || true
  exit 0
fi

BEFORE="$(cat -- "${SNAP_PATH}" 2>/dev/null || true)"
if [[ "${BEFORE}" == "${NOW}" ]]; then
  exit 0
fi

# 달라진 줄만 뽑습니다. 경로별로 무엇이 바뀌었는지 사람이 읽을 수 있게 정리합니다.
# LC_ALL=C 를 붙입니다. 두 목록은 LC_ALL=C sort 로 정렬했는데 comm 을 로케일 기본으로
# 돌리면 "정렬되지 않았다" 고 판단해 실패하고, 그때 폴백이 전체를 변경으로 보고합니다.
# 실제로 첫 비교에서 39건 전부가 변경으로 나왔습니다. loop.sh 의 security_snapshot 이
# 같은 이유로 LC_ALL=C 를 붙여 두었는데 여기서 같은 함정을 다시 밟았습니다.
CHANGED="$(LC_ALL=C comm -13 <(printf '%s\n' "${BEFORE}") <(printf '%s\n' "${NOW}") 2>/dev/null || printf '%s\n' "${NOW}")"
GONE="$(LC_ALL=C comm -23 <(printf '%s\n' "${BEFORE}") <(printf '%s\n' "${NOW}") 2>/dev/null || true)"

: > "${SNAP_PATH}.tmp" 2>/dev/null || true
save_snapshot
mv -f "${SNAP_PATH}.tmp" "${SNAP_PATH}" 2>/dev/null || true

REPORTED=""
while IFS=$'\t' read -r p _h; do
  [[ -n "${p}" ]] || continue
  REPORTED="${REPORTED} ${p}"
  guard_log_event "${ROOT}" change "${p}" "내용이 바뀌었습니다"
done <<< "${CHANGED}"
while IFS=$'\t' read -r p _h; do
  [[ -n "${p}" ]] || continue
  printf '%s' "${REPORTED}" | grep -qF -- " ${p}" && continue
  REPORTED="${REPORTED} ${p}"
  guard_log_event "${ROOT}" change "${p}" "사라졌거나 되돌려졌습니다"
done <<< "${GONE}"

REPORTED="${REPORTED# }"
[[ -n "${REPORTED}" ]] || exit 0

# 목록이 길면 앞의 몇 건만 보여 줍니다. 전량은 기록에 있습니다.
_count=0
for _x in ${REPORTED}; do _count=$((_count + 1)); done
_shown="${REPORTED}"
if [[ "${_count}" -gt 8 ]]; then
  _shown=""
  _i=0
  for _x in ${REPORTED}; do
    _i=$((_i + 1))
    [[ "${_i}" -le 8 ]] || break
    _shown="${_shown:+${_shown} }${_x}"
  done
  _shown="${_shown} … 외 $((_count - 8))건"
fi

emit "[harness] 보호 대상 ${_count}건이 변경되었습니다: ${_shown}"
emit "이 hook 은 막지 않습니다. 이미 일어난 변경을 알릴 뿐입니다."
emit "의도한 변경이면 그대로 두고, 사람 승인 없이 평가·게이트 기준을 바꾼 것이라면 되돌리십시오."
emit "기록: .harness/guard-events.log"
exit 0
