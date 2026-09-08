#!/usr/bin/env bash
# language/python/lang.sh — Python 언어 팩. 직접 실행하지 않고 scripts/lib/detect-stack.sh 가 source 합니다.
# 계약: language/README.md 2절.
#
# 스택 ID : python | python:uv | python:poetry | python:pdm | python:pipenv
# kind    : backend
# 담당     : pyproject/requirements 감지, ruff·mypy·pytest·import-linter 기본 단계,
#            ruff·flake8·mypy·pytest·import-linter 설정 보호 패턴

if [[ -n "${HARNESS_LANG_PYTHON_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
HARNESS_LANG_PYTHON_LOADED=1

HARNESS_LANG_PACKS+=(python)

# --- 감지 ---------------------------------------------------------------------
harness_lang_python_detect() {
  local root="${1:-$PWD}"
  if [[ -f "$root/pyproject.toml" || -f "$root/requirements.txt" \
     || -f "$root/setup.py" || -f "$root/setup.cfg" || -f "$root/Pipfile" ]]; then
    if [[ -f "$root/uv.lock" ]]; then
      printf 'python:uv\n'
    elif [[ -f "$root/poetry.lock" ]]; then
      printf 'python:poetry\n'
    elif [[ -f "$root/pdm.lock" ]]; then
      printf 'python:pdm\n'
    elif [[ -f "$root/Pipfile.lock" || -f "$root/Pipfile" ]]; then
      printf 'python:pipenv\n'
    else
      printf 'python\n'
    fi
    return 0
  fi
  return 1
}

# Python 팩은 서버·배치·CLI·데이터 파이프라인을 대상으로 합니다.
harness_lang_python_kind() {
  printf 'backend\n'
}

# --- 명령 접두사 ----------------------------------------------------------------
# lockfile 과 도구가 모두 있을 때만 접두사를 붙입니다. 도구가 없으면 활성화된 venv 를 가정합니다.
harness_lang_python_run_prefix() {
  local root="$1" stack="${2:-}"
  case "$stack" in
    python:uv)     have_cmd uv && printf 'uv run ' ;;
    python:poetry) have_cmd poetry && printf 'poetry run ' ;;
    python:pdm)    have_cmd pdm && printf 'pdm run ' ;;
    python:pipenv) have_cmd pipenv && printf 'pipenv run ' ;;
    *) printf '' ;;
  esac
  return 0
}

# pyproject.toml 에 [tool.<name>] 섹션이 있는지.
harness_lang_python_has_tool_section() {
  local root="$1" tool="$2"
  [[ -f "$root/pyproject.toml" ]] || return 1
  grep -qE "^\[tool\.${tool}(\.|\])" "$root/pyproject.toml" 2>/dev/null
}

# --- 기본 verify 단계 -------------------------------------------------------------
# 설정 파일이 있는 도구만 단계로 넣습니다. 설치되지 않은 도구를 무조건 부르면 verify 가 항상 실패합니다.
harness_lang_python_default_steps() {
  local stack="${1:-python}" root="${2:-$PWD}" kind="${3:-backend}"
  local p
  p="$(harness_lang_python_run_prefix "$root" "$stack")"

  if [[ -f "$root/ruff.toml" || -f "$root/.ruff.toml" ]] || harness_lang_python_has_tool_section "$root" ruff; then
    _emit_step lint quality false "${p}ruff check ."
    _emit_step format-check quality false "${p}ruff format --check ."
  elif [[ -f "$root/.flake8" ]]; then
    _emit_step lint quality false "${p}flake8"
  fi

  if [[ -f "$root/mypy.ini" || -f "$root/.mypy.ini" ]] || harness_lang_python_has_tool_section "$root" mypy; then
    _emit_step typecheck quality false "${p}mypy ."
  elif [[ -f "$root/pyrightconfig.json" ]] || harness_lang_python_has_tool_section "$root" pyright; then
    _emit_step typecheck quality false "${p}pyright"
  fi

  # import-linter: 계층·패키지 의존 방향 규칙 (architecture 계층).
  if [[ -f "$root/.importlinter" ]] || harness_lang_python_has_tool_section "$root" importlinter; then
    _emit_step arch-test architecture true "${p}lint-imports"
  fi

  # 테스트 단계도 다른 단계와 같은 규약을 따릅니다. "있으면 실행되는" 것만 냅니다.
  # 무조건 내면 테스트가 아직 없는 저장소에서 pytest 가 exit 5(수집된 테스트 없음),
  # 미설치 환경에서 exit 127 을 내고, required=true 라 첫 verify 가 그 자리에서
  # 멈춥니다. go 의 go test ./... 나 rust 의 cargo test 는 테스트가 없어도 0 이라
  # 무조건 내도 무해하지만 pytest 는 그렇지 않습니다.
  if [[ -d "$root/tests" || -d "$root/test" ]] \
    || [[ -f "$root/pytest.ini" || -f "$root/tox.ini" || -f "$root/setup.cfg" ]] \
    || harness_lang_python_has_tool_section "$root" pytest; then
    _emit_step test correctness true "${p}pytest -q"
  fi
}

# --- 보호 패턴 -----------------------------------------------------------------
# 차단: lint·타입·테스트·아키텍처 규칙 파일. 바뀌면 quality/architecture/correctness 계층의 의미가 달라집니다.
HARNESS_LANG_PYTHON_PROTECTED_PATTERNS=(
  "ruff.toml"
  ".ruff.toml"
  ".flake8"
  "mypy.ini"
  ".mypy.ini"
  "pyrightconfig.json"
  ".pylintrc"
  "pylintrc"
  "pytest.ini"
  ".importlinter"
  ".coveragerc"
  ".bandit"
)

# 경고: 의존성과 도구 설정이 한 파일에 섞여 있습니다. [tool.ruff] 완화는 리뷰가 잡아야 합니다.
HARNESS_LANG_PYTHON_WARN_PATTERNS=(
  "pyproject.toml"
  "setup.cfg"
  "setup.py"
  "tox.ini"
  "conftest.py"
  "requirements*.txt"
  "requirements/*"
  "Pipfile"
  "uv.lock"
  "poetry.lock"
  "pdm.lock"
)

# 보안 민감 경로: 패키지 인덱스 자격 증명.
HARNESS_LANG_PYTHON_SECURITY_PATTERNS='\.pypirc$|\.netrc$|pip\.conf$'
