#!/usr/bin/env bash
# self-check.sh — 하네스 번들 자신이 성립하는지 검사합니다.
#
# 대상 프로젝트의 코드가 아니라 **하네스 설치 상태**를 봅니다. 하네스를 처음 붙인 직후,
# 언어 팩을 추가한 뒤, 그리고 verify 단계로 등록해 매 검증마다 자동으로 실행합니다.
#
# 이 스크립트가 존재하는 이유:
#   언어 팩 계약, 보호 패턴 병합, 문서 링크는 전부 기계로 판정할 수 있는데 문서로만 규정하면
#   어겨져도 아무 신호가 나지 않습니다. 특히 팩이 계약을 어기면 guard hook 의 보호 목록이
#   조용히 줄어듭니다. 그 판정을 지시문(EL-1)에서 검증(EL-5)으로 올리는 것이 이 스크립트입니다.
#   근거: improvement-log 2026-09-03-002, rules/lesson-placement.rule.md LP-1.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck disable=SC1090,SC1091
source "${SCRIPT_DIR}/lib/common.sh"

# 프로젝트 설정을 읽습니다. HARNESS_SELF_CHECK_LINK_DIRS 를 여기서 가져옵니다.
# verify.sh 가 각 단계를 bash -c 로 띄우므로 부모의 변수는 전달되지 않습니다.
# (guard hook 과 달리 이 스크립트는 사람이 실행하는 검증 명령이라 설정을 읽어도 됩니다.)
HARNESS_PROJECT_ROOT_RESOLVED="$(find_project_root "$PWD")"
load_config "${HARNESS_PROJECT_ROOT_RESOLVED}" || true

usage() {
  cat <<'USAGE'
사용법: self-check.sh [옵션]

하네스 번들 자신의 무결성을 검사합니다. 대상 프로젝트의 코드는 보지 않습니다.

검사 항목:
  syntax      번들의 모든 bash 스크립트가 파싱되고 진입점에 실행 비트가 있는가
  packs       언어 팩이 하나 이상 로드되고 전부 계약을 지키는가
  protection  보호 패턴이 감지와 무관하게 모든 팩의 합집합으로 병합되는가
  links       번들 안 마크다운의 상대 링크가 전부 실재하는가
              HARNESS_SELF_CHECK_LINK_DIRS 로 프로젝트 문서를 검사 대상에 더할 수 있습니다
  log-schema  번들이 제공하는 improvement-log 예시가 스키마를 만족하는가
  inventory   번들의 스크립트가 README 트리에 전부 등장하는가

옵션:
  --only <검사>   지정한 검사만 실행합니다. 여러 번 지정할 수 있습니다.
  --list          검사 목록만 출력합니다.
  -h, --help      이 도움말을 출력합니다.

종료 코드:
  0  모든 검사 통과
  1  하나 이상 실패
  3  인자가 잘못되었습니다
USAGE
}

CHECKS=(syntax packs protection links log-schema inventory)
ONLY=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --list) printf '%s\n' "${CHECKS[@]}"; exit 0 ;;
    --only)
      [[ $# -ge 2 ]] || die "--only 에는 검사 이름이 필요합니다." 3
      ONLY+=("$2"); shift 2 ;;
    --only=*) ONLY+=("${1#*=}"); shift ;;
    *) die "알 수 없는 옵션입니다: $1 (--help 를 보십시오)" 3 ;;
  esac
done

selected() {
  [[ ${#ONLY[@]} -eq 0 ]] && return 0
  local o
  for o in "${ONLY[@]}"; do [[ "$o" == "$1" ]] && return 0; done
  return 1
}

FAILED=0
report_pass() { printf '  [ok]   %s — %s\n' "$1" "$2"; }
report_fail() { printf '  [FAIL] %s — %s\n' "$1" "$2"; FAILED=$((FAILED + 1)); }

printf '하네스 자기 점검: %s\n\n' "${HARNESS_DIR}"

# --- 1. syntax -----------------------------------------------------------------
if selected syntax; then
  bad=""
  while IFS= read -r f; do
    bash -n "$f" 2>/dev/null || bad="${bad} ${f#"${HARNESS_DIR}/"}"
  done < <(find "${HARNESS_DIR}" -name '*.sh' -type f)

  # 직접 실행되는 진입점은 git 인덱스에 실행 비트를 가져야 합니다.
  # 작업 트리 권한이 아니라 인덱스를 보는 이유: core.fileMode=false 인 환경(Windows)에서는
  # 작업 트리가 항상 실행 가능해 보이지만 인덱스에는 100644 로 들어가고, 그 상태로 clone 한
  # 쪽에서 hook 과 verify 진입점이 exit 126 으로 죽습니다. 126 은 0 도 2 도 아니므로
  # stop 게이트와 평가 가드가 "차단 없음"으로 읽혀 조용히 사라집니다.
  # scripts/ 와 hooks/ 의 depth 1 만 봅니다. lib/ 와 language/ 의 팩은 source 전용입니다.
  noexec=""
  if git -C "${HARNESS_PROJECT_ROOT_RESOLVED}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    while IFS= read -r f; do
      rel="${f#"${HARNESS_PROJECT_ROOT_RESOLVED}/"}"
      mode="$(git -C "${HARNESS_PROJECT_ROOT_RESOLVED}" ls-files -s -- "$rel" 2>/dev/null | awk '{print $1}')"
      [[ -z "$mode" ]] && continue   # 아직 추적되지 않는 파일은 판정하지 않습니다
      [[ "$mode" == "100755" ]] || noexec="${noexec} ${rel}"
    done < <(find "${HARNESS_DIR}/scripts" "${HARNESS_DIR}/hooks" -maxdepth 1 -name '*.sh' -type f)
  fi

  if [[ -n "$bad" ]]; then
    report_fail syntax "파싱 실패:${bad}"
  elif [[ -n "$noexec" ]]; then
    report_fail syntax "git 인덱스에 실행 비트가 없습니다(clone 하면 exit 126):${noexec} — git update-index --chmod=+x 로 고칩니다"
  else
    report_pass syntax "모든 bash 스크립트가 파싱되고 진입점에 실행 비트가 있습니다"
  fi
fi

# --- 2. packs ------------------------------------------------------------------
# 팩 로더를 서브셸에서 돌려 계약 위반 개수와 로드된 팩 수를 회수합니다.
if selected packs; then
  pack_out="$(
    # shellcheck disable=SC1090,SC1091
    source "${SCRIPT_DIR}/lib/detect-stack.sh" 2>/dev/null || exit 9
    harness_lang_load_packs 2>/dev/null || true
    printf '%s|%s\n' "${#HARNESS_LANG_PACKS[@]}" "${HARNESS_LANG_PACK_PROBLEMS:-0}"
  )" || pack_out="0|9"
  pack_count="${pack_out%%|*}"
  pack_problems="${pack_out##*|}"
  if [[ "$pack_count" -eq 0 ]]; then
    report_fail packs "언어 팩을 하나도 로드하지 못했습니다. 언어별 보호와 기본 단계가 없습니다"
  elif [[ "$pack_problems" -ne 0 ]]; then
    report_fail packs "계약을 어긴 팩 ${pack_problems}개가 비활성화되었습니다 (사유는 위 stderr)"
  else
    report_pass packs "팩 ${pack_count}개가 전부 계약을 지킵니다"
  fi
fi

# --- 3. protection --------------------------------------------------------------
# 보호 목록이 감지에 의존하지 않는지 확인합니다. 스택을 감지할 수 없는 디렉터리에서
# guard --list 를 돌려도 언어별 패턴이 나와야 합니다.
if selected protection; then
  guard="${HARNESS_DIR}/hooks/guard-evaluation-tampering.sh"
  if [[ ! -x "$guard" && ! -f "$guard" ]]; then
    report_fail protection "guard-evaluation-tampering.sh 를 찾을 수 없습니다"
  else
    empty_dir="$(mktemp -d)"
    nolang_dir="$(mktemp -d)"
    trap 'rm -rf "${empty_dir}" "${nolang_dir}"' EXIT
    _blocked_count() { sed -n '/^blocked:/,/^warned:/p' | grep -c '^  ' || true; }
    # 팩을 병합한 목록과, 팩 디렉터리를 비워 코어만 남긴 목록을 각각 셉니다.
    # 상수와 비교하지 않는 이유: 코어 목록이 자라면 상수가 조용히 추월당해
    # "팩이 병합되었는가" 단정이 영원히 통과합니다. 실제로 상수 12 는 코어 14 에
    # 추월당해 죽어 있었습니다. 두 실측값을 비교하면 그 부패가 생기지 않습니다.
    listing="$(CLAUDE_PROJECT_DIR="${empty_dir}" bash "$guard" --list 2>/dev/null || true)"
    blocked="$(printf '%s' "$listing" | _blocked_count)"
    core_only="$(CLAUDE_PROJECT_DIR="${empty_dir}" HARNESS_LANGUAGE_DIR="${nolang_dir}" \
      bash "$guard" --list 2>/dev/null | _blocked_count || true)"
    if [[ "$blocked" -le "$core_only" ]]; then
      report_fail protection "스택 미감지 상태의 차단 패턴 ${blocked}개가 코어 단독 ${core_only}개보다 많지 않습니다. 언어별 보호가 병합되지 않았습니다"
    else
      # 대표 패턴 몇 개가 실제로 차단되는지 확인합니다.
      miss=""
      # 파일명 패턴과 **경로 패턴**을 함께 봅니다. 파일명만 보면 to_relative 나 경로
      # 일치 규칙이 깨져도 이 검사가 통과합니다. 실제로 보호 목록을 hooks/lib/guard-lib.sh
      # 로 옮길 때 to_relative 의 이스케이프가 깨져 경로에서 "/" 를 전부 지웠고,
      # harness/scripts/*.sh 를 포함한 모든 경로 패턴이 빗나갔는데 이 검사는 통과했습니다.
      # 파일명 탐침만으로는 죽은 단언이 됩니다.
      for p in tsconfig.json checkstyle.xml ruff.toml .golangci.yml clippy.toml .rubocop.yml \
               harness/scripts/verify.sh harness/rules/RULES.md .harness/verify.json \
               .claude/settings.json .github/workflows/harness.yml; do
        c=0
        printf '{"tool_input":{"file_path":"%s"}}' "$p" \
          | CLAUDE_PROJECT_DIR="${empty_dir}" bash "$guard" >/dev/null 2>&1 || c=$?
        [[ "$c" -eq 2 ]] || miss="${miss} ${p}"
      done
      if [[ -n "$miss" ]]; then
        report_fail protection "스택 미감지 상태에서 차단되지 않은 파일:${miss}"
      else
        report_pass protection "보호 패턴 ${blocked}개(코어 ${core_only} + 팩)가 감지와 무관하게 병합됩니다"
      fi
    fi
  fi
fi

# --- 4. links ------------------------------------------------------------------
if selected links; then
  # 기본 대상은 번들입니다. 프로젝트가 자기 문서도 함께 검사하려면
  # harness.config 에서 HARNESS_SELF_CHECK_LINK_DIRS 에 프로젝트 루트 기준 상대 경로를 공백으로 나열합니다.
  # 채택하지 않은 프로젝트의 문서를 임의로 훑으면 의도적인 외부 링크까지 실패로 잡히므로 기본값은 번들뿐입니다.
  link_roots=("${HARNESS_DIR}")
  missing_roots=""
  if [[ -n "${HARNESS_SELF_CHECK_LINK_DIRS:-}" ]]; then
    _proj="${HARNESS_PROJECT_ROOT_RESOLVED}"
    for _d in ${HARNESS_SELF_CHECK_LINK_DIRS}; do
      if [[ -e "${_proj}/${_d}" ]]; then
        link_roots+=("${_proj}/${_d}")
      else
        missing_roots="${missing_roots} ${_d}"
      fi
    done
  fi
  broken=""
  count=0
  while IFS= read -r f; do
    d="$(dirname "$f")"
    while IFS= read -r link; do
      target="${link%%#*}"
      [[ -n "$target" ]] || continue
      count=$((count + 1))
      [[ -e "${d}/${target}" ]] || broken="${broken}\n    ${f#"${HARNESS_DIR}/"} -> ${link}"
    done < <(grep -oE '\]\([^)]+\)' "$f" | sed -E 's/^\]\((.*)\)$/\1/' | grep -vE '^(http|mailto)' || true)
  done < <(find "${link_roots[@]}" -name '*.md' -type f)
  # 한 검사는 한 줄만 보고합니다. 예전에는 없는 경로를 만나면 그 자리에서
  # report_fail 하고도 아래까지 흘러가 [FAIL] 과 [ok] 를 둘 다 출력했습니다.
  # verify.sh 는 로그의 마지막 줄을 verify.json 의 summary 로 쓰므로,
  # 기계가 읽는 결과에는 성공 메시지가 실패 사유로 기록되었습니다.
  if [[ -n "$missing_roots" ]]; then
    report_fail links "HARNESS_SELF_CHECK_LINK_DIRS 의 경로가 없습니다:${missing_roots}"
  elif [[ -n "$broken" ]]; then
    report_fail links "끊어진 링크:$(printf '%b' "$broken")"
  else
    report_pass links "상대 링크 ${count}건이 전부 실재합니다 (대상 ${#link_roots[@]}곳)"
  fi
fi

# --- 5. log-schema --------------------------------------------------------------
if selected log-schema; then
  examples=()
  while IFS= read -r f; do examples+=("$f"); done < <(
    find "${HARNESS_DIR}" -name '*improvement-log*.yaml' -o -name '*.example.yaml' | sort -u
  )
  # 프로젝트가 실제로 쌓은 로그도 함께 봅니다. 번들 예시만 검사하면 진짜 로그의
  # 스키마 위반이 그대로 통과합니다. 이 단계가 지키려는 것은 예시가 아니라 로그입니다.
  proj_log="${HARNESS_PROJECT_ROOT_RESOLVED}/improvement-log"
  if [[ -d "$proj_log" ]]; then
    while IFS= read -r f; do examples+=("$f"); done < <(find "$proj_log" -name '*.yaml' -type f | sort)
  fi
  if [[ ${#examples[@]} -eq 0 ]]; then
    # 입력이 0건인 것은 통과가 아닙니다. 번들은 항상 예시를 싣고 있으므로
    # 0건은 예시가 제거되었다는 뜻이고, 통과 처리하면 게이트를 지우는 것이
    # 게이트를 초록으로 만드는 방법이 됩니다.
    report_fail log-schema "검사할 예시가 하나도 없습니다. 번들의 improvement-log 예시가 제거되었는지 확인하십시오"
  elif out="$("${SCRIPT_DIR}/improvement-log.sh" validate "${examples[@]}" 2>&1)"; then
    report_pass log-schema "예시·로그 ${#examples[@]}건이 스키마를 만족합니다"
  else
    report_fail log-schema "$(printf '%s' "$out" | tail -n 5)"
  fi
fi

# --- 6. inventory ---------------------------------------------------------------
# 번들의 스크립트가 README 트리에 등장하는가.
#
# links 검사는 마크다운 링크의 **대상이 존재하는지**만 봅니다. 파일을 추가하고 트리를
# 갱신하지 않으면 링크가 끊기지 않으므로 아무 신호도 나오지 않습니다. 실제로
# self-check.sh 는 이 저장소의 다섯 단계를 전부 수행하면서도 트리에 없었고, 그 사실이
# 오래 드러나지 않았습니다. 2026-09-06 라운드에서 추가한 세 파일도 같은 상태였습니다.
#
# 이 검사가 EL-5 로 올리는 지침: "파일을 추가하면 README 트리도 갱신한다."
# 근거: improvement-log/2026-09-04-001 (개수 표기와 실제가 어긋나는 것을 기계가 보지 않음),
#       2026-09-05-001 (문서와 구현의 불일치가 리뷰 전까지 신호를 내지 않음). GC-7.
#
# 파일명만 봅니다. 경로까지 요구하면 트리의 요약 표기(_template/ (README.md, lang.sh, …))를
# 전부 펼쳐야 하고, 그 형식은 사람이 읽기 위한 것이라 강제 대상이 아닙니다.
if selected inventory; then
  readme="${HARNESS_DIR}/README.md"
  if [[ ! -f "$readme" ]]; then
    report_fail inventory "번들 README 를 찾을 수 없습니다: ${readme}"
  else
    # 트리 블록 안에서만 찾습니다. 파일 전체를 보면 산문에 한 번 언급된 것만으로
    # 통과해 검사가 죽습니다. 첫 구현이 그랬고, 트리에서 self-check.sh 를 지워도
    # 통과했습니다. 자기 자신을 지키는 검사도 죽은 단언이 될 수 있습니다.
    tree=""
    in_tree=0
    while IFS= read -r line; do
      # CR 을 떼어냅니다. autocrlf 가 켜진 체크아웃에서는 이 파일이 CRLF 로 오고,
      # 그때 트리 시작 표시와 읽은 줄이 CR 하나 때문에 달라져 블록을 영영 못 찾습니다.
      # 리눅스 CI 는 LF 라 통과하므로 이 결함은 CI 로 잡히지 않습니다. 실제로 CI 가
      # 초록인 상태로 병합된 main 이 Windows 체크아웃에서 이 단계로 실패했습니다.
      # improvement-log.sh 의 il_parse_file 이 같은 이유로 같은 처리를 합니다.
      line="${line%$'\r'}"
      if [[ "$in_tree" -eq 0 ]]; then
        [[ "$line" == '```text' ]] && in_tree=1
        continue
      fi
      [[ "$line" == '```' ]] && break
      tree="${tree}${line}"$'\n'
    done < "$readme"
    missing=""
    count=0
    while IFS= read -r f; do
      count=$((count + 1))
      b="${f##*/}"
      [[ "$tree" == *"${b}"* ]] || missing="${missing} ${f#"${HARNESS_DIR}/"}"
    done < <(find "${HARNESS_DIR}" -name '*.sh' -type f | sort)
    if [[ -z "$tree" ]]; then
      report_fail inventory "README 에서 파일 트리 블록을 찾지 못했습니다"
    elif [[ "$count" -eq 0 ]]; then
      report_fail inventory "번들에서 스크립트를 하나도 찾지 못했습니다"
    elif [[ -n "$missing" ]]; then
      report_fail inventory "README 트리에 없는 스크립트:${missing} — harness/README.md 를 갱신합니다"
    else
      report_pass inventory "스크립트 ${count}개가 전부 README 트리에 등장합니다"
    fi
  fi
fi

printf '\n'
if [[ "$FAILED" -eq 0 ]]; then
  printf '자기 점검 통과.\n'
  exit 0
fi
printf '자기 점검 실패: %s건.\n' "$FAILED"
printf '하네스가 성립하지 않는 상태입니다. 대상 코드를 고치기 전에 이것부터 해소하십시오.\n'
exit 1
