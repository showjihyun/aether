#!/usr/bin/env bash
# detect-stack.sh — 언어 팩 로더와 스택 감지 진입점. 직접 실행하지 않고 source 해서 사용합니다.
#
# 제공 함수:
#   harness_lang_load_packs   language/*/lang.sh 를 모두 source 하고 계약을 검증합니다 (1회).
#   harness_lang_validate_packs  등록된 팩의 필수 함수·배열을 검사하고 위반 팩을 비활성화합니다.
#   harness_lang_has <팩>     팩이 로드되었는지 확인합니다.
#   detect_stack [root]       첫 번째로 감지된 스택 ID. HARNESS_STACK 이 있으면 그 값(옛 형식은 변환).
#   detect_all_stacks [root]  감지 순서대로 모든 후보 스택 ID (한 줄에 하나).
#   detect_kind <root> [stack]  frontend | backend | fullstack | unknown. HARNESS_KIND 가 있으면 그 값.
#   stack_base / stack_variant   "typescript:pnpm" → "typescript" / "pnpm".
#   default_steps_for_stack <stack> [root] [kind]   "id|layer|required|command" 줄 목록 (language/README.md 2절).
#   lang_all_protected_patterns / lang_all_warn_patterns / lang_all_security_patterns
#                             로드된 **모든** 팩 × 모든 kind 의 패턴 합집합. 보호 판정은 이것만 씁니다.
#                             감지 결과로 범위를 좁히는 변형을 다시 만들지 마십시오. 근거는 hooks/README.md 입니다.
#   _emit_step <id> <layer> <required> <command…>   팩이 단계 한 줄을 출력할 때 씁니다.
#
# 언어별 감지·기본 단계·보호 패턴은 harness/language/<언어>/lang.sh 가 소유합니다.
# 팩 계약과 감지 순서는 harness/language/README.md 를 읽습니다. 이 파일은 언어를 알지 못합니다.
set -euo pipefail

if [[ -n "${HARNESS_DETECT_STACK_SH_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
HARNESS_DETECT_STACK_SH_LOADED=1

_HARNESS_DETECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck disable=SC1090,SC1091
source "${_HARNESS_DETECT_DIR}/common.sh"

# --- 팩 레지스트리 --------------------------------------------------------------
HARNESS_LANGUAGE_DIR="${HARNESS_LANGUAGE_DIR:-${HARNESS_DIR}/language}"
HARNESS_LANG_PACKS=()
HARNESS_LANG_PACK_PROBLEMS=0
# 문서화된 kind 목록. 팩은 이 값으로 kind 별 패턴 변수 이름을 만듭니다(예: _FRONTEND_PROTECTED_PATTERNS).
HARNESS_LANG_KINDS=(frontend backend)
# 감지 우선순위 기본값. 앞의 팩이 먼저 검사되고 처음 감지된 스택이 채택됩니다.
# 재정의는 HARNESS_LANG_DETECT_ORDER="java typescript" 처럼 공백 구분 문자열로 합니다.
HARNESS_LANG_DETECT_ORDER_DEFAULT=(typescript java python go rust ruby)

# _emit_step <id> <layer> <required> <command…>
# 팩이 사용합니다. 팩보다 먼저 정의되어야 하므로 로더 앞에 둡니다.
_emit_step() {
  local id="$1" layer="$2" required="$3"
  shift 3
  printf '%s|%s|%s|%s\n' "$id" "$layer" "$required" "$*"
}

# _lang_upper <문자열> — 변수명에 쓸 수 있게 대문자화합니다 (typescript → TYPESCRIPT, c-sharp → C_SHARP).
# hook 이 매 편집마다 실행되므로 tr 대신 bash 내장만 씁니다. 이 플랫폼에서 fork 1회는 약 30ms 입니다.
_lang_upper() {
  local s="${1//-/_}"
  printf '%s' "${s^^}"
}

# _lang_is_array <변수명> — 그 이름이 **인덱스 배열**로 선언되어 있는지 확인합니다.
# declare -p 만으로는 스칼라도 통과하고, 스칼라에 ${#name[@]} 를 쓰면 set -u 아래에서 스크립트가 죽습니다.
# ${!name@a} 는 간접 참조 후 속성 플래그를 냅니다. 배열이면 'a' 를 포함하고 미선언·스칼라면 비어 있습니다.
_lang_is_array() {
  local n="$1"
  # declare -p 는 내장이므로 리다이렉션만으로는 fork 하지 않습니다. 명령 치환으로 감싸지 마십시오.
  # 미선언 변수를 먼저 걸러야 합니다. set -u 아래에서 미선언 변수의 간접 참조는 셸을 종료시킵니다.
  declare -p "$n" >/dev/null 2>&1 || return 1
  [[ "${!n@a}" == *a* ]]
}

# harness_lang_load_packs — language/*/lang.sh 를 사전순으로 source 합니다. '_' 로 시작하는 디렉터리는 건너뜁니다.
# 팩 하나의 실패가 다른 팩과 코어로 번지지 않도록 개별 격리합니다.
harness_lang_load_packs() {
  if [[ -n "${HARNESS_LANG_PACKS_LOADED:-}" ]]; then
    return 0
  fi
  HARNESS_LANG_PACKS_LOADED=1
  if [[ ! -d "$HARNESS_LANGUAGE_DIR" ]]; then
    log_warn "언어 팩 디렉터리가 없습니다: ${HARNESS_LANGUAGE_DIR} (언어별 감지와 보호 패턴을 사용할 수 없습니다)"
    return 0
  fi
  local f name dir
  for f in "${HARNESS_LANGUAGE_DIR}"/*/lang.sh; do
    [[ -f "$f" ]] || continue
    dir="${f%/lang.sh}"; name="${dir##*/}"
    [[ "$name" == _* ]] && continue
    # shellcheck disable=SC1090
    if ! source "$f"; then
      log_warn "언어 팩을 로드하지 못했습니다: ${f} (이 팩을 건너뜁니다)"
    fi
  done
  harness_lang_validate_packs || true
  return 0
}

# harness_lang_validate_packs — 등록된 팩이 language/README.md 2절 계약을 지키는지 검사합니다.
# 계약을 어긴 팩은 등록에서 제외하고 사유를 stderr 에 남깁니다.
# 조용히 넘어가면 그 팩의 보호 패턴이 사라진 사실이 아무 데도 드러나지 않습니다.
harness_lang_validate_packs() {
  local p up fn v bad problems=0 reasons=""
  local -a kept=()
  for p in ${HARNESS_LANG_PACKS[@]+"${HARNESS_LANG_PACKS[@]}"}; do
    bad=""
    if [[ ! "$p" =~ ^[a-z][a-z0-9-]*$ ]]; then
      bad="${bad} 팩 이름이 [a-z][a-z0-9-]* 형식이 아닙니다;"
    fi
    for fn in detect kind default_steps; do
      declare -F "harness_lang_${p}_${fn}" >/dev/null 2>&1 \
        || bad="${bad} harness_lang_${p}_${fn}() 없음;"
    done
    up="$(_lang_upper "$p")"
    for v in PROTECTED WARN; do
      _lang_is_array "HARNESS_LANG_${up}_${v}_PATTERNS" \
        || bad="${bad} HARNESS_LANG_${up}_${v}_PATTERNS 가 배열이 아님;"
    done
    if [[ -n "$bad" ]]; then
      problems=$((problems + 1))
      reasons="${reasons}  ${p}:${bad}"$'\n'
    else
      kept+=("$p")
    fi
  done
  HARNESS_LANG_PACKS=(${kept[@]+"${kept[@]}"})
  HARNESS_LANG_PACK_PROBLEMS="$problems"
  if [[ "$problems" -gt 0 ]]; then
    log_error "언어 팩 계약 위반 ${problems}건. 해당 팩을 비활성화했습니다. 그 언어의 보호 패턴과 기본 단계가 없습니다."
    printf '%s' "$reasons" >&2
    log_error "계약은 harness/language/README.md 2절입니다."
  fi
  return 0
}

# harness_lang_has <팩이름>
harness_lang_has() {
  local p
  for p in ${HARNESS_LANG_PACKS[@]+"${HARNESS_LANG_PACKS[@]}"}; do
    [[ "$p" == "$1" ]] && return 0
  done
  return 1
}

# _harness_lang_ordered_packs — 감지 순서대로 팩 이름을 출력합니다.
# HARNESS_LANG_DETECT_ORDER(또는 기본 순서)에 있는 팩 먼저, 그 다음 나머지 로드된 팩.
_harness_lang_ordered_packs() {
  local -a order_src=()
  local p seen=" "
  if [[ -n "${HARNESS_LANG_DETECT_ORDER:-}" ]]; then
    read -r -a order_src <<<"${HARNESS_LANG_DETECT_ORDER}"
  else
    order_src=("${HARNESS_LANG_DETECT_ORDER_DEFAULT[@]}")
  fi
  for p in ${order_src[@]+"${order_src[@]}"}; do
    harness_lang_has "$p" || continue
    [[ "$seen" == *" ${p} "* ]] && continue
    printf '%s\n' "$p"; seen="${seen}${p} "
  done
  for p in ${HARNESS_LANG_PACKS[@]+"${HARNESS_LANG_PACKS[@]}"}; do
    [[ "$seen" == *" ${p} "* ]] && continue
    printf '%s\n' "$p"; seen="${seen}${p} "
  done
}

# --- 스택 ID -------------------------------------------------------------------
# _harness_stack_normalize <stack> — 옛 형식(node:*, gradle, maven)을 새 형식으로 바꿉니다.
_harness_stack_normalize() {
  case "$1" in
    node) printf 'typescript' ;;
    node:*) printf 'typescript:%s' "${1#node:}" ;;
    gradle) printf 'java:gradle' ;;
    maven) printf 'java:maven' ;;
    *) printf '%s' "$1" ;;
  esac
}

# stack_base <stack> — "typescript:pnpm" 에서 "typescript" 를 꺼냅니다. 팩 이름과 같습니다.
stack_base() { printf '%s' "${1%%:*}"; }

# stack_variant <stack> — "typescript:pnpm" 에서 "pnpm" 을 꺼냅니다. 없으면 빈 문자열입니다.
stack_variant() {
  local s="$1"
  [[ "$s" == *:* ]] && printf '%s' "${s#*:}" || printf ''
}

# detect_all_stacks [root] — 감지 순서대로 모든 후보를 출력합니다.
detect_all_stacks() {
  local root="${1:-$PWD}" p s
  harness_lang_load_packs
  for p in $(_harness_lang_ordered_packs); do
    declare -F "harness_lang_${p}_detect" >/dev/null 2>&1 || continue
    s=""
    if s="$("harness_lang_${p}_detect" "$root" 2>/dev/null)" && [[ -n "$s" ]]; then
      printf '%s\n' "$s"
    fi
  done
}

# detect_stack [root]
# 출력: 첫 번째로 감지된 스택 ID, 없으면 unknown. HARNESS_STACK 환경변수가 있으면 그 값을 씁니다.
detect_stack() {
  local root="${1:-$PWD}" s all
  if [[ -n "${HARNESS_STACK:-}" ]]; then
    s="$(_harness_stack_normalize "${HARNESS_STACK}")"
    if [[ "$s" != "${HARNESS_STACK}" ]]; then
      log_warn "HARNESS_STACK=${HARNESS_STACK} 은 옛 형식입니다. ${s} 로 해석합니다. harness.config 를 갱신하십시오."
    fi
    printf '%s\n' "$s"
    return 0
  fi
  # 파이프 조기 종료(SIGPIPE)를 피하려고 전체를 변수로 받은 뒤 첫 줄만 씁니다.
  all="$(detect_all_stacks "$root")"
  s="${all%%$'\n'*}"
  [[ -n "$s" ]] || s="unknown"
  printf '%s\n' "$s"
}

# detect_kind <root> [stack]
# 출력: frontend | backend | fullstack | unknown. HARNESS_KIND 환경변수가 있으면 그 값을 씁니다.
# kind 는 **기본 verify 단계 선택에만** 씁니다. 보호 패턴은 kind 에 의존하지 않습니다.
detect_kind() {
  local root="${1:-$PWD}" stack="${2:-}" base
  if [[ -n "${HARNESS_KIND:-}" ]]; then
    printf '%s\n' "${HARNESS_KIND}"
    return 0
  fi
  [[ -n "$stack" ]] || stack="$(detect_stack "$root")"
  base="$(stack_base "$stack")"
  harness_lang_load_packs
  if harness_lang_has "$base" && declare -F "harness_lang_${base}_kind" >/dev/null 2>&1; then
    "harness_lang_${base}_kind" "$root" "$stack"
  else
    printf 'unknown\n'
  fi
}

# default_steps_for_stack <stack> [root] [kind]
# 출력: "id|layer|required|command" 형식의 줄 목록 (language/README.md 2절). 팩이 없으면 아무 줄도 출력하지 않습니다.
default_steps_for_stack() {
  local stack="${1:-unknown}" root="${2:-$PWD}" kind="${3:-}" base
  base="$(stack_base "$stack")"
  harness_lang_load_packs
  harness_lang_has "$base" || return 0
  if ! declare -F "harness_lang_${base}_default_steps" >/dev/null 2>&1; then
    log_warn "언어 팩 ${base} 에 harness_lang_${base}_default_steps 가 없습니다. 기본 단계를 만들지 못합니다."
    return 0
  fi
  [[ -n "$kind" ]] || kind="$(detect_kind "$root" "$stack")"
  "harness_lang_${base}_default_steps" "$stack" "$root" "$kind"
}

# --- 팩 패턴 수집 ----------------------------------------------------------------
# _lang_array_lines <배열변수명> — 배열의 원소를 한 줄에 하나씩 출력합니다.
# 배열이 아니거나 비어 있으면 아무것도 출력하지 않습니다.
_lang_array_lines() {
  local name="$1" n=0 item ref
  _lang_is_array "$name" || return 0
  eval "n=\${#${name}[@]}"
  [[ "$n" -gt 0 ]] || return 0
  ref="${name}[@]"
  for item in "${!ref}"; do
    printf '%s\n' "$item"
  done
}

# --- 보호 패턴 (감지와 무관한 합집합) ------------------------------------------------
# 보호 목록은 **감지 결과에 의존하지 않습니다.** 로드된 모든 팩의 모든 kind 패턴을 합칩니다.
# 감지에 의존하면 다음 상황에서 다른 언어의 평가 설정 파일이 조용히 무방비가 됩니다.
#   - 지원하지 않는 언어의 저장소(스택 미감지)
#   - monorepo·polyglot(루트에서 한 언어만 감지됨)
#   - kind 오판정
#   - 빈 package.json 을 루트에 만들어 감지 결과를 바꾸는 조작
# 패턴 이름은 언어 간에 겹치지 않으므로(Java 저장소에 tsconfig.json 은 없습니다) 합집합의 오탐 비용은 없습니다.
# 감지 결과는 verify 의 기본 단계 선택과 진단 표시에만 씁니다.
_lang_all_patterns() {
  local list="$1" p up k
  harness_lang_load_packs
  for p in ${HARNESS_LANG_PACKS[@]+"${HARNESS_LANG_PACKS[@]}"}; do
    up="$(_lang_upper "$p")"
    _lang_array_lines "HARNESS_LANG_${up}_${list}_PATTERNS"
    for k in "${HARNESS_LANG_KINDS[@]}"; do
      _lang_array_lines "HARNESS_LANG_${up}_$(_lang_upper "$k")_${list}_PATTERNS"
    done
  done
}

lang_all_protected_patterns() { _lang_all_patterns PROTECTED; }
lang_all_warn_patterns() { _lang_all_patterns WARN; }

# lang_all_security_patterns — 로드된 모든 팩의 보안 패턴을 '|' 로 이어 붙입니다.
lang_all_security_patterns() {
  local p up name out="" v
  harness_lang_load_packs
  for p in ${HARNESS_LANG_PACKS[@]+"${HARNESS_LANG_PACKS[@]}"}; do
    up="$(_lang_upper "$p")"
    name="HARNESS_LANG_${up}_SECURITY_PATTERNS"
    v="${!name:-}"
    [[ -n "$v" ]] || continue
    out="${out:+${out}|}${v}"
  done
  printf '%s' "$out"
}
