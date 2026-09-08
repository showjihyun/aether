#!/usr/bin/env bash
# loop.sh — 예산과 종료 조건을 가진 self-improving loop 러너입니다.
# rules/loop-budget.rule.md 의 종료 조건을 모두 구현하고 상태를 .harness/loop-state.json 에 남깁니다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck disable=SC1090,SC1091
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck disable=SC1090,SC1091
source "${SCRIPT_DIR}/lib/detect-stack.sh"

usage() {
  cat <<'USAGE'
사용법: loop.sh [옵션]

한 라운드는 다음 순서입니다.
  1. eval.sh 실행 (내부에서 verify.sh 를 실행합니다)
  2. pass-threshold.sh 로 합격 판정 — 통과하면 즉시 종료합니다
  3. 통과하지 못하면 가장 큰 실패 하나를 담은 프롬프트를 만들어
     HARNESS_AGENT_CMD 에 파이프로 넘겨 한 번 실행합니다
  4. 상태를 .harness/loop-state.json 에 갱신합니다

옵션:
  --max-iterations <N>  최대 반복 횟수. 기본값은 HARNESS_MAX_ITERATIONS 또는 8 입니다.
  --threshold <N>       합격선을 재정의합니다.
  --dry-run             에이전트를 실행하지 않고 사람이 실행할 프롬프트만 출력합니다.
  -h, --help            이 도움말을 출력합니다.

종료 조건 (rules/loop-budget.rule.md):
  - 최대 반복 횟수 도달                      → max_iterations
  - 동일 실패 서명 HARNESS_MAX_SAME_FAILURE 회 → same_failure
  - HARNESS_NO_IMPROVEMENT_ROUNDS 라운드 연속 개선 없음 → no_improvement
  - 루프 시작 이후 보안 민감 파일 변경 감지    → security_review (사람 검토로 에스컬레이션)
  - 시간 예산(HARNESS_MAX_SECONDS) 초과       → budget_exceeded

HARNESS_AGENT_CMD 가 비어 있으면 자동으로 dry-run 으로 동작합니다.

종료 코드:
  0  합격했거나 dry-run 으로 프롬프트만 출력했습니다.
  1  합격하지 못한 채 종료 조건에 걸렸습니다.
  2  loop 를 시작할 수 없습니다.
USAGE
}

OPT_DRY_RUN=0
OPT_MAX=""
OPT_THRESHOLD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --dry-run) OPT_DRY_RUN=1; shift ;;
    --max-iterations)
      [[ $# -ge 2 ]] || die "--max-iterations 에는 숫자가 필요합니다." 2
      OPT_MAX="$2"; shift 2 ;;
    --max-iterations=*) OPT_MAX="${1#*=}"; shift ;;
    --threshold)
      [[ $# -ge 2 ]] || die "--threshold 에는 숫자가 필요합니다." 2
      OPT_THRESHOLD="$2"; shift 2 ;;
    --threshold=*) OPT_THRESHOLD="${1#*=}"; shift ;;
    *) die "알 수 없는 옵션입니다: $1 (--help 를 보십시오)" 2 ;;
  esac
done

ROOT="$(find_project_root "$PWD")"
cd "$ROOT"
load_config "$ROOT"
harness_ensure_state_dir "$ROOT"

MAX_ITERATIONS="${OPT_MAX:-${HARNESS_MAX_ITERATIONS:-8}}"
MAX_SAME_FAILURE="${HARNESS_MAX_SAME_FAILURE:-3}"
MAX_NO_IMPROVEMENT="${HARNESS_NO_IMPROVEMENT_ROUNDS:-2}"
MAX_SECONDS="${HARNESS_MAX_SECONDS:-0}"
AGENT_CMD="${HARNESS_AGENT_CMD:-}"
THRESHOLD_ARGS=()
[[ -n "$OPT_THRESHOLD" ]] && THRESHOLD_ARGS=(--threshold "$OPT_THRESHOLD")

[[ "$MAX_ITERATIONS" =~ ^[0-9]+$ && "$MAX_ITERATIONS" -gt 0 ]] || die "max-iterations 가 잘못되었습니다: ${MAX_ITERATIONS}" 2

DRY_RUN="$OPT_DRY_RUN"
if [[ -z "$AGENT_CMD" && "$DRY_RUN" -eq 0 ]]; then
  DRY_RUN=1
  log_warn "HARNESS_AGENT_CMD 가 비어 있어 dry-run 으로 실행합니다. 프롬프트만 출력합니다."
fi

# 보안 민감 파일 패턴. 변경이 감지되면 사람 검토로 에스컬레이션합니다.
# 코어 패턴은 언어에 고정되지 않습니다. 언어별 자격 증명 파일(.npmrc, .pypirc, *.jks …)은
# harness/language/<언어>/lang.sh 의 HARNESS_LANG_<언어>_SECURITY_PATTERNS 가 덧붙입니다.
# 보호 목록과 같은 이유로 감지 결과에 의존하지 않고 모든 팩의 패턴을 합칩니다.
# monorepo 에서 루트가 한 언어만 가리켜도 다른 언어의 자격 증명 변경을 놓치지 않기 위해서입니다.
# 키워드는 경로 성분 경계에 붙여 판정합니다. 경계 없이 부분 문자열로 두면
# docs/authoring.md, AUTHORS, Miami.md 같은 무관한 경로가 auth·iam 에 걸려
# 루프가 보안 검토로 중단됩니다. 뒤의 s? 는 permissions.ts, secrets.yaml 처럼
# 흔한 복수형을 살리기 위한 것입니다.
SECURITY_KEYWORDS='secret|credential|password|token|auth|crypto|security|permission|iam'
SECURITY_PATTERNS="(^|/)(\.env|\.env\.[^/]+|id_rsa|id_ed25519)|(^|[^a-z0-9])(${SECURITY_KEYWORDS})s?([^a-z0-9]|$)|\.pem$|\.key$"
harness_lang_load_packs || true
LANG_SECURITY="$(lang_all_security_patterns)"
[[ -z "$LANG_SECURITY" ]] || SECURITY_PATTERNS="${SECURITY_PATTERNS}|${LANG_SECURITY}"

ITERATION=0
SCORES=()
LAST_SIGNATURE=""
SAME_FAILURE_COUNT=0
NO_IMPROVEMENT_ROUNDS=0
BEST_SCORE=-1
STOPPED_REASON=""
CURRENT_SCORE=0
CURRENT_SIGNATURE=""
LARGEST_LAYER=""
LARGEST_DETAIL=""
START_TS="$(date +%s)"

write_state() {
  local scores_json="" s
  for s in ${SCORES[@]+"${SCORES[@]}"}; do
    [[ -n "$scores_json" ]] && scores_json="${scores_json}, "
    scores_json="${scores_json}${s}"
  done
  {
    printf '{\n'
    printf '  "schema": "harness.loop/1",\n'
    printf '  "iteration": %s,\n' "$ITERATION"
    printf '  "scores": [%s],\n' "$scores_json"
    printf '  "last_failure_signature": "%s",\n' "$(json_escape "$LAST_SIGNATURE")"
    printf '  "same_failure_count": %s,\n' "$SAME_FAILURE_COUNT"
    printf '  "no_improvement_rounds": %s,\n' "$NO_IMPROVEMENT_ROUNDS"
    printf '  "stopped_reason": "%s",\n' "$(json_escape "$STOPPED_REASON")"
    printf '  "threshold": %s,\n' "${CURRENT_THRESHOLD:-0}"
    printf '  "max_iterations": %s,\n' "$MAX_ITERATIONS"
    printf '  "updated_at": "%s"\n' "$(now_iso)"
    printf '}\n'
  } > "${ROOT}/${HARNESS_LOOP_JSON}"
}

# 실패 서명 = 실패한 단계 id 를 순서대로 이어붙인 문자열입니다.
failure_signature() {
  local file="${ROOT}/${HARNESS_VERIFY_JSON}" sig="" line sid sstatus
  [[ -f "$file" ]] || { printf 'no-verify-json'; return 0; }
  while IFS= read -r line; do
    [[ "$line" == *'"id":'* ]] || continue
    sstatus="$(json_str_field "$line" status)"
    [[ "$sstatus" == "pass" ]] && continue
    sid="$(json_str_field "$line" id)"
    [[ -n "$sig" ]] && sig="${sig},"
    sig="${sig}${sid}:${sstatus}"
  done < "$file"
  [[ -n "$sig" ]] || sig="none"
  printf '%s' "$sig"
}

read_eval() {
  local file="${ROOT}/${HARNESS_EVAL_JSON}" content largest
  CURRENT_SCORE=0; CURRENT_THRESHOLD=0; LARGEST_LAYER=""; LARGEST_DETAIL=""
  [[ -f "$file" ]] || return 1
  content="$(tr '\n' ' ' < "$file")"
  CURRENT_SCORE="$(json_num_field "$content" score)"
  CURRENT_THRESHOLD="$(json_num_field "$content" threshold)"
  [[ "$CURRENT_SCORE" =~ ^[0-9]+$ ]] || CURRENT_SCORE=0
  [[ "$CURRENT_THRESHOLD" =~ ^[0-9]+$ ]] || CURRENT_THRESHOLD=0
  largest="$(printf '%s' "$content" | sed -n 's/.*"largest_failure"[[:space:]]*:[[:space:]]*{\([^}]*\)}.*/\1/p')"
  if [[ -n "$largest" ]]; then
    LARGEST_LAYER="$(json_str_field "$largest" layer)"
    LARGEST_DETAIL="$(json_str_field "$largest" detail)"
  fi
  return 0
}

failing_step_report() {
  local file="${ROOT}/${HARNESS_VERIFY_JSON}" line sid sstatus slog ssum
  [[ -f "$file" ]] || return 0
  while IFS= read -r line; do
    [[ "$line" == *'"id":'* ]] || continue
    sstatus="$(json_str_field "$line" status)"
    [[ "$sstatus" == "pass" ]] && continue
    sid="$(json_str_field "$line" id)"
    slog="$(json_str_field "$line" log)"
    [[ -n "$slog" ]] || slog="(없음)"
    ssum="$(json_str_field "$line" summary)"
    printf -- '- %s (%s) 로그: %s\n  마지막 출력: %s\n' "$sid" "$sstatus" "$slog" "$ssum"
  done < "$file"
}

build_prompt() {
  cat <<PROMPT
당신은 이 저장소에서 self-improving loop 의 한 라운드를 수행합니다.

현재 평가 결과
- 총점: ${CURRENT_SCORE} / 합격선: ${CURRENT_THRESHOLD}
- 가장 큰 실패 계층: ${LARGEST_LAYER:-(없음)}
- 상세: ${LARGEST_DETAIL:-(없음)}
- 반복: ${ITERATION} / ${MAX_ITERATIONS}

실패한 단계
$(failing_step_report)

지켜야 할 제약
1. 평가 기준을 수정하지 말 것. 테스트, lint 규칙, 임계값, verify 단계 정의, harness.config 를 느슨하게 바꾸는 것은 금지합니다.
2. 가장 큰 실패 하나만 고칠 것. 위에 적힌 가장 큰 실패 계층부터 다룹니다.
3. 한 번에 하나만 바꿀 것. 하나의 원인에 대한 하나의 변경만 적용하고 멈춥니다.

작업 절차
1. 실패 로그를 읽고 근본 원인을 한 문장으로 적습니다.
2. 그 원인에 대한 최소 변경을 적용합니다.
3. harness/scripts/verify.sh 를 실행해 그 변경이 실패를 해소했는지 확인합니다.
4. 반복될 만한 실패였다면 harness/scripts/improvement-log.sh new 로 후보를 남깁니다.
PROMPT
}

# 보안 민감 경로의 **내용 스냅숏**을 냅니다. "경로 내용해시" 줄의 목록입니다.
#
# 경로 집합만 비교하면 두 가지를 놓칩니다.
#   1. 루프 시작 시점에 이미 더티했던 .env 를 에이전트가 다시 쓰면, 경로 집합이
#      그대로여서 영영 걸리지 않습니다. 기준선에 있다는 이유로 면제됩니다.
#   2. 에이전트가 변경을 커밋하면 그 경로가 git status 에서 사라져 보이지 않습니다.
# 그래서 (a) 시작 시점 커밋 이후의 변경 경로까지 포함하고, (b) 경로가 아니라
# 내용 해시를 비교합니다. AGENTS.md 의 "보안에 닿는 변경은 사람 검토로
# 에스컬레이션합니다" 는 경로가 아니라 변경에 대한 약속입니다.
#
# LC_ALL=C 를 붙이는 이유: sort 는 로케일 순서로 정렬하고 비교는 바이트 단위라
# 비-C 로케일에서 두 목록의 순서가 어긋날 수 있습니다.
security_snapshot() {
  local p
  {
    git -C "$ROOT" status --porcelain 2>/dev/null | sed 's/^...//'
    [[ -n "${SECURITY_BASE_REV}" ]] && git -C "$ROOT" diff --name-only "${SECURITY_BASE_REV}" 2>/dev/null
  } | LC_ALL=C sort -u | grep -Ei "$SECURITY_PATTERNS" | while IFS= read -r p; do
    [[ -n "$p" ]] || continue
    if [[ -f "${ROOT}/${p}" ]]; then
      printf '%s %s\n' "$p" "$(git -C "$ROOT" hash-object -- "${ROOT}/${p}" 2>/dev/null || printf 'unhashable')"
    else
      printf '%s deleted\n' "$p"
    fi
  done
}

SECURITY_BASE_REV=""
SECURITY_BASELINE=""
if have_cmd git && git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  SECURITY_BASE_REV="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || true)"
  SECURITY_BASELINE="$(security_snapshot)"
fi
SECURITY_MATCHED=""

security_sensitive_change() {
  have_cmd git || return 1
  git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
  local now
  now="$(security_snapshot)"
  [[ "$now" != "$SECURITY_BASELINE" ]] || return 1
  # 기준선에 없던 줄(= 새로 생겼거나 내용이 바뀐 경로)만 보고합니다.
  SECURITY_MATCHED="$(
    comm -13 <(printf '%s\n' "$SECURITY_BASELINE" | LC_ALL=C sort) \
             <(printf '%s\n' "$now" | LC_ALL=C sort) 2>/dev/null \
      || printf '%s\n' "$now"
  )"
  SECURITY_MATCHED="$(printf '%s\n' "$SECURITY_MATCHED" | sed 's/ [0-9a-f]\{40\}$//; s/ unhashable$//; /^$/d')"
  [[ -n "$SECURITY_MATCHED" ]]
}

printf '%s\n' "self-improving loop 를 시작합니다."
printf '%s\n' "프로젝트 루트: ${ROOT}"
printf '%s\n' "최대 반복: ${MAX_ITERATIONS} / 동일 실패 한도: ${MAX_SAME_FAILURE} / 개선 없음 한도: ${MAX_NO_IMPROVEMENT}"
if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '%s\n' "모드: dry-run (에이전트를 실행하지 않습니다)"
else
  printf '%s\n' "모드: 자동 (HARNESS_AGENT_CMD=${AGENT_CMD})"
fi
printf '\n'

while :; do
  ITERATION=$((ITERATION + 1))
  printf '===== 라운드 %s / %s =====\n' "$ITERATION" "$MAX_ITERATIONS"

  set +e
  "${SCRIPT_DIR}/eval.sh" ${THRESHOLD_ARGS[@]+"${THRESHOLD_ARGS[@]}"}
  eval_code=$?
  set -e
  # eval.sh 는 성공하면 0 을 냅니다(합격 여부와 무관하게). 0 이 아니면 이번 라운드의
  # 점수가 나오지 않은 것입니다. 예전에는 3 만 특별 취급해서 2(--reuse 대상 없음),
  # 126(실행 권한 없음), 127(명령 없음)이 그대로 흘러가 아래 read_eval 이
  # **직전 라운드의 latest-eval.json** 을 이번 라운드 점수로 읽었습니다.
  # 커밋 768170f 가 eval.sh 안에서 고친 것과 같은 결함이 한 계층 위에 남아 있었습니다.
  if [[ "$eval_code" -ne 0 ]]; then
    STOPPED_REASON="eval_unavailable"
    write_state
    log_error "평가를 계산할 수 없어 loop 를 중단합니다 (eval.sh exit ${eval_code})."
    log_error "직전 라운드의 ${HARNESS_EVAL_JSON} 을 이번 라운드 결과로 쓰지 않습니다."
    exit 2
  fi

  read_eval || { STOPPED_REASON="eval_unavailable"; write_state; die "평가 결과 파일을 읽지 못했습니다." 2; }
  SCORES+=("$CURRENT_SCORE")
  CURRENT_SIGNATURE="$(failure_signature)"

  set +e
  "${SCRIPT_DIR}/pass-threshold.sh" ${THRESHOLD_ARGS[@]+"${THRESHOLD_ARGS[@]}"}
  pass_code=$?
  set -e
  if [[ "$pass_code" -eq 0 ]]; then
    STOPPED_REASON="passed"
    LAST_SIGNATURE="$CURRENT_SIGNATURE"
    write_state
    printf '\n%s\n' "종료 사유: 합격선을 넘었습니다 (score ${CURRENT_SCORE} >= threshold ${CURRENT_THRESHOLD})."
    printf '%s\n' "상태 파일: ${HARNESS_LOOP_JSON}"
    exit 0
  fi

  # 동일 실패 추적
  if [[ "$CURRENT_SIGNATURE" == "$LAST_SIGNATURE" ]]; then
    SAME_FAILURE_COUNT=$((SAME_FAILURE_COUNT + 1))
  else
    SAME_FAILURE_COUNT=1
  fi
  LAST_SIGNATURE="$CURRENT_SIGNATURE"

  # 개선 추적
  if [[ "$CURRENT_SCORE" -gt "$BEST_SCORE" ]]; then
    BEST_SCORE="$CURRENT_SCORE"
    NO_IMPROVEMENT_ROUNDS=0
  else
    NO_IMPROVEMENT_ROUNDS=$((NO_IMPROVEMENT_ROUNDS + 1))
  fi

  write_state

  # --- 종료 조건 (rules/loop-budget.rule.md) ---
  if security_sensitive_change; then
    STOPPED_REASON="security_review"
  elif [[ "$SAME_FAILURE_COUNT" -ge "$MAX_SAME_FAILURE" ]]; then
    STOPPED_REASON="same_failure"
  elif [[ "$NO_IMPROVEMENT_ROUNDS" -ge "$MAX_NO_IMPROVEMENT" ]]; then
    STOPPED_REASON="no_improvement"
  elif [[ "$MAX_SECONDS" =~ ^[0-9]+$ && "$MAX_SECONDS" -gt 0 && $(( $(date +%s) - START_TS )) -ge "$MAX_SECONDS" ]]; then
    STOPPED_REASON="budget_exceeded"
  elif [[ "$ITERATION" -ge "$MAX_ITERATIONS" ]]; then
    STOPPED_REASON="max_iterations"
  fi

  if [[ -n "$STOPPED_REASON" ]]; then
    write_state
    break
  fi

  # --- 에이전트 실행 ---
  PROMPT="$(build_prompt)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '\n%s\n' "----- 이 라운드에서 에이전트에게 줄 프롬프트 -----"
    printf '%s\n' "$PROMPT"
    printf '%s\n\n' "------------------------------------------------"
    STOPPED_REASON="dry_run"
    write_state
    printf '%s\n' "종료 사유: dry-run 입니다. 위 프롬프트를 사람이 직접 에이전트에 넘기거나 HARNESS_AGENT_CMD 를 설정하십시오."
    printf '%s\n' "남은 실패:"
    failing_step_report
    printf '%s\n' "상태 파일: ${HARNESS_LOOP_JSON}"
    exit 0
  fi

  agent_log="${HARNESS_LOG_DIR}/agent-round-${ITERATION}.log"
  printf '%s\n' "에이전트를 실행합니다. 로그: ${agent_log}"
  set +e
  printf '%s\n' "$PROMPT" | bash -c "$AGENT_CMD" >"${ROOT}/${agent_log}" 2>&1
  agent_code=$?
  set -e
  if [[ "$agent_code" -ne 0 ]]; then
    log_warn "에이전트 명령이 exit ${agent_code} 로 끝났습니다. 로그: ${agent_log}"
  fi
  write_state
  printf '\n'
done

# --- 중단 보고 ---
printf '\n'
case "$STOPPED_REASON" in
  same_failure)
    printf '%s\n' "종료 사유: 같은 실패가 ${SAME_FAILURE_COUNT}회 반복되었습니다 (한도 ${MAX_SAME_FAILURE}회)."
    printf '%s\n' "같은 자리에서 맴돌고 있습니다. 하네스 자체를 고칠 차례입니다." ;;
  no_improvement)
    printf '%s\n' "종료 사유: ${NO_IMPROVEMENT_ROUNDS}라운드 연속 점수가 개선되지 않았습니다 (한도 ${MAX_NO_IMPROVEMENT}라운드)."
    printf '%s\n' "최고 점수: ${BEST_SCORE}. 문제를 더 작게 쪼개거나 평가 증거를 보강하십시오." ;;
  security_review)
    printf '%s\n' "종료 사유: 보안 민감 파일 변경이 감지되었습니다. 사람 검토로 에스컬레이션합니다."
    printf '%s\n' "걸린 경로 (루프 시작 이후 새로 바뀐 것만):"
    printf '%s\n' "${SECURITY_MATCHED}" | sed 's/^/  /'
    printf '%s\n' "전체 변경은 git status --porcelain 으로 확인하십시오." ;;
  budget_exceeded)
    printf '%s\n' "종료 사유: 시간 예산 ${MAX_SECONDS}초를 초과했습니다." ;;
  max_iterations)
    printf '%s\n' "종료 사유: 최대 반복 ${MAX_ITERATIONS}회에 도달했습니다." ;;
  *)
    printf '%s\n' "종료 사유: ${STOPPED_REASON}" ;;
esac

printf '%s\n' "마지막 점수: ${CURRENT_SCORE} / 합격선: ${CURRENT_THRESHOLD}"
printf '%s\n' "점수 이력: ${SCORES[*]}"
printf '%s\n' "실패 서명: ${LAST_SIGNATURE}"
printf '%s\n' "남은 실패:"
failing_step_report
printf '%s\n' "상태 파일: ${HARNESS_LOOP_JSON}"
exit 1
