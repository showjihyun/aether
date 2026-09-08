#!/usr/bin/env bash
# protected-diff.sh — 두 리비전 사이에서 보호 파일이 바뀌었는지 봅니다.
#
# 로컬 hook 은 에이전트가 도는 곳에서 돕니다. 그래서 결정적인 우회를 원리적으로 막지
# 못합니다. hook 을 등록에서 빼거나, 열거에 없는 명령으로 쓰거나, hook 이 읽을 수 없는
# 프로그램 안에서 쓰면 됩니다. 이 스크립트는 그 밖에서 돌기 위한 것입니다.
# 에이전트는 자기 머신의 어떤 hook 도 이길 수 있지만, 푸시된 커밋을 다른 곳에서 보는
# 검사는 이기지 못합니다.
#
# 보호 목록은 hooks/lib/guard-lib.sh 와 언어 팩이 소유합니다. 여기서 다시 적지 않습니다.
# 목록이 갈라지면 로컬이 막는 것을 CI 가 보지 못합니다.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
GUARD_LIB="${HARNESS_DIR}/hooks/lib/guard-lib.sh"
DETECT_LIB="${SCRIPT_DIR}/lib/detect-stack.sh"

usage() {
  cat <<'USAGE'
사용법: protected-diff.sh [<base-ref>]

<base-ref> 와 HEAD 사이에서 바뀐 파일 중 보호 목록에 걸리는 것을 출력합니다.
base-ref 를 주지 않으면 HEAD 와 작업 트리를 비교합니다.

종료 코드:
  0  보호 파일 변경 없음
  1  보호 파일이 바뀌었습니다 (목록을 표준출력으로 냅니다)
  3  실행할 수 없습니다 (git 저장소가 아니거나 보호 목록을 못 읽었습니다)
USAGE
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
esac

[[ -f "${GUARD_LIB}" ]] || { printf '%s\n' "보호 목록을 찾을 수 없습니다: ${GUARD_LIB}" >&2; exit 3; }
# shellcheck source=../hooks/lib/guard-lib.sh
source "${GUARD_LIB}"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { printf '%s\n' "git 저장소가 아닙니다." >&2; exit 3; }

# 언어 팩 패턴도 합칩니다. 로컬 가드와 같은 범위를 봐야 합니다.
if [[ -f "${DETECT_LIB}" ]]; then
  if source "${DETECT_LIB}" 2>/dev/null && declare -F harness_lang_load_packs >/dev/null 2>&1; then
    harness_lang_load_packs || true
    while IFS= read -r _p; do
      [[ -n "${_p}" ]] && HARNESS_PROTECTED_PATTERNS+=("${_p}")
    done < <(lang_all_protected_patterns 2>/dev/null || true)
  fi
fi

BASE="${1:-}"
if [[ -n "${BASE}" ]]; then
  CHANGED="$(git -C "${ROOT}" diff --name-only "${BASE}...HEAD" 2>/dev/null || git -C "${ROOT}" diff --name-only "${BASE}" HEAD)"
else
  CHANGED="$(git -C "${ROOT}" diff --name-only HEAD)"
fi

HITS=""
while IFS= read -r p; do
  [[ -n "${p}" ]] || continue
  if m="$(matches_any "${p}" "${p##*/}" ${HARNESS_PROTECTED_PATTERNS[@]+"${HARNESS_PROTECTED_PATTERNS[@]}"})"; then
    HITS="${HITS}${p}	${m}"$'\n'
  fi
done <<< "${CHANGED}"

if [[ -z "${HITS}" ]]; then
  exit 0
fi

printf '%s' "${HITS}"
exit 1
