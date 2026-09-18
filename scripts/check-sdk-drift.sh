#!/usr/bin/env bash
# check-sdk-drift.sh — AD-2 후보 2026-09-17-005: `packages/sdk/openapi.json` 등 계약과
# `packages/sdk/src/generated` 생성물이 서로 맞는지, 커밋 여부와 무관하게 검사합니다.
#
# 기존 `harness.config` 의 `web-typecheck` 드리프트 검사(`git diff --exit-code HEAD --
# packages/sdk/src/generated`)는 재생성 결과를 **HEAD** 와 비교합니다. 그래서 계약을
# 올바르게 바꾸고 생성물을 정확히 재생성했더라도 커밋 전에는 반드시 실패했습니다
# (improvement-log 2026-09-17-005, evaluation/runs/2026-09-17-REP-7.md,
# evaluation/runs/2026-09-17-REP-1-r2.md). 이 스크립트는 git 을 쓰지 않고 "작업 트리
# 자체가 스스로 일치하는가" 만 봅니다 — CI 는 깨끗한 체크아웃이라 작업 트리 = 커밋이므로
# 검출력은 같습니다.
#
# 동작:
#   1. 생성물 디렉터리를 임시 위치에 통째로 복사해 둡니다(재생성 전 스냅샷).
#   2. 생성 명령을 실행해 생성물 디렉터리를 제자리에서 재생성합니다.
#   3. 재생성 결과(현재 디렉터리)와 스냅샷을 바이트 단위로 비교합니다. 파일이 새로
#      생기거나 사라지는 것도 차이로 봅니다.
#
# 실패든 성공이든 재생성된 생성물은 그대로 둡니다(되돌리지 않음 — 지금 단계와 같은
# 동작). 임시 스냅샷만 trap 으로 정리합니다.
#
# 사용:
#   scripts/check-sdk-drift.sh                                          # 저장소 기본값
#   scripts/check-sdk-drift.sh --dir <경로> --generate-cmd <명령 문자열>  # 테스트용
#
# 종료 코드:
#   0 — 재생성 결과가 작업 트리와 바이트 단위로 같음.
#   1 이상 — 다르거나(내용/추가/삭제), 생성물 디렉터리가 없거나, 생성 명령이 실패함
#           (생성 명령의 종료 코드를 그대로 전파).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

DIR="${ROOT}/packages/sdk/src/generated"
GENERATE_CMD="pnpm -F sdk run generate"

while [ $# -gt 0 ]; do
  case "$1" in
    --dir)
      DIR="$2"
      shift 2
      ;;
    --generate-cmd)
      GENERATE_CMD="$2"
      shift 2
      ;;
    *)
      echo "check-sdk-drift: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ ! -d "$DIR" ]; then
  echo "check-sdk-drift: 생성물 디렉터리가 없습니다: ${DIR}" >&2
  exit 1
fi

DIR="$(cd "$DIR" && pwd -P)"

SNAPSHOT_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$SNAPSHOT_DIR"
}
trap cleanup EXIT

# 재생성 전 스냅샷 — 디렉터리 내용을 통째로 복사합니다(숨김 파일 포함). 뒤에서 이
# 스냅샷과 재생성 결과(제자리에서 덮어써진 $DIR)를 비교합니다.
cp -a "${DIR}/." "${SNAPSHOT_DIR}/"

# 생성 명령을 실행합니다. `set -e` 아래에서 대입에 실패한 명령 치환이 곧바로 스크립트를
# 끝내지 않도록 `||` 로 종료 코드만 따로 받습니다(check-bench.sh 와 같은 방식의 변형).
GEN_EXIT=0
GEN_OUTPUT="$(cd "$ROOT" && eval "$GENERATE_CMD" 2>&1)" || GEN_EXIT=$?

if [ "$GEN_EXIT" -ne 0 ]; then
  printf '%s\n' "$GEN_OUTPUT" >&2
  echo "check-sdk-drift: 생성 명령이 실패했습니다(exit ${GEN_EXIT}): ${GENERATE_CMD}" >&2
  exit "$GEN_EXIT"
fi

# 스냅샷(재생성 전)과 현재 디렉터리(재생성 후)를 바이트 단위로 비교합니다. `-r` 은
# 하위 디렉터리까지, `-q` 는 다른 파일 이름만 한 줄씩 보고합니다. 새 파일이 생기거나
# 기존 파일이 사라진 경우도 "Only in ..." 줄로 잡힙니다.
DIFF_OUTPUT=""
DIFF_STATUS=0
DIFF_OUTPUT="$(diff -rq "$SNAPSHOT_DIR" "$DIR" 2>&1)" || DIFF_STATUS=$?

if [ "$DIFF_STATUS" -eq 0 ]; then
  FILE_COUNT="$(find "$DIR" -type f | wc -l | tr -d '[:space:]')"
  printf 'check-sdk-drift: 재생성 결과가 작업 트리와 같습니다 (파일 %s개 확인)\n' "$FILE_COUNT"
  exit 0
fi

# diff -rq 의 각 줄에서 파일 이름만 뽑아 사람이 읽기 쉬운 목록을 만듭니다.
#   "Files <스냅샷>/rel and <DIR>/rel differ"  -> rel 의 마지막 조각(파일 이름)
#   "Only in <경로>: 이름"                     -> 이름
DIFF_FILES="$(printf '%s\n' "$DIFF_OUTPUT" | sed -E \
  -e 's#^Files .*[\/]([^\/]+) and .*[\/][^\/]+ differ$#\1#' \
  -e 's#^Only in .*: (.+)$#\1#' \
)"
FILES_JOINED="$(printf '%s\n' "$DIFF_FILES" | paste -sd ',' - | sed 's/,/, /g')"

echo "check-sdk-drift: 재생성 결과가 작업 트리와 다릅니다" >&2
printf '%s\n' "$DIFF_OUTPUT" >&2
printf 'check-sdk-drift: 재생성 결과가 작업 트리와 다릅니다: %s\n' "$FILES_JOINED"
exit 1
