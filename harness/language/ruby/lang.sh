#!/usr/bin/env bash
# language/ruby/lang.sh — Ruby 언어 팩(최소). 직접 실행하지 않고 scripts/lib/detect-stack.sh 가 source 합니다.
# 계약: language/README.md 2절.
#
# 스택 ID : ruby
# kind    : backend
# 담당     : Gemfile 감지, rubocop lint·테스트 기본 단계, RuboCop 설정 보호 패턴
# 문서 예시(examples.md)는 아직 없습니다. 필요하면 language/_template 을 따라 추가합니다.

if [[ -n "${HARNESS_LANG_RUBY_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
HARNESS_LANG_RUBY_LOADED=1

HARNESS_LANG_PACKS+=(ruby)

# --- 감지 ---------------------------------------------------------------------
# Bundler 가 Ruby 프로젝트의 사실상 유일한 의존성 관리 도구이므로 변형을 두지 않습니다.
# gems.rb 는 Bundler 가 지원하는 Gemfile 의 대체 이름입니다.
harness_lang_ruby_detect() {
  local root="${1:-$PWD}"
  [[ -f "$root/Gemfile" || -f "$root/gems.rb" ]] || return 1
  printf 'ruby\n'
}

# Rails 도 산출물이 서버에서 실행되므로 backend 입니다(language/README.md 1.1절 정의).
harness_lang_ruby_kind() {
  printf 'backend\n'
}

# --- 기본 verify 단계 -------------------------------------------------------------
# Ruby 에는 언제나 성립하는 빌드 단계가 없습니다. 설정·디렉터리가 있는 것만 단계로 냅니다.
# 무조건 내면 rubocop 미설치는 exit 127, rspec 은 테스트가 없어도 실패해 첫 verify 가 그 자리에서 멈춥니다.
harness_lang_ruby_default_steps() {
  local stack="${1:-ruby}" root="${2:-$PWD}" kind="${3:-backend}"
  # Gemfile.lock 이 있으면 잠긴 버전으로 실행합니다. 없으면 전역에 설치된 실행 파일을 가정합니다.
  local p=""
  [[ -f "$root/Gemfile.lock" || -f "$root/gems.locked" ]] && p="bundle exec "

  if [[ -f "$root/.rubocop.yml" || -f "$root/.rubocop.yaml" ]]; then
    _emit_step lint quality false "${p}rubocop"
  fi

  # packwerk: 패키지 경계 규칙 (architecture 계층).
  if [[ -f "$root/packwerk.yml" ]]; then
    _emit_step arch-test architecture true "${p}packwerk check"
  fi

  if [[ -f "$root/.rspec" || -d "$root/spec" ]]; then
    _emit_step test correctness true "${p}rspec"
  elif [[ -f "$root/Rakefile" && -d "$root/test" ]]; then
    _emit_step test correctness true "${p}rake test"
  fi
}

# --- 보호 패턴 -----------------------------------------------------------------
# 차단: lint 규칙·예외 목록, 테스트 기본 옵션, 커버리지 임계값, 패키지 경계 규칙.
# .rubocop_todo.yml 은 기존 위반을 통째로 제외하는 목록이라 quality 위반 동결과 같습니다.
HARNESS_LANG_RUBY_PROTECTED_PATTERNS=(
  ".rubocop.yml"
  ".rubocop.yaml"
  ".rubocop_todo.yml"
  ".rspec"
  ".simplecov"
  "packwerk.yml"
)

# 경고: 의존성 매니페스트와 테스트 헬퍼. 의존성 변경은 정상이지만
# Rakefile 의 기본 task 와 spec 헬퍼에서 테스트 범위가 바뀝니다.
HARNESS_LANG_RUBY_WARN_PATTERNS=(
  "Gemfile"
  "Gemfile.lock"
  "gems.rb"
  "gems.locked"
  "*.gemspec"
  "Rakefile"
  ".ruby-version"
  "spec/spec_helper.rb"
  "test/test_helper.rb"
)

# 보안 민감 경로: RubyGems API 키, Rails 자격 증명 키, 프라이빗 gem 소스 토큰.
HARNESS_LANG_RUBY_SECURITY_PATTERNS='\.gem/credentials$|config/master\.key$|config/credentials/.*\.key$|\.bundle/config$'
