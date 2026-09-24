#!/usr/bin/env bash
# check-log-schema.sh — AD-2 후보: verify 의 `log-schema` 단계 비용 제거.
#
# `harness/scripts/self-check.sh --only log-schema` 는 번들 예시(6건) + 프로젝트
# improvement-log/ 전체(43건, 계속 증가)를 매 verify 실행마다 다시 검증한다.
# `improvement-log.sh validate` 는 파일 1건에 ~1.1초(프로세스 생성 비용)가 들어,
# 49건 전수 검사가 57초 걸린다 — improvement-log 는 append-only 라서 이미 검증을
# 통과한 파일을 매번 다시 볼 이유가 없다.
#
# 이 스크립트는 CI 에서는 지금처럼 전수 검사하되, 로컬에서는 기준선(origin/main
# 이 있으면 그것과의 merge-base, 없으면 HEAD) 대비 바뀐 improvement-log/*.yaml 과
# 번들 예시 파일만 검사한다. 바뀐 것이 없으면 정본 예시 1건
# (harness/improvement-log/2026-08-09-001.example.yaml)만 검사해, "검사 대상 0건"
# 이 조용히 통과로 처리되는 것(번들 예시가 지워졌다는 뜻)을 막는다. 정본 예시는
# 변경분이 있을 때도 함께 검사해 안전망을 유지한다.
#
# 번들(harness/) 파일은 읽기만 한다 — 이 스크립트도, 이 스크립트가 강제하는
# 스키마도 harness/improvement-log/schema.md 가 정본이며 여기서 고치지 않는다.
#
# 사용:
#   scripts/check-log-schema.sh                # 저장소 기본 경로
#   scripts/check-log-schema.sh --root <경로>   # 테스트용: 저장소 루트를 바꿔 지정
#
# 환경변수:
#   CI  — 비어 있지 않으면 번들 예시 + 프로젝트 로그 전수를 검사합니다(기존 동작).
#
# 종료 코드:
#   0 — 검사 대상이 스키마를 만족합니다.
#   1 — 스키마 위반, 또는 검사 대상이 0건(정본 예시가 없거나 지워짐).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

while [ $# -gt 0 ]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    *)
      echo "check-log-schema: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

HARNESS_DIR="${ROOT}/harness"
PROJ_LOG_DIR="${ROOT}/improvement-log"
VALIDATOR="${HARNESS_DIR}/scripts/improvement-log.sh"
CANONICAL_EXAMPLE="${HARNESS_DIR}/improvement-log/2026-08-09-001.example.yaml"

if [ ! -x "$VALIDATOR" ] && [ ! -f "$VALIDATOR" ]; then
  echo "check-log-schema: validator 를 찾을 수 없습니다: ${VALIDATOR}" >&2
  exit 1
fi

# improvement-log.sh validate 를 호출하는 함수 — CI/로컬 두 경로가 공유합니다.
# 실패하면 마지막 5줄을 출력하고 exit 1, 성공하면 요약 한 줄을 출력하고 exit 0.
run_validate() {
  local desc="$1"
  shift
  local out
  if out="$(cd "$ROOT" && HARNESS_PROJECT_ROOT="$ROOT" bash "$VALIDATOR" validate "$@" 2>&1)"; then
    echo "log-schema: ${desc}, 통과"
    return 0
  fi
  printf '%s\n' "$out" | tail -n 5
  echo "log-schema: ${desc}, 실패"
  return 1
}

if [ -n "${CI:-}" ]; then
  # --- CI: 전수 검사 (기존 self-check.sh --only log-schema 와 동일) -------------
  examples=()
  while IFS= read -r f; do examples+=("$f"); done < <(
    find "${HARNESS_DIR}" \( -name '*improvement-log*.yaml' -o -name '*.example.yaml' \) | sort -u
  )
  if [ -d "$PROJ_LOG_DIR" ]; then
    while IFS= read -r f; do examples+=("$f"); done < <(find "$PROJ_LOG_DIR" -name '*.yaml' -type f | sort)
  fi
  if [ ${#examples[@]} -eq 0 ]; then
    echo "check-log-schema: 검사할 예시가 하나도 없습니다. 번들의 improvement-log 예시가 제거되었는지 확인하십시오" >&2
    echo "log-schema: CI 전수 0건 — 실패(예시 없음)"
    exit 1
  fi
  run_validate "CI 전수 ${#examples[@]}건 검사" "${examples[@]}"
  exit $?
fi

# --- 로컬: 바뀐 것만 --------------------------------------------------------
if [ "$(cd "$ROOT" && git rev-parse --is-inside-work-tree 2>/dev/null || true)" != "true" ]; then
  echo "check-log-schema: ${ROOT} 는 git 저장소가 아닙니다" >&2
  exit 1
fi

BASE="HEAD"
if (cd "$ROOT" && git rev-parse --verify origin/main >/dev/null 2>&1); then
  MERGE_BASE="$(cd "$ROOT" && git merge-base HEAD origin/main 2>/dev/null || true)"
  [ -n "$MERGE_BASE" ] && BASE="$MERGE_BASE"
fi

add_if_match() {
  local relpath="$1"
  local abspath="${ROOT}/${relpath}"
  [ -f "$abspath" ] || return 0
  case "$relpath" in
    improvement-log/*.yaml)
      targets+=("$abspath")
      return 0
      ;;
  esac
  case "$relpath" in
    harness/*)
      case "$(basename "$relpath")" in
        *improvement-log*.yaml|*.example.yaml)
          targets+=("$abspath")
          ;;
      esac
      ;;
  esac
}

targets=()
while IFS= read -r f; do
  [ -n "$f" ] && add_if_match "$f"
done < <(
  cd "$ROOT"
  {
    git diff --name-only "$BASE" -- improvement-log harness 2>/dev/null
    git ls-files --others --exclude-standard -- improvement-log harness 2>/dev/null
  } | sort -u
)

changed_count=${#targets[@]}

if [ -f "$CANONICAL_EXAMPLE" ]; then
  targets+=("$CANONICAL_EXAMPLE")
fi

if [ ${#targets[@]} -eq 0 ]; then
  # 바뀐 것도 없고 정본 예시도 없다 — 통과가 아니라 실패다(예시가 지워졌다는 뜻).
  echo "check-log-schema: 정본 예시가 없습니다: ${CANONICAL_EXAMPLE}" >&2
  echo "log-schema: 검사 대상 0건 — 실패(정본 예시 없음)"
  exit 1
fi

# 중복 제거 (정본 예시가 이미 변경분에 포함됐을 수 있음)
mapfile -t targets < <(printf '%s\n' "${targets[@]}" | sort -u)

if [ "$changed_count" -gt 0 ]; then
  desc="변경 ${changed_count}건 + 정본 예시 검사"
else
  desc="정본 예시만 검사"
fi

run_validate "$desc" "${targets[@]}"
exit $?
