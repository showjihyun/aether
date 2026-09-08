#!/usr/bin/env bash
# language/_template/lang.sh — 새 언어 팩의 뼈대입니다.
# 직접 실행하지 않습니다. scripts/lib/detect-stack.sh 가 source 합니다. 계약: language/README.md 2절.
#
# 이 파일은 _template/ 아래에 있는 동안 로더가 건너뜁니다. 새 팩을 만들 때는 다음처럼 복사하고
# 자리표시자 mylang / MYLANG 을 실제 언어 이름(디렉터리 이름과 동일)으로 바꿉니다.
#
#   cp -r harness/language/_template harness/language/<언어>
#   sed -i 's/mylang/<언어>/g; s/MYLANG/<언어 대문자>/g' harness/language/<언어>/lang.sh
#
# <파일>, <명령> 같은 꺾쇠 자리표시자는 프로젝트에 맞는 값으로 채웁니다.

if [[ -n "${HARNESS_LANG_MYLANG_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
HARNESS_LANG_MYLANG_LOADED=1

# 1. 팩 등록 — 디렉터리 이름과 같아야 합니다.
HARNESS_LANG_PACKS+=(mylang)

# 2. 감지 — 스택 ID 를 출력하고, 감지되지 않으면 return 1.
#    파일 존재만으로 판정합니다. 빌드 도구를 실행하지 않습니다.
harness_lang_mylang_detect() {
  local root="${1:-$PWD}"
  if [[ -f "$root/<빌드 파일>" ]]; then
    if [[ -f "$root/<lockfile>" ]]; then
      printf 'mylang:<변형>\n'
    else
      printf 'mylang\n'
    fi
    return 0
  fi
  return 1
}

# 3. kind — frontend | backend | fullstack | unknown
harness_lang_mylang_kind() {
  local root="${1:-$PWD}" stack="${2:-}"
  printf 'backend\n'
}

# 4. 기본 verify 단계 — "id|layer|required|command" 줄 목록.
#    layer 는 correctness | architecture | quality | behavior | performance | subjective.
#    있으면 실행되는 단계만 냅니다.
harness_lang_mylang_default_steps() {
  local stack="${1:-mylang}" root="${2:-$PWD}" kind="${3:-backend}"
  _emit_step build correctness true "<빌드 명령>"
  if [[ -f "$root/<lint 설정 파일>" ]]; then
    _emit_step lint quality false "<lint 명령>"
  fi
  _emit_step test correctness true "<테스트 명령>"
}

# 5. 보호 패턴 — guard-evaluation-tampering.sh 가 코어 패턴에 합칩니다.
#    '/' 가 없는 패턴은 경로 전체와 파일명 양쪽에 대해 검사됩니다.
HARNESS_LANG_MYLANG_PROTECTED_PATTERNS=(
  "<lint 설정 파일>"
)
HARNESS_LANG_MYLANG_WARN_PATTERNS=(
  "<의존성 매니페스트>"
)

# 6. (선택) 보안 민감 경로 — loop.sh 의 SECURITY_PATTERNS 에 덧붙일 ERE 조각.
HARNESS_LANG_MYLANG_SECURITY_PATTERNS=''

# 7. (선택) kind 별 추가 패턴. 이름은 HARNESS_LANG_MYLANG_FRONTEND_* / _BACKEND_* 입니다.
# HARNESS_LANG_MYLANG_BACKEND_PROTECTED_PATTERNS=()
# HARNESS_LANG_MYLANG_BACKEND_WARN_PATTERNS=()
