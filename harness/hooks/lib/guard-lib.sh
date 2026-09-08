#!/usr/bin/env bash
# guard-lib.sh — hook 공용 판정 자산. 직접 실행하지 않고 source 해서 사용합니다.
#
# 여기 있는 것은 두 hook 이 **같아야만** 하는 것들입니다.
#   - 코어 보호·경고 패턴 목록
#   - 경로 정규화(to_relative)와 패턴 일치(matches_any)
#   - 감사 기록(guard_log_event)
#
# 사전 차단(guard-evaluation-tampering.sh)과 사후 검출(detect-guarded-change.sh)이
# 서로 다른 목록이나 다른 일치 규칙을 쓰면, 한쪽이 막는 것을 다른 쪽이 보지 못하고
# 그 틈이 아무 신호도 내지 않습니다. 복제본이 갈라져도 verify 가 통과하는 문제는
# improvement-log/2026-09-05-002 가 기록한 유형입니다. 그래서 정본을 하나로 둡니다.
#
# 이 파일은 lib/ 에 있어 source 전용입니다. 실행 비트를 요구하지 않습니다.

if [[ -n "${HARNESS_GUARD_LIB_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
HARNESS_GUARD_LIB_LOADED=1

# ---------------------------------------------------------------------------
# 차단 대상: 이 파일들이 바뀌면 평가 결과의 의미가 달라집니다.
#
# 패턴 규칙:
#   - '/' 가 없는 패턴은 경로 전체와 파일명 양쪽에 대해 검사합니다.
#   - '/' 가 있는 패턴은 경로 전체와 하위 경로 접미사 양쪽에 대해 검사합니다.
#     (하네스를 tools/harness/ 로 벤더링하거나 monorepo 하위 패키지를 편집할 때도 걸립니다)
#
# 언어별 목록(eslint, tsconfig, checkstyle, ruff …)은 harness/language/<언어>/lang.sh 가
# 소유하며 감지 결과와 무관하게 모든 팩의 목록이 합쳐집니다.
HARNESS_PROTECTED_PATTERNS=(
  "harness.config"
  "harness.config.local"
  "harness/evaluation/*"
  # 프로젝트가 실체화한 평가 세트. 번들 템플릿과 같은 이유로 에이전트의 자가 수정 대상이 아닙니다.
  "evaluation/*"
  "harness/rules/*"
  "harness/hooks/*"
  # scripts/ 전체를 봅니다. 개별 파일을 열거하면 새 스크립트가 목록에 빠진 채
  # 게이트를 지탱하게 됩니다. 실제로 improvement-log.sh 와 loop.sh 가 그 상태였습니다.
  "harness/scripts/*.sh"
  "harness/scripts/lib/*"
  "harness/language/*/lang.sh"
  # 런타임 산출물 전체입니다. baseline-eval.json 은 회귀 판정의 기준선이라,
  # 점수를 못 올리는 에이전트가 기준선을 낮추면 모든 결과가 개선이 됩니다.
  ".harness/*"
  # 게이트를 지키는 범위에는 게이트의 **실행 조건**이 들어갑니다.
  # hooks/ 를 지키면서 그 hook 을 켜는 파일을 열어 두면, 편집 1회로 PreToolUse 가드와
  # Stop 게이트와 PostToolUse 검출이 함께 사라집니다. 근거: improvement-log/2026-09-05-005.
  # settings.local.json 도 막습니다. hooks 블록을 그쪽에도 쓸 수 있고, env 로
  # HARNESS_ALLOW_GUARDED_EDIT 을 상시로 켜는 것도 그쪽에서 가능합니다.
  ".claude/settings.json"
  ".claude/settings.local.json"
  # 저장소 밖의 심판입니다. 로컬 hook 을 전부 이겨도 여기서 걸리므로 마지막 자리입니다.
  # 다른 워크플로는 경고에 두어 프로젝트의 정상 작업을 막지 않습니다.
  ".github/workflows/harness.yml"
  ".github/CODEOWNERS"
)

# 경고 대상: 차단하지는 않지만 평가에 영향을 줄 수 있어 사실을 알립니다.
HARNESS_WARN_PATTERNS=(
  ".github/workflows/*"
  ".gitlab-ci.yml"
  "sonar-project.properties"
  "codecov.yml"
  "improvement-log/*"
)

# 사후 검출에서 제외할 경로. 스크립트가 매 실행 다시 쓰는 런타임 산출물이라
# 변경 자체가 정상이며, 이것을 검출하면 모든 verify 실행이 경보가 됩니다.
# 차단 목록에는 그대로 남습니다. 사람이 손으로 고치는 것은 여전히 막습니다.
# 이 영역의 무결성은 stop 게이트의 신선도 지문과 eval 재실행이 담당합니다.
HARNESS_DETECT_EXCLUDE_PATTERNS=(
  ".harness/*"
)

# ---------------------------------------------------------------------------
# to_relative <project_root> <path>
# Windows 절대 경로는 역슬래시로 들어옵니다. 정규화하지 않으면 '/' 를 포함한 패턴이 전부 빗나갑니다.
to_relative() {
  local root="$1" path="$2" lroot lpath
  root="${root//\\//}"
  path="${path//\\//}"
  root="${root%/}"
  path="${path#./}"
  if [[ "${path}" == "${root}/"* ]]; then
    printf '%s' "${path#"${root}/"}"
    return 0
  fi
  # Windows 는 드라이브 문자 대소문자가 다를 수 있습니다. hook 은 매 편집마다 도므로 내장만 씁니다.
  lroot="${root,,}"
  lpath="${path,,}"
  if [[ "${lpath}" == "${lroot}/"* ]]; then
    printf '%s' "${path:$((${#root} + 1))}"
    return 0
  fi
  printf '%s' "${path}"
}

# matches_any <rel> <base> <pattern...> — 일치한 패턴을 출력하고 0 을 냅니다.
matches_any() {
  local rel="$1" base="$2" pat=""
  shift 2
  for pat in "$@"; do
    # shellcheck disable=SC2053
    if [[ "${rel}" == ${pat} ]]; then
      printf '%s' "${pat}"
      return 0
    fi
    if [[ "${pat}" == */* ]]; then
      # 경로를 포함한 패턴은 하위 경로에서도 일치시킵니다.
      # 이것이 없으면 하네스를 tools/harness/ 로 벤더링했을 때 가드가 자기 자신을 지키지 못합니다.
      # shellcheck disable=SC2053
      if [[ "${rel}" == */${pat} ]]; then
        printf '%s' "${pat}"
        return 0
      fi
    else
      # shellcheck disable=SC2053
      if [[ "${base}" == ${pat} ]]; then
        printf '%s' "${pat}"
        return 0
      fi
    fi
  done
  return 1
}

# ---------------------------------------------------------------------------
# guard_log_event <project_root> <kind> <path> [detail]
#
# 감사 기록입니다. kind 는 block | bypass | warn | change 입니다.
# 이것이 없으면 "가드가 차단 메시지를 낸 흔적이 없음"(REP-3 의 합격 기준)을
# 관측할 수단이 없고, HARNESS_ALLOW_GUARDED_EDIT 우회는 stderr 한 줄로 사라집니다.
# 승인 자체는 막지 않습니다. 승인이 있었다는 사실을 남길 뿐입니다.
#
# 실패해도 hook 을 죽이지 않습니다. 기록은 판정의 부수 산출이지 판정 자체가 아닙니다.
guard_log_event() {
  local root="${1:-}" kind="${2:-}" path="${3:-}" detail="${4:-}"
  local log_dir="${root}/.harness" ts head line
  local log_path="${log_dir}/guard-events.log"
  [[ -n "${root}" ]] || return 0
  mkdir -p "${log_dir}" 2>/dev/null || return 0
  # 시각과 HEAD 는 프로세스마다 한 번만 구합니다. 이벤트마다 구하면 fork 가 건당 2회
  # 늘어나고, 한 번에 수십 건이 나올 때 hook 이 초 단위로 느려집니다. 실제로 39건에
  # 6.9초가 걸렸습니다. 한 hook 실행 안에서 두 값은 어차피 같습니다.
  [[ -n "${GUARD_LOG_TS:-}" ]] || GUARD_LOG_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || printf 'unknown')"
  [[ -n "${GUARD_LOG_HEAD:-}" ]] || GUARD_LOG_HEAD="$(git -C "${root}" rev-parse --short HEAD 2>/dev/null || printf 'nogit')"
  ts="${GUARD_LOG_TS}"
  head="${GUARD_LOG_HEAD}"
  # 탭 구분입니다. 값 안의 탭과 개행은 공백으로 눕힙니다.
  detail="${detail//$'\t'/ }"
  detail="${detail//$'\n'/ }"
  path="${path//$'\t'/ }"
  line="$(printf '%s\t%s\t%s\t%s\t%s' "${ts}" "${head}" "${kind}" "${path}" "${detail}")"
  printf '%s\n' "${line}" >> "${log_path}" 2>/dev/null || true
  return 0
}
