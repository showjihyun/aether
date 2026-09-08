#!/usr/bin/env bash
# pass-threshold.sh — .harness/latest-eval.json 의 score 를 합격선과 비교합니다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck disable=SC1090,SC1091
source "${SCRIPT_DIR}/lib/common.sh"

usage() {
  cat <<'USAGE'
사용법: pass-threshold.sh [옵션]

.harness/latest-eval.json 의 score 와 threshold 를 비교해 합격 여부만 판정합니다.
평가를 다시 실행하지 않습니다. 필요하면 eval.sh 를 먼저 실행하십시오.

옵션:
  --threshold <N>   파일에 기록된 threshold 대신 이 값을 씁니다.
  --quiet           사람용 출력을 하지 않고 종료 코드로만 답합니다.
  -h, --help        이 도움말을 출력합니다.

종료 코드:
  0  score >= threshold
  1  score < threshold 이거나 필수 단계가 하나 이상 실패했습니다
  2  .harness/latest-eval.json 이 없거나 읽을 수 없습니다.
USAGE
}

OPT_THRESHOLD=""
OPT_QUIET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --quiet) OPT_QUIET=1; shift ;;
    --threshold)
      [[ $# -ge 2 ]] || die "--threshold 에는 숫자가 필요합니다." 2
      OPT_THRESHOLD="$2"; shift 2 ;;
    --threshold=*) OPT_THRESHOLD="${1#*=}"; shift ;;
    *) die "알 수 없는 옵션입니다: $1 (--help 를 보십시오)" 2 ;;
  esac
done

say() { [[ "$OPT_QUIET" -eq 1 ]] || printf '%s\n' "$*"; }

ROOT="$(find_project_root "$PWD")"
cd "$ROOT"
load_config "$ROOT"

EVAL_FILE="${ROOT}/${HARNESS_EVAL_JSON}"
if [[ ! -f "$EVAL_FILE" ]]; then
  log_error "${HARNESS_EVAL_JSON} 이 없습니다."
  log_error "사유: 아직 평가를 실행하지 않았습니다. harness/scripts/eval.sh 를 먼저 실행하십시오."
  exit 2
fi

CONTENT="$(tr '\n' ' ' < "$EVAL_FILE")"
SCORE="$(json_num_field "$CONTENT" score)"
FILE_THRESHOLD="$(json_num_field "$CONTENT" threshold)"

if [[ ! "$SCORE" =~ ^[0-9]+$ ]]; then
  log_error "${HARNESS_EVAL_JSON} 에서 score 를 읽지 못했습니다."
  log_error "사유: 파일이 손상되었거나 harness.eval/1 스키마가 아닙니다."
  exit 2
fi

# 명시적으로 받은 --threshold 가 정수가 아니면 조용히 버리지 않고 실패합니다.
# 예전에는 파일 값이나 기본값으로 대체해서, `--threshold 9O`(문자 O)를 준 호출자가
# 자기가 적은 값으로 게이트했다고 믿게 되었습니다. eval.sh 는 같은 입력에 die 하므로
# 두 스크립트가 "잘못된 --threshold" 의 의미에 대해 서로 다르게 답하고 있었습니다.
if [[ -n "${OPT_THRESHOLD}" ]]; then
  [[ "$OPT_THRESHOLD" =~ ^[0-9]+$ ]] || die "--threshold 가 정수가 아닙니다: ${OPT_THRESHOLD}" 2
  THRESHOLD="$OPT_THRESHOLD"
else
  THRESHOLD="$FILE_THRESHOLD"
  [[ "$THRESHOLD" =~ ^[0-9]+$ ]] || THRESHOLD="${HARNESS_THRESHOLD:-80}"
  [[ "$THRESHOLD" =~ ^[0-9]+$ ]] || die "threshold 가 정수가 아닙니다: ${THRESHOLD}" 2
fi

# 필수 단계 실패는 점수보다 앞섭니다 (harness-evaluator 의 EV-5). eval.sh 가 기록한
# failed_required 를 봅니다. 이 키가 없으면 판정하지 않고 실패합니다. 없는 것을 0 으로
# 가정하면 이 키 이전 형식의 파일이 조용히 합격으로 읽힙니다. 게이트는 근거가 없을 때
# 열지 않고 닫습니다. 근거: 감지 실패를 fail-open 으로 두었던 improvement-log/2026-09-03-001.
FAILED_REQUIRED="$(json_num_field "$CONTENT" failed_required)"
if [[ ! "$FAILED_REQUIRED" =~ ^[0-9]+$ ]]; then
  log_error "${HARNESS_EVAL_JSON} 에 failed_required 가 없습니다."
  log_error "사유: 이 키를 기록하기 이전 형식의 파일입니다. harness/scripts/eval.sh 를 다시 실행하십시오."
  exit 2
fi

if [[ "$FAILED_REQUIRED" -eq 0 && "$SCORE" -ge "$THRESHOLD" ]]; then
  say "합격: score ${SCORE} >= threshold ${THRESHOLD}, 필수 단계 실패 0건"
  exit 0
fi

if [[ "$FAILED_REQUIRED" -gt 0 ]]; then
  say "불합격: 필수 단계 ${FAILED_REQUIRED}건이 실패했습니다 (score ${SCORE} 는 판정에 쓰지 않습니다)"
else
  say "불합격: score ${SCORE} < threshold ${THRESHOLD}"
fi
LARGEST="$(printf '%s' "$CONTENT" | sed -n 's/.*"largest_failure"[[:space:]]*:[[:space:]]*{\([^}]*\)}.*/\1/p')"
if [[ -n "$LARGEST" ]]; then
  say "가장 큰 실패: $(json_str_field "$LARGEST" layer) — $(json_str_field "$LARGEST" detail)"
fi
exit 1
