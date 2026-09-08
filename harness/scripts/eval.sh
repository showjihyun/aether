#!/usr/bin/env bash
# eval.sh — verify 결과를 6개 평가 계층으로 집계해 가중 점수를 냅니다.
# 결과는 .harness/latest-eval.json 에 기록합니다. 키와 산출식의 정본은 evaluation/rubric.md 입니다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck disable=SC1090,SC1091
source "${SCRIPT_DIR}/lib/common.sh"

usage() {
  cat <<'USAGE'
사용법: eval.sh [옵션]

verify.sh 를 실행하고 그 결과를 correctness, architecture, quality, behavior,
performance, subjective 6개 계층으로 집계해 .harness/latest-eval.json 을 씁니다.

옵션:
  --reuse              verify.sh 를 다시 실행하지 않고 기존 .harness/verify.json 을 씁니다.
  --threshold <N>      합격선을 재정의합니다. 기본값은 harness.config 의 HARNESS_THRESHOLD 입니다.
  --json               사람용 출력을 억제하고 결과 JSON 만 표준출력으로 냅니다.
  -h, --help           이 도움말을 출력합니다.

점수 계산:
  계층 점수 = (그 계층의 통과 단계 수 / 그 계층의 단계 수) * 100
  단계가 하나도 없는 계층은 score 가 null 이고, 그 가중치는 나머지 계층에 비례 재분배합니다.
  최종 score 는 계층 점수의 가중 평균을 반올림한 0~100 정수입니다.
  필수 단계가 하나라도 실패하면 score 와 무관하게 pass 는 false 입니다 (EV-5).

종료 코드:
  0  계산에 성공했습니다. (합격 여부는 pass 필드와 pass-threshold.sh 로 판정합니다)
  2  --reuse 인데 .harness/verify.json 이 없습니다.
  3  집계할 단계가 없습니다.
USAGE
}

OPT_REUSE=0
OPT_JSON=0
OPT_THRESHOLD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --reuse) OPT_REUSE=1; shift ;;
    --json) OPT_JSON=1; shift ;;
    --threshold)
      [[ $# -ge 2 ]] || die "--threshold 에는 숫자가 필요합니다." 3
      OPT_THRESHOLD="$2"; shift 2 ;;
    --threshold=*) OPT_THRESHOLD="${1#*=}"; shift ;;
    *) die "알 수 없는 옵션입니다: $1 (--help 를 보십시오)" 3 ;;
  esac
done

say() { [[ "$OPT_JSON" -eq 1 ]] || printf '%s\n' "$*"; }

ROOT="$(find_project_root "$PWD")"
cd "$ROOT"
load_config "$ROOT"

VERIFY_FILE="${ROOT}/${HARNESS_VERIFY_JSON}"

if [[ "$OPT_REUSE" -eq 1 ]]; then
  [[ -f "$VERIFY_FILE" ]] || die "재사용할 ${HARNESS_VERIFY_JSON} 이 없습니다. --reuse 없이 다시 실행하십시오." 2
  say "기존 ${HARNESS_VERIFY_JSON} 을 재사용합니다."
else
  say "verify.sh 를 실행합니다."
  _rc=0
  if [[ "$OPT_JSON" -eq 1 ]]; then
    "${SCRIPT_DIR}/verify.sh" >/dev/null 2>&1 || _rc=$?
  else
    "${SCRIPT_DIR}/verify.sh" || _rc=$?
  fi
  # verify.sh 의 규약: 0 = 필수 전부 통과, 1 = 필수 실패. 둘 다 채점 가능한 결과를 남깁니다.
  # 그 밖(3 단계 정의 오류, 126 실행 권한 없음, 127 명령 없음, 시그널)은 이번 실행이
  # 결과를 남기지 못했다는 뜻입니다. 예전에는 || true 로 삼키고 파일 존재만 확인해서
  # **실행되지 않은 라운드의 낡은 점수**를 이번 결과로 보고했습니다.
  case "$_rc" in
    0|1) ;;
    *) die "verify.sh 가 exit ${_rc} 로 끝나 이번 실행의 결과를 남기지 못했습니다. 낡은 ${HARNESS_VERIFY_JSON} 은 채점하지 않습니다." 3 ;;
  esac
  [[ -f "$VERIFY_FILE" ]] || die "verify.sh 가 ${HARNESS_VERIFY_JSON} 을 만들지 못했습니다." 3
fi

# 부분 실행 결과는 채점하지 않습니다.
#
# verify.sh --only 로 한 단계만 돈 결과에도 status: pass 가 붙습니다. 그것을 그대로
# 집계하면 실행되지 않은 계층이 전부 null 이 되어 가중치가 실행된 한 계층으로
# 재분배되고, 총점 100 / pass: true 가 나옵니다. evaluation/README.md 와
# skills/harness-promote/SKILL.md 는 이 출력을 회귀·승격의 근거로 쓰므로,
# 5개 필수 단계 중 1개만 돈 결과가 승격을 인증하게 됩니다.
# stop 게이트가 partial 을 막는 것과 같은 이유이며, 여기가 더 중요합니다.
# 게이트는 한 세션의 종료를 막지만 이쪽은 하네스에 영구히 들어갈 변경을 판정합니다.
_partial="$(json_num_field "$(tr '\n' ' ' < "$VERIFY_FILE")" partial)"
if [[ "$_partial" == "true" ]]; then
  _ran="$(json_num_field "$(tr '\n' ' ' < "$VERIFY_FILE")" ran_steps)"
  _defined="$(json_num_field "$(tr '\n' ' ' < "$VERIFY_FILE")" defined_steps)"
  die "${HARNESS_VERIFY_JSON} 이 부분 실행 결과입니다 (${_ran:-?}/${_defined:-?} 단계). 부분 실행은 채점하지 않습니다. verify.sh 를 --only 없이 실행한 뒤 다시 시도하십시오." 3
fi

# --- verify.json 의 단계 읽기 ---------------------------------------------------
STEP_IDS=(); STEP_LAYERS=(); STEP_STATUS=(); STEP_LOGS=()
while IFS= read -r line; do
  [[ "$line" == *'"id":'* ]] || continue
  sid="$(json_str_field "$line" id)"
  slayer="$(json_str_field "$line" layer)"
  sstatus="$(json_str_field "$line" status)"
  slog="$(json_str_field "$line" log)"
  [[ -n "$sid" && -n "$slayer" ]] || continue
  STEP_IDS+=("$sid"); STEP_LAYERS+=("$slayer"); STEP_STATUS+=("$sstatus"); STEP_LOGS+=("$slog")
done < "$VERIFY_FILE"

STEP_COUNT=${#STEP_IDS[@]}
if [[ "$STEP_COUNT" -eq 0 ]]; then
  log_error "집계할 단계가 없습니다. verify.sh 가 단계를 하나도 실행하지 못했습니다."
  log_error "harness.config 의 HARNESS_STEPS 를 정의하거나 감지 가능한 스택에서 실행하십시오."
  exit 3
fi

# --- 가중치 ---------------------------------------------------------------------
# weight_to_milli <십진수> — 0.30 → 300 (정수 산술을 위해 1000배 합니다)
weight_to_milli() {
  local w="${1:-0}" int frac
  w="${w#+}"
  if [[ "$w" == *.* ]]; then
    int="${w%%.*}"; frac="${w#*.}"
  else
    int="$w"; frac=""
  fi
  [[ "$int" =~ ^[0-9]+$ ]] || int=0
  frac="${frac//[^0-9]/}"
  frac="${frac}000"; frac="${frac:0:3}"
  printf '%s' "$(( 10#$int * 1000 + 10#$frac ))"
}

milli_to_weight() {
  local m="$1"
  if [[ $((m % 10)) -eq 0 ]]; then
    printf '%d.%02d' "$((m / 1000))" "$(((m % 1000) / 10))"
  else
    printf '%d.%03d' "$((m / 1000))" "$((m % 1000))"
  fi
}

declare -A W_MILLI=(
  [correctness]=300 [architecture]=200 [quality]=200
  [behavior]=150 [performance]=100 [subjective]=50
)
WEIGHT_SOURCE="기본값"
_weight_count=0
if declare -p HARNESS_EVAL_WEIGHTS >/dev/null 2>&1; then
  _weight_count=${#HARNESS_EVAL_WEIGHTS[@]}
fi
if [[ "$_weight_count" -gt 0 ]]; then
  for entry in "${HARNESS_EVAL_WEIGHTS[@]}"; do
    [[ -z "$entry" ]] && continue
    IFS='|' read -r wlayer wvalue <<<"$entry"
    wlayer="${wlayer//[[:space:]]/}"
    wvalue="${wvalue//[[:space:]]/}"
    harness_layer_is_valid "$wlayer" || die "HARNESS_EVAL_WEIGHTS 에 알 수 없는 layer 가 있습니다: ${wlayer}" 3
    W_MILLI["$wlayer"]="$(weight_to_milli "$wvalue")"
  done
  WEIGHT_SOURCE="harness.config"
fi

# --- 계층 집계 -------------------------------------------------------------------
declare -A L_TOTAL L_PASS L_EVIDENCE L_FAILED
for layer in "${HARNESS_LAYERS[@]}"; do
  L_TOTAL["$layer"]=0; L_PASS["$layer"]=0; L_EVIDENCE["$layer"]=""; L_FAILED["$layer"]=""
done

for ((i = 0; i < STEP_COUNT; i++)); do
  layer="${STEP_LAYERS[$i]}"
  harness_layer_is_valid "$layer" || continue
  L_TOTAL["$layer"]=$(( L_TOTAL["$layer"] + 1 ))
  if [[ "${STEP_STATUS[$i]}" == "pass" ]]; then
    L_PASS["$layer"]=$(( L_PASS["$layer"] + 1 ))
    [[ -n "${L_EVIDENCE[$layer]}" ]] || L_EVIDENCE["$layer"]="${STEP_LOGS[$i]}"
  else
    L_FAILED["$layer"]="${L_FAILED[$layer]}${STEP_IDS[$i]} "
    [[ -n "${STEP_LOGS[$i]}" ]] && L_EVIDENCE["$layer"]="${STEP_LOGS[$i]}"
  fi
done

# 점수가 있는 계층의 원래 가중치 합을 구해 재분배 분모로 씁니다.
ACTIVE_MILLI=0
for layer in "${HARNESS_LAYERS[@]}"; do
  [[ "${L_TOTAL[$layer]}" -gt 0 ]] || continue
  ACTIVE_MILLI=$(( ACTIVE_MILLI + W_MILLI[$layer] ))
done
[[ "$ACTIVE_MILLI" -gt 0 ]] || die "가중치 합이 0 입니다. HARNESS_EVAL_WEIGHTS 를 확인하십시오." 3

WEIGHTED_SUM=0
LAYERS_JSON=""
LARGEST_LAYER=""
LARGEST_DEFICIT=-1
for layer in "${HARNESS_LAYERS[@]}"; do
  total="${L_TOTAL[$layer]}"
  base_milli="${W_MILLI[$layer]}"
  if [[ "$total" -gt 0 ]]; then
    eff_milli=$(( base_milli * 1000 / ACTIVE_MILLI ))
    score=$(( (L_PASS[$layer] * 100 * 2 + total) / (total * 2) ))
    WEIGHTED_SUM=$(( WEIGHTED_SUM + eff_milli * score ))
    score_json="$score"
    notes="${L_PASS[$layer]}/${total} 단계 통과"
    deficit=$(( eff_milli * (100 - score) ))
    if [[ "$deficit" -gt 0 && "$deficit" -gt "$LARGEST_DEFICIT" ]]; then
      LARGEST_DEFICIT="$deficit"; LARGEST_LAYER="$layer"
    fi
  else
    eff_milli=0
    score_json="null"
    notes="단계 없음: 가중치를 다른 계층에 재분배했습니다"
  fi
  if [[ "$layer" == "subjective" ]]; then deterministic="false"; else deterministic="true"; fi
  [[ -n "$LAYERS_JSON" ]] && LAYERS_JSON="${LAYERS_JSON},"$'\n'
  LAYERS_JSON="${LAYERS_JSON}    {\"layer\": \"${layer}\", \"weight\": $(milli_to_weight "$eff_milli"), \"score\": ${score_json}, \"deterministic\": ${deterministic}, \"evidence\": \"$(json_escape "${L_EVIDENCE[$layer]}")\", \"notes\": \"$(json_escape "$notes")\"}"
done
[[ -n "$LAYERS_JSON" ]] && LAYERS_JSON="${LAYERS_JSON}"$'\n'

SCORE=$(( (WEIGHTED_SUM + 500) / 1000 ))
[[ "$SCORE" -le 100 ]] || SCORE=100
[[ "$SCORE" -ge 0 ]] || SCORE=0

# 필수 단계 실패는 점수보다 앞섭니다. subagents/harness-evaluator.md 의 EV-5 가 이미
# "총점이 임계값을 넘어도 필수 결정론 계층이 실패했으면 pass 는 false" 라고 규정했는데
# 구현에는 그 조건이 없었습니다. 총점만으로 판정하면 계층 분포에 따라 필수 실패가
# 합격선 위에 남습니다. 예를 들어 quality 가 3단계가 되고 그중 하나가 실패하면
# 총점은 92 로 계산되어 threshold 90 을 넘지만 verify 는 status:fail 입니다.
# 합격선이라는 숫자가 "한 단계라도 실패하면 불합격" 이라는 불리언을 대신 표현하고 있었고,
# 단계 구성이 바뀌는 순간 그 대체는 깨집니다. 불리언은 불리언으로 판정합니다.
FAILED_REQUIRED_COUNT="$(json_num_field "$(tr '\n' ' ' < "$VERIFY_FILE")" failed_required)"
[[ "$FAILED_REQUIRED_COUNT" =~ ^[0-9]+$ ]] \
  || die "${HARNESS_VERIFY_JSON} 에서 failed_required 를 읽지 못했습니다. harness.verify/1 형식이 아닙니다. verify.sh 를 다시 실행하십시오." 3

THRESHOLD="${OPT_THRESHOLD:-${HARNESS_THRESHOLD:-80}}"
[[ "$THRESHOLD" =~ ^[0-9]+$ ]] || die "threshold 가 정수가 아닙니다: ${THRESHOLD}" 3

if [[ "$SCORE" -ge "$THRESHOLD" && "$FAILED_REQUIRED_COUNT" -eq 0 ]]; then PASS="true"; else PASS="false"; fi

if [[ -n "$LARGEST_LAYER" ]]; then
  failed_list="${L_FAILED[$LARGEST_LAYER]}"
  failed_list="${failed_list% }"
  [[ -n "$failed_list" ]] || failed_list="(실패 단계 없음)"
  LARGEST_JSON="{\"layer\": \"${LARGEST_LAYER}\", \"detail\": \"$(json_escape "가중치 결손이 가장 큰 계층입니다. 실패 단계: ${failed_list}. 증거 로그: ${L_EVIDENCE[$LARGEST_LAYER]}")\"}"
else
  LARGEST_JSON="null"
fi

{
  # 최상위 스칼라를 배열보다 **먼저** 씁니다. lib/common.sh 의 json_num_field 는
  # 첫 일치를 내므로, layers 가 앞에 오면 계층의 score 를 최상위 score 로 읽습니다.
  # verify.json 도 같은 순서(스칼라 → steps 배열)입니다. 이 순서를 바꾸지 마십시오.
  printf '{\n'
  printf '  "schema": "harness.eval/1",\n'
  printf '  "score": %s,\n' "$SCORE"
  printf '  "threshold": %s,\n' "$THRESHOLD"
  printf '  "pass": %s,\n' "$PASS"
  printf '  "failed_required": %s,\n' "$FAILED_REQUIRED_COUNT"
  printf '  "layers": [\n'
  printf '%s' "$LAYERS_JSON"
  printf '  ],\n'
  printf '  "largest_failure": %s\n' "$LARGEST_JSON"
  printf '}\n'
} > "${ROOT}/${HARNESS_EVAL_JSON}"

if [[ "$OPT_JSON" -eq 1 ]]; then
  cat "${ROOT}/${HARNESS_EVAL_JSON}"
  exit 0
fi

say ""
say "가중치 출처: ${WEIGHT_SOURCE}"
say "| layer | weight | score | 비고 |"
say "| --- | --- | --- | --- |"
for layer in "${HARNESS_LAYERS[@]}"; do
  total="${L_TOTAL[$layer]}"
  if [[ "$total" -gt 0 ]]; then
    eff_milli=$(( W_MILLI[$layer] * 1000 / ACTIVE_MILLI ))
    score=$(( (L_PASS[$layer] * 100 * 2 + total) / (total * 2) ))
    say "| ${layer} | $(milli_to_weight "$eff_milli") | ${score} | ${L_PASS[$layer]}/${total} 단계 통과 |"
  else
    say "| ${layer} | 0.00 | null | 단계 없음 (가중치 재분배) |"
  fi
done
say ""
say "총점: ${SCORE} / 합격선: ${THRESHOLD} / 합격 여부: ${PASS}"
if [[ "$FAILED_REQUIRED_COUNT" -gt 0 ]]; then
  say "필수 단계 ${FAILED_REQUIRED_COUNT}건이 실패했습니다. 총점과 무관하게 불합격입니다 (EV-5)."
fi
if [[ -n "$LARGEST_LAYER" ]]; then
  say "가장 큰 실패 계층: ${LARGEST_LAYER} (실패 단계: ${L_FAILED[$LARGEST_LAYER]:-없음})"
fi
say "결과 파일: ${HARNESS_EVAL_JSON}"
exit 0
