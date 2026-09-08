#!/usr/bin/env bash
# language/rust/lang.sh — Rust 언어 팩(최소). 직접 실행하지 않고 scripts/lib/detect-stack.sh 가 source 합니다.
# 계약: language/README.md 2절.
#
# 스택 ID : rust
# kind    : backend
# 담당     : Cargo.toml 감지, build·fmt·clippy·test 기본 단계, clippy·rustfmt·cargo-deny 설정 보호 패턴
# 이 팩은 코어 detect-stack.sh 가 원래 제공하던 Rust 감지·단계를 옮긴 최소 팩입니다.
# 문서 예시(examples.md)는 아직 없습니다. 필요하면 language/_template 을 따라 추가합니다.

if [[ -n "${HARNESS_LANG_RUST_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
HARNESS_LANG_RUST_LOADED=1

HARNESS_LANG_PACKS+=(rust)

harness_lang_rust_detect() {
  local root="${1:-$PWD}"
  [[ -f "$root/Cargo.toml" ]] || return 1
  printf 'rust\n'
}

harness_lang_rust_kind() {
  printf 'backend\n'
}

harness_lang_rust_default_steps() {
  local stack="${1:-rust}" root="${2:-$PWD}" kind="${3:-backend}"
  _emit_step build correctness true "cargo build --locked"
  _emit_step fmt quality false "cargo fmt --check"
  _emit_step clippy quality false "cargo clippy -- -D warnings"
  if [[ -f "$root/deny.toml" ]]; then
    _emit_step deny architecture false "cargo deny check"
  fi
  _emit_step test correctness true "cargo test"
}

# 차단: lint·포맷·의존성 정책 파일.
HARNESS_LANG_RUST_PROTECTED_PATTERNS=(
  "clippy.toml"
  ".clippy.toml"
  "rustfmt.toml"
  ".rustfmt.toml"
  "deny.toml"
  ".cargo/audit.toml"
)

# 경고: 매니페스트와 빌드 스크립트. feature 플래그로 테스트가 빠질 수 있습니다.
HARNESS_LANG_RUST_WARN_PATTERNS=(
  "Cargo.toml"
  "Cargo.lock"
  ".cargo/config.toml"
  "build.rs"
)

HARNESS_LANG_RUST_SECURITY_PATTERNS='\.cargo/credentials(\.toml)?$'
