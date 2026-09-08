#!/usr/bin/env bash
# verify.sh — 통합 검증 명령. 프로젝트의 모든 검증 단계를 한 번에 실행하고
# 결과를 .harness/verify.json 으로 남깁니다. 키는 아래 write_verify_json 이 소유하고,
# 게이트가 읽는 키의 의미는 hooks/README.md 가 설명합니다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck disable=SC1090,SC1091
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck disable=SC1090,SC1091
source "${SCRIPT_DIR}/lib/detect-stack.sh"

usage() {
  cat <<'USAGE'
사용법: verify.sh [옵션]

프로젝트의 검증 단계를 순서대로 실행하고 결과를 .harness/verify.json 에 씁니다.

옵션:
  --only <id>          지정한 id 의 단계만 실행합니다. 여러 번 지정할 수 있습니다.
  --list               실행할 단계 목록만 출력하고 종료합니다.
  --continue-on-fail   필수 단계가 실패해도 남은 단계를 계속 실행합니다.
  --json               사람용 출력을 억제하고 결과 JSON 만 표준출력으로 냅니다.
  -h, --help           이 도움말을 출력합니다.

단계 정의:
  프로젝트 루트의 harness.config 에 HARNESS_STEPS 가 있으면 그것을 씁니다.
  없으면 언어 팩(harness/language/<언어>/lang.sh)이 스택과 kind(frontend/backend)를 감지해
  기본 단계를 씁니다. 감지 재정의는 HARNESS_STACK, HARNESS_KIND 입니다.
  각 항목의 형식은 "id|layer|required|command" 입니다.
  layer 는 correctness, architecture, quality, behavior, performance, subjective 중 하나입니다.

종료 코드:
  0  필수 단계가 모두 통과했습니다.
  1  필수 단계가 하나 이상 실패했습니다.
  3  실행할 단계가 없거나 단계 정의가 잘못되었습니다.
USAGE
}

OPT_JSON=0
OPT_LIST=0
OPT_CONTINUE=0
ONLY_IDS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --json) OPT_JSON=1; shift ;;
    --list) OPT_LIST=1; shift ;;
    --continue-on-fail) OPT_CONTINUE=1; shift ;;
    --only)
      [[ $# -ge 2 ]] || die "--only 에는 단계 id 가 필요합니다." 3
      ONLY_IDS+=("$2"); shift 2 ;;
    --only=*) ONLY_IDS+=("${1#*=}"); shift ;;
    *) die "알 수 없는 옵션입니다: $1 (--help 를 보십시오)" 3 ;;
  esac
done

say() { [[ "$OPT_JSON" -eq 1 ]] || printf '%s\n' "$*"; }

ROOT="$(find_project_root "$PWD")"
cd "$ROOT"
load_config "$ROOT"

# 팩을 이 프로세스에서 한 번만 로드합니다. 아래 명령 치환들이 이미 로드된 함수를 물려받아
# 팩을 여러 번 다시 source 하지 않습니다.
harness_lang_load_packs || true

STACK="$(detect_stack "$ROOT")"
KIND="$(detect_kind "$ROOT" "$STACK")"
# 여러 언어가 함께 감지되면 채택되지 않은 후보를 알려 줍니다(monorepo 진단용).
OTHER_STACKS=""
while IFS= read -r _cand; do
  [[ -n "$_cand" && "$_cand" != "$STACK" ]] || continue
  OTHER_STACKS="${OTHER_STACKS:+${OTHER_STACKS}, }${_cand}"
done < <(detect_all_stacks "$ROOT")

# --- 단계 정의 수집 -----------------------------------------------------------
STEP_LINES=()
STEP_SOURCE=""
_config_step_count=0
if declare -p HARNESS_STEPS >/dev/null 2>&1; then
  _config_step_count=${#HARNESS_STEPS[@]}
fi
if [[ "$_config_step_count" -gt 0 ]]; then
  STEP_LINES=("${HARNESS_STEPS[@]}")
  STEP_SOURCE="harness.config"
else
  while IFS= read -r _line; do
    [[ -n "$_line" ]] && STEP_LINES+=("$_line")
  done < <(default_steps_for_stack "$STACK" "$ROOT" "$KIND")
  STEP_SOURCE="자동 감지 (${STACK}, ${KIND})"
  # kind 가 한쪽으로 확정되면 반대편 kind 의 단계가 빠집니다. 그 사실을 알립니다.
  # 알리지 않으면 계약 테스트·스모크·번들 크기 단계가 조용히 실행되지 않은 채
  # "검증했다" 는 결론만 남습니다.
  if [[ "$KIND" == "frontend" || "$KIND" == "backend" ]]; then
    _have_ids=" "
    for _l in ${STEP_LINES[@]+"${STEP_LINES[@]}"}; do
      _have_ids="${_have_ids}${_l%%|*} "
    done
    OMITTED_IDS=""
    while IFS= read -r _l; do
      [[ -n "$_l" ]] || continue
      _oid="${_l%%|*}"
      [[ "$_have_ids" == *" ${_oid} "* ]] && continue
      OMITTED_IDS="${OMITTED_IDS:+${OMITTED_IDS}, }${_oid}"
    done < <(default_steps_for_stack "$STACK" "$ROOT" fullstack)
  fi
fi

say "프로젝트 루트: ${ROOT}"
say "감지된 스택: ${STACK} (kind: ${KIND})"
[[ -z "$OTHER_STACKS" ]] || say "다른 후보 스택: ${OTHER_STACKS} (HARNESS_STACK 으로 바꿀 수 있습니다)"
say "단계 정의 출처: ${STEP_SOURCE}"
if [[ -n "${OMITTED_IDS:-}" ]]; then
  say "kind=${KIND} 판정으로 제외된 단계: ${OMITTED_IDS} (포함하려면 HARNESS_KIND=fullstack)"
fi
if [[ "${HARNESS_LANG_PACK_PROBLEMS:-0}" -gt 0 ]]; then
  log_warn "계약을 어긴 언어 팩 ${HARNESS_LANG_PACK_PROBLEMS}개를 비활성화했습니다. 위 오류를 먼저 해소하십시오."
fi
say ""

# --- 파싱과 검증 ---------------------------------------------------------------
IDS=(); LAYERS=(); REQUIREDS=(); COMMANDS=()
DEFINED_TOTAL=0   # --only 로 걸러내기 **전**의 단계 수. 부분 실행 판정에 씁니다.
for _line in ${STEP_LINES[@]+"${STEP_LINES[@]}"}; do
  [[ -z "$_line" || "$_line" == \#* ]] && continue
  IFS='|' read -r _id _layer _req _cmd <<<"$_line"
  _id="${_id//[[:space:]]/}"
  _layer="${_layer//[[:space:]]/}"
  _req="${_req//[[:space:]]/}"
  [[ -n "$_id" && -n "$_layer" && -n "$_cmd" ]] || die "단계 정의 형식이 잘못되었습니다: ${_line}" 3
  harness_layer_is_valid "$_layer" || die "알 수 없는 layer 입니다: ${_layer} (단계 ${_id})" 3
  case "$_req" in
    true|yes|1|required) _req="true" ;;
    false|no|0|optional|"") _req="false" ;;
    *) die "required 값이 잘못되었습니다: ${_req} (단계 ${_id})" 3 ;;
  esac
  DEFINED_TOTAL=$((DEFINED_TOTAL + 1))
  if [[ ${#ONLY_IDS[@]} -gt 0 ]]; then
    _match=0
    for _o in "${ONLY_IDS[@]}"; do [[ "$_o" == "$_id" ]] && _match=1; done
    [[ "$_match" -eq 1 ]] || continue
  fi
  IDS+=("$_id"); LAYERS+=("$_layer"); REQUIREDS+=("$_req"); COMMANDS+=("$_cmd")
done

TOTAL=${#IDS[@]}

if [[ "$OPT_LIST" -eq 1 ]]; then
  if [[ "$TOTAL" -eq 0 ]]; then
    say "실행할 단계가 없습니다."
    exit 3
  fi
  say "| id | layer | required | command |"
  say "| --- | --- | --- | --- |"
  for ((i = 0; i < TOTAL; i++)); do
    say "| ${IDS[$i]} | ${LAYERS[$i]} | ${REQUIREDS[$i]} | ${COMMANDS[$i]} |"
  done
  exit 0
fi

harness_ensure_state_dir "$ROOT"

write_verify_json() {
  local status="$1" failed_required="$2" failed_optional="$3" steps_json="$4"
  local only_json="" sep="" i=0 partial="false"
  for ((i = 0; i < ${#ONLY_IDS[@]}; i++)); do
    only_json="${only_json}${sep}\"${ONLY_IDS[$i]}\""
    sep=", "
  done
  if [[ "$TOTAL" -lt "$DEFINED_TOTAL" ]]; then partial="true"; fi
  {
    printf '{\n'
    printf '  "schema": "harness.verify/1",\n'
    printf '  "status": "%s",\n' "$status"
    # 부분 실행 표시. 이 세 키가 없으면 --only 한 번의 결과가 전량 실행과 구별되지 않습니다.
    printf '  "partial": %s,\n' "$partial"
    printf '  "defined_steps": %s,\n' "$DEFINED_TOTAL"
    printf '  "ran_steps": %s,\n' "$TOTAL"
    printf '  "only": [%s],\n' "$only_json"
    # 신선도 근거. 둘 다 없으면 며칠 지난 pass 가 오늘의 종료를 통과시킵니다.
    printf '  "finished_at": "%s",\n' "$(now_iso)"
    printf '  "tree": "%s",\n' "$(harness_tree_fingerprint "$ROOT")"
    printf '  "steps": [\n'
    printf '%s' "$steps_json"
    printf '  ],\n'
    printf '  "failed_required": %s,\n' "$failed_required"
    printf '  "failed_optional": %s\n' "$failed_optional"
    printf '}\n'
  } > "$ROOT/$HARNESS_VERIFY_JSON"
}

if [[ "$TOTAL" -eq 0 ]]; then
  write_verify_json "error" 0 0 ""
  if [[ "$OPT_JSON" -eq 1 ]]; then
    cat "$ROOT/$HARNESS_VERIFY_JSON"
  else
    log_error "실행할 단계가 없습니다."
    if [[ ${#ONLY_IDS[@]} -gt 0 ]]; then
      log_error "사유: --only 로 지정한 id 와 일치하는 단계가 없습니다."
    elif [[ "$STACK" == "unknown" ]]; then
      log_error "사유: 스택을 감지하지 못했습니다. 지원 언어 팩은 harness/language/README.md 4절에 있습니다."
      log_error "      harness.config 의 HARNESS_STEPS 로 단계를 직접 정의하거나 HARNESS_STACK 으로 스택을 지정하십시오."
    else
      log_error "사유: 감지된 스택(${STACK}, kind ${KIND})에서 실행 가능한 기본 단계를 찾지 못했습니다. harness.config 의 HARNESS_STEPS 로 단계를 직접 정의하십시오."
    fi
    log_error "예시는 harness/scripts/harness.config.example 와 harness/language/<언어>/<kind>/harness.config.example 를 보십시오."
  fi
  exit 3
fi

# --- 실행 ----------------------------------------------------------------------
STEPS_JSON=""
FAILED_REQUIRED=0
FAILED_OPTIONAL=0
FAILED_IDS=()
ABORTED=0

for ((i = 0; i < TOTAL; i++)); do
  id="${IDS[$i]}"; layer="${LAYERS[$i]}"; req="${REQUIREDS[$i]}"; cmd="${COMMANDS[$i]}"
  slug="$(harness_slug "$id")"
  log_rel="${HARNESS_LOG_DIR}/${slug}.log"
  log_abs="${ROOT}/${log_rel}"

  if [[ "$ABORTED" -eq 1 ]]; then
    status="skip"; code="null"; dur=0
    log_rel=""
    summary="이전 필수 단계 실패로 실행하지 않았습니다"
    say "[$((i + 1))/${TOTAL}] ${id} — 건너뜀"
  else
    say "[$((i + 1))/${TOTAL}] ${id} (${layer}, required=${req}) 실행 중: ${cmd}"
    start_ms="$(now_ms)"
    if bash -c "$cmd" >"$log_abs" 2>&1; then
      code=0
    else
      code=$?
    fi
    dur=$(( $(now_ms) - start_ms ))
    [[ "$dur" -ge 0 ]] || dur=0
    summary="$(tail -n 40 "$log_abs" 2>/dev/null | grep -v '^[[:space:]]*$' | tail -n 1 || true)"
    summary="${summary//\"/\'}"
    summary="${summary:0:200}"
    if [[ "$code" -eq 0 ]]; then
      status="pass"
      say "        통과 (${dur}ms)"
    else
      status="fail"
      FAILED_IDS+=("$id")
      say "        실패 (exit ${code}, ${dur}ms)"
      say "        로그: ${log_rel}"
      if [[ "$OPT_JSON" -eq 0 ]]; then
        say "        --- 마지막 20줄 ---"
        tail -n 20 "$log_abs" 2>/dev/null | sed 's/^/        /' || true
        say "        -------------------"
      fi
      if [[ "$req" == "true" ]]; then
        FAILED_REQUIRED=$((FAILED_REQUIRED + 1))
        [[ "$OPT_CONTINUE" -eq 1 ]] || ABORTED=1
      else
        FAILED_OPTIONAL=$((FAILED_OPTIONAL + 1))
      fi
    fi
  fi

  [[ -n "$STEPS_JSON" ]] && STEPS_JSON="${STEPS_JSON},"$'\n'
  STEPS_JSON="${STEPS_JSON}    {\"id\": \"$(json_escape "$id")\", \"layer\": \"${layer}\", \"required\": ${req}, \"status\": \"${status}\", \"exit_code\": ${code}, \"duration_ms\": ${dur}, \"summary\": \"$(json_escape "$summary")\", \"log\": \"$(json_escape "$log_rel")\"}"
done
[[ -n "$STEPS_JSON" ]] && STEPS_JSON="${STEPS_JSON}"$'\n'

if [[ "$FAILED_REQUIRED" -gt 0 ]]; then
  OVERALL="fail"
else
  OVERALL="pass"
fi

write_verify_json "$OVERALL" "$FAILED_REQUIRED" "$FAILED_OPTIONAL" "$STEPS_JSON"

if [[ "$OPT_JSON" -eq 1 ]]; then
  cat "$ROOT/$HARNESS_VERIFY_JSON"
else
  say ""
  say "결과: ${OVERALL} (필수 실패 ${FAILED_REQUIRED}건, 선택 실패 ${FAILED_OPTIONAL}건)"
  if [[ ${#FAILED_IDS[@]} -gt 0 ]]; then
    say "실패 단계: ${FAILED_IDS[*]}"
  fi
  if [[ "$ABORTED" -eq 1 ]]; then
    say "필수 단계 실패로 이후 단계를 실행하지 않았습니다. 전부 실행하려면 --continue-on-fail 을 쓰십시오."
  fi
  say "결과 파일: ${HARNESS_VERIFY_JSON}"
fi

[[ "$FAILED_REQUIRED" -eq 0 ]] || exit 1
exit 0
