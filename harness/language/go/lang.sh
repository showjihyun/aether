#!/usr/bin/env bash
# language/go/lang.sh — Go 언어 팩(최소). 직접 실행하지 않고 scripts/lib/detect-stack.sh 가 source 합니다.
# 계약: language/README.md 2절.
#
# 스택 ID : go
# kind    : backend
# 담당     : go.mod 감지, build·vet·test 기본 단계, golangci-lint 설정 보호 패턴
# 이 팩은 코어 detect-stack.sh 가 원래 제공하던 Go 감지·단계를 옮긴 최소 팩입니다.
# 문서 예시(examples.md)는 아직 없습니다. 필요하면 language/_template 을 따라 추가합니다.

if [[ -n "${HARNESS_LANG_GO_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
HARNESS_LANG_GO_LOADED=1

HARNESS_LANG_PACKS+=(go)

harness_lang_go_detect() {
  local root="${1:-$PWD}"
  [[ -f "$root/go.mod" ]] || return 1
  printf 'go\n'
}

harness_lang_go_kind() {
  printf 'backend\n'
}

harness_lang_go_default_steps() {
  local stack="${1:-go}" root="${2:-$PWD}" kind="${3:-backend}"
  _emit_step build correctness true "go build ./..."
  _emit_step vet quality true "go vet ./..."
  if [[ -f "$root/.golangci.yml" || -f "$root/.golangci.yaml" || -f "$root/.golangci.toml" || -f "$root/.golangci.json" ]]; then
    _emit_step lint quality false "golangci-lint run ./..."
  fi
  _emit_step test correctness true "go test ./..."
}

# 차단: lint 규칙과 아키텍처 규칙 파일.
HARNESS_LANG_GO_PROTECTED_PATTERNS=(
  ".golangci.yml"
  ".golangci.yaml"
  ".golangci.toml"
  ".golangci.json"
  "staticcheck.conf"
  ".go-arch-lint.yml"
)

# 경고: 모듈 정의와 빌드 스크립트. 테스트 태그·빌드 제약이 여기서 바뀝니다.
HARNESS_LANG_GO_WARN_PATTERNS=(
  "go.mod"
  "go.sum"
  "go.work"
  "Makefile"
  "tools.go"
)

HARNESS_LANG_GO_SECURITY_PATTERNS='\.netrc$'
