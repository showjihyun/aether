#!/usr/bin/env bash
# improvement-log.sh — improvement log 후보를 만들고 조회하고 검증하는 CLI 입니다.
# improvement-log/schema.md 의 키 목록과 순서, enum 값을 강제합니다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck disable=SC1090,SC1091
source "${SCRIPT_DIR}/lib/common.sh"

# _need_value <플래그> [값...] — 값이 따라오지 않으면 exit 3 으로 멈춥니다.
#
# shift 2 를 무조건 하면 인자가 하나뿐일 때 set -e 가 스크립트를 조용히
# 종료시킵니다. 호출자는 출력 없는 exit 1 만 보고, usage 는 1 을 "검증 위반
# 또는 허용되지 않은 전이" 로 문서화하므로 인자 실수가 스키마 위반으로
# 오독됩니다. 인자 오류의 규약 코드는 3 입니다.
_need_value() {
  [[ $# -ge 2 ]] || die "${1} 에는 값이 필요합니다." 3
}

usage() {
  cat <<'USAGE'
사용법: improvement-log.sh <명령> [옵션]

명령:
  new [옵션]                 다음 id(YYYY-MM-DD-NNN)를 계산해 후보 파일을 만듭니다.
  list [--status <S>]        id / status / recurrence_risk / symptom 요약 표를 출력합니다.
  validate [파일...]         스키마를 검증합니다. 파일을 주지 않으면 improvement-log/ 전체를 봅니다.
  set-status <id> <status>   허용된 전이만 수행합니다.
  -h, --help                 이 도움말을 출력합니다.

new 의 옵션 (주지 않으면 빈 값으로 둡니다):
  --symptom <문장>                  --evidence <문장>
  --root-cause <문장>               --fix <문장>
  --recurrence-risk <low|medium|high>
  --harness-element <HE-1..HE-15>   --proposed-harness-change <문장>
  --preferred-enforcement <test|lint|arch-rule|hook|script|doc|skill|subagent|instruction>
  --trust <untrusted|validated>     --regression-check <문장>
  --owner <이름>                    --expires <YYYY-MM-DD|none>
  --status <candidate|validating|promoted|rejected|expired>

허용된 상태 전이:
  candidate → validating
  validating → promoted | rejected
  모든 상태 → expired

종료 코드:
  0  성공
  1  검증 위반 또는 허용되지 않은 전이
  2  대상 파일이나 디렉터리를 찾을 수 없습니다
  3  인자가 잘못되었습니다
USAGE
}

REQUIRED_KEYS=(id date status symptom evidence root_cause fix recurrence_risk
  harness_element proposed_harness_change preferred_enforcement trust
  regression_check owner expires)

# owner 는 비어 있어도 됩니다. 나머지는 값이 있어야 합니다.
OPTIONAL_VALUE_KEYS=" owner "

ENUM_STATUS="candidate validating promoted rejected expired"
ENUM_RISK="low medium high"
ENUM_ENFORCEMENT="test lint arch-rule hook script doc skill subagent instruction"
ENUM_TRUST="untrusted validated"

il_trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

il_unquote() {
  local s="$1"
  if [[ ${#s} -ge 2 && "${s:0:1}" == '"' && "${s: -1}" == '"' ]]; then
    s="${s:1:${#s}-2}"
  elif [[ ${#s} -ge 2 && "${s:0:1}" == "'" && "${s: -1}" == "'" ]]; then
    s="${s:1:${#s}-2}"
  fi
  printf '%s' "$s"
}

# il_parse_file <파일> — "키<TAB>값" 줄을 출력합니다.
# 값에 콜론이 있어도 첫 콜론 뒤 전체를 값으로 봅니다.
# 들여쓴 다음 줄들은 앞 키의 값에 이어 붙입니다(블록 스타일 지원).
il_parse_file() {
  local f="$1" key="" val="" line
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    case "$(il_trim "$line")" in
      ''|'#'*) continue ;;
    esac
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_-]*):(.*)$ ]]; then
      if [[ -n "$key" ]]; then
        printf '%s\t%s\n' "$key" "$(il_unquote "$(il_trim "$val")")"
      fi
      key="${BASH_REMATCH[1]}"
      val="${BASH_REMATCH[2]}"
    elif [[ -n "$key" ]]; then
      val="${val} $(il_trim "$line")"
    fi
  done < "$f"
  if [[ -n "$key" ]]; then
    printf '%s\t%s\n' "$key" "$(il_unquote "$(il_trim "$val")")"
  fi
}

# il_get <파일> <키> — 첫 번째로 나오는 키의 값을 출력합니다.
# awk 를 조기 종료시키지 않습니다. 조기 종료는 pipefail 과 만나 SIGPIPE(141) 를 만듭니다.
# 한 파일에서 키를 여러 개 읽을 때는 이것을 반복 호출하지 말고 il_load_file 을 쓰십시오.
# 이 함수는 호출 한 번에 서브셸과 awk 를 새로 띄우며, Windows 에서 프로세스 생성은 매우 비쌉니다.
il_get() {
  local f="$1" k="$2"
  il_parse_file "$f" | awk -v k="$k" '
    !found && index($0, k "\t") == 1 { value = substr($0, length(k) + 2); found = 1 }
    END { if (found) print value }
  '
}

# il_load_file <파일> — 파일을 **한 번만** 파싱해 IL_KEYS(등장 순서)와 IL_VALS(키→값)에 담습니다.
# 같은 파일에서 키를 15개 이상 읽는 validate/list 가 il_get 을 반복 호출하면
# 파일 하나당 20회 넘는 프로세스 생성이 일어나 항목이 쌓일수록 검증이 급격히 느려집니다.
declare -A IL_VALS
IL_KEYS=()
il_load_file() {
  local f="$1" k v
  IL_VALS=()
  IL_KEYS=()
  while IFS=$'\t' read -r k v; do
    [[ -n "$k" ]] || continue
    IL_KEYS+=("$k")
    [[ -n "${IL_VALS[$k]+x}" ]] || IL_VALS["$k"]="$v"
  done < <(il_parse_file "$f")
}

# il_val <키> — il_load_file 로 읽어 둔 값을 냅니다. 없으면 빈 문자열입니다.
il_val() { printf '%s' "${IL_VALS[$1]:-}"; }

il_enum_has() {
  local list="$1" value="$2" item
  for item in $list; do
    [[ "$item" == "$value" ]] && return 0
  done
  return 1
}

il_yaml_value() {
  local v="$1"
  if [[ -z "$v" ]]; then
    printf ''
  elif [[ "$v" == *:* || "$v" == \#* || "$v" == *$'\n'* ]]; then
    printf '"%s"' "${v//\"/\'}"
  else
    printf '%s' "$v"
  fi
}

ROOT="$(find_project_root "$PWD")"
cd "$ROOT"
load_config "$ROOT"
LOG_DIR="${ROOT}/${HARNESS_IMPROVEMENT_DIR}"

# ---------------------------------------------------------------------------
cmd_new() {
  local status="candidate" symptom="" evidence="" root_cause="" fix=""
  local recurrence_risk="" harness_element="" proposed="" enforcement=""
  local trust="untrusted" regression_check="" owner="" expires="none"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --symptom) _need_value "$@"; symptom="$2"; shift 2 ;;
      --evidence) _need_value "$@"; evidence="$2"; shift 2 ;;
      --root-cause) _need_value "$@"; root_cause="$2"; shift 2 ;;
      --fix) _need_value "$@"; fix="$2"; shift 2 ;;
      --recurrence-risk) _need_value "$@"; recurrence_risk="$2"; shift 2 ;;
      --harness-element) _need_value "$@"; harness_element="$2"; shift 2 ;;
      --proposed-harness-change) _need_value "$@"; proposed="$2"; shift 2 ;;
      --preferred-enforcement) _need_value "$@"; enforcement="$2"; shift 2 ;;
      --trust) _need_value "$@"; trust="$2"; shift 2 ;;
      --regression-check) _need_value "$@"; regression_check="$2"; shift 2 ;;
      --owner) _need_value "$@"; owner="$2"; shift 2 ;;
      --expires) _need_value "$@"; expires="$2"; shift 2 ;;
      --status) _need_value "$@"; status="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "new 가 모르는 옵션입니다: $1" 3 ;;
    esac
  done

  mkdir -p "$LOG_DIR"
  local today seq id file
  today="$(date +%F)"
  seq=1
  local f base num
  for f in "$LOG_DIR/${today}-"*.yaml; do
    [[ -e "$f" ]] || continue
    base="$(basename "$f")"
    num="${base#"${today}-"}"
    num="${num%%[!0-9]*}"
    [[ "$num" =~ ^[0-9]+$ ]] || continue
    [[ $((10#$num + 1)) -gt "$seq" ]] && seq=$((10#$num + 1))
  done
  id="$(printf '%s-%03d' "$today" "$seq")"
  file="${LOG_DIR}/${id}.yaml"
  [[ -e "$file" ]] && die "이미 존재하는 파일입니다: ${file}" 2

  {
    printf '# improvement log 후보입니다. improvement-log/schema.md 의 키 순서를 바꾸지 않습니다.\n'
    printf 'id: %s\n' "$id"
    printf 'date: %s\n' "$today"
    printf 'status: %s\n' "$(il_yaml_value "$status")"
    printf 'symptom: %s\n' "$(il_yaml_value "$symptom")"
    printf 'evidence: %s\n' "$(il_yaml_value "$evidence")"
    printf 'root_cause: %s\n' "$(il_yaml_value "$root_cause")"
    printf 'fix: %s\n' "$(il_yaml_value "$fix")"
    printf 'recurrence_risk: %s\n' "$(il_yaml_value "$recurrence_risk")"
    printf 'harness_element: %s\n' "$(il_yaml_value "$harness_element")"
    printf 'proposed_harness_change: %s\n' "$(il_yaml_value "$proposed")"
    printf 'preferred_enforcement: %s\n' "$(il_yaml_value "$enforcement")"
    printf 'trust: %s\n' "$(il_yaml_value "$trust")"
    printf 'regression_check: %s\n' "$(il_yaml_value "$regression_check")"
    printf 'owner: %s\n' "$(il_yaml_value "$owner")"
    printf 'expires: %s\n' "$(il_yaml_value "$expires")"
  } > "$file"

  printf '%s\n' "새 improvement 후보를 만들었습니다: ${HARNESS_IMPROVEMENT_DIR}/${id}.yaml"
  printf '%s\n' "빈 값을 채운 뒤 improvement-log.sh validate 로 검증하십시오."
  printf '%s\n' "$file"
}

# ---------------------------------------------------------------------------
cmd_list() {
  local filter=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --status) _need_value "$@"; filter="$2"; shift 2 ;;
      --status=*) filter="${1#*=}"; shift ;;
      -h|--help) usage; exit 0 ;;
      *) die "list 가 모르는 옵션입니다: $1" 3 ;;
    esac
  done

  if [[ ! -d "$LOG_DIR" ]]; then
    printf '%s\n' "${HARNESS_IMPROVEMENT_DIR}/ 가 아직 없습니다. improvement-log.sh new 로 첫 후보를 만드십시오."
    return 0
  fi

  local found=0 f id status risk symptom
  printf '%-16s %-11s %-16s %s\n' "id" "status" "recurrence_risk" "symptom"
  printf '%-16s %-11s %-16s %s\n' "----------------" "-----------" "----------------" "-------"
  for f in "$LOG_DIR"/*.yaml; do
    [[ -e "$f" ]] || continue
    [[ "$(basename "$f")" == _* ]] && continue
    il_load_file "$f"
    id="$(il_val id)"
    status="$(il_val status)"
    risk="$(il_val recurrence_risk)"
    symptom="$(il_val symptom)"
    [[ -n "$filter" && "$status" != "$filter" ]] && continue
    found=$((found + 1))
    printf '%-16s %-11s %-16s %s\n' "${id:--}" "${status:--}" "${risk:--}" "${symptom:0:60}"
  done
  if [[ "$found" -eq 0 ]]; then
    printf '%s\n' "조건에 맞는 항목이 없습니다."
  fi
}

# ---------------------------------------------------------------------------
validate_one() {
  local f="$1" rel violations=0
  rel="${f#"$ROOT"/}"

  # 파일은 한 번만 파싱합니다. 아래 검사는 전부 IL_KEYS / IL_VALS 를 씁니다.
  il_load_file "$f"
  local keys=("${IL_KEYS[@]+"${IL_KEYS[@]}"}")

  # 1. 필수 키 존재와 순서
  local i expected actual
  for ((i = 0; i < ${#REQUIRED_KEYS[@]}; i++)); do
    expected="${REQUIRED_KEYS[$i]}"
    actual="${keys[$i]:-}"
    if [[ -z "$actual" ]]; then
      printf '%s:%s 필수 키가 없습니다.\n' "$rel" "$expected"
      violations=$((violations + 1))
    elif [[ "$actual" != "$expected" ]]; then
      printf '%s:%s 키 순서가 improvement-log/schema.md 와 다릅니다. %s번째는 %s 여야 합니다.\n' "$rel" "$actual" "$((i + 1))" "$expected"
      violations=$((violations + 1))
    fi
  done
  for ((i = ${#REQUIRED_KEYS[@]}; i < ${#keys[@]}; i++)); do
    printf '%s:%s improvement-log/schema.md 에 없는 키입니다.\n' "$rel" "${keys[$i]}"
    violations=$((violations + 1))
  done

  # 2. 값 존재
  local key val
  for key in "${REQUIRED_KEYS[@]}"; do
    val="$(il_val "$key")"
    if [[ -z "$val" && "$OPTIONAL_VALUE_KEYS" != *" ${key} "* ]]; then
      printf '%s:%s 값이 비어 있습니다.\n' "$rel" "$key"
      violations=$((violations + 1))
    fi
  done

  # 3. 형식과 enum
  val="$(il_val id)"
  if [[ -n "$val" && ! "$val" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{3}$ ]]; then
    printf '%s:id 형식이 YYYY-MM-DD-NNN 이 아닙니다: %s\n' "$rel" "$val"; violations=$((violations + 1))
  fi
  val="$(il_val date)"
  if [[ -n "$val" && ! "$val" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    printf '%s:date 형식이 YYYY-MM-DD 가 아닙니다: %s\n' "$rel" "$val"; violations=$((violations + 1))
  fi
  val="$(il_val status)"
  if [[ -n "$val" ]] && ! il_enum_has "$ENUM_STATUS" "$val"; then
    printf '%s:status 값이 허용 목록에 없습니다: %s\n' "$rel" "$val"; violations=$((violations + 1))
  fi
  val="$(il_val recurrence_risk)"
  if [[ -n "$val" ]] && ! il_enum_has "$ENUM_RISK" "$val"; then
    printf '%s:recurrence_risk 값이 허용 목록에 없습니다: %s\n' "$rel" "$val"; violations=$((violations + 1))
  fi
  val="$(il_val preferred_enforcement)"
  if [[ -n "$val" ]] && ! il_enum_has "$ENUM_ENFORCEMENT" "$val"; then
    printf '%s:preferred_enforcement 값이 허용 목록에 없습니다: %s\n' "$rel" "$val"; violations=$((violations + 1))
  fi
  val="$(il_val trust)"
  if [[ -n "$val" ]] && ! il_enum_has "$ENUM_TRUST" "$val"; then
    printf '%s:trust 값이 허용 목록에 없습니다: %s\n' "$rel" "$val"; violations=$((violations + 1))
  fi
  val="$(il_val harness_element)"
  if [[ -n "$val" && ! "$val" =~ ^HE-([1-9]|1[0-5])$ ]]; then
    printf '%s:harness_element 가 HE-1 ~ HE-15 가 아닙니다: %s\n' "$rel" "$val"; violations=$((violations + 1))
  fi
  val="$(il_val expires)"
  if [[ -n "$val" && "$val" != "none" && ! "$val" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    printf '%s:expires 는 YYYY-MM-DD 또는 none 이어야 합니다: %s\n' "$rel" "$val"; violations=$((violations + 1))
  fi

  return "$((violations > 0 ? 1 : 0))"
}

cmd_validate() {
  local files=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help) usage; exit 0 ;;
      *) files+=("$1"); shift ;;
    esac
  done

  if [[ ${#files[@]} -eq 0 ]]; then
    [[ -d "$LOG_DIR" ]] || die "${HARNESS_IMPROVEMENT_DIR}/ 가 없습니다. 검증할 파일이 없습니다." 2
    local f
    for f in "$LOG_DIR"/*.yaml; do
      [[ -e "$f" ]] || continue
      [[ "$(basename "$f")" == _* ]] && continue
      files+=("$f")
    done
  fi
  [[ ${#files[@]} -gt 0 ]] || { printf '%s\n' "검증할 파일이 없습니다."; return 0; }

  local bad=0 file
  for file in "${files[@]}"; do
    [[ -f "$file" ]] || { printf '%s: 파일이 없습니다.\n' "$file"; bad=$((bad + 1)); continue; }
    if ! validate_one "$file"; then
      bad=$((bad + 1))
    fi
  done

  if [[ "$bad" -gt 0 ]]; then
    printf '%s\n' "검증 실패: ${bad}개 파일에 위반이 있습니다."
    return 1
  fi
  printf '%s\n' "검증 통과: ${#files[@]}개 파일이 improvement-log/schema.md 를 만족합니다."
  return 0
}

# ---------------------------------------------------------------------------
cmd_set_status() {
  [[ $# -ge 2 ]] || die "사용법: improvement-log.sh set-status <id> <status>" 3
  local id="$1" new_status="$2"
  il_enum_has "$ENUM_STATUS" "$new_status" || die "알 수 없는 status 입니다: ${new_status} (허용: ${ENUM_STATUS})" 3

  local file="" f
  for f in "$LOG_DIR/${id}.yaml" "$LOG_DIR/${id}."*.yaml; do
    [[ -f "$f" ]] || continue
    file="$f"; break
  done
  [[ -n "$file" ]] || die "id 에 해당하는 파일을 찾지 못했습니다: ${id}" 2

  local current
  current="$(il_get "$file" status)"
  [[ -n "$current" ]] || die "${file}: 현재 status 를 읽지 못했습니다." 1

  local allowed=""
  case "$current" in
    candidate) allowed="validating expired" ;;
    validating) allowed="promoted rejected expired" ;;
    promoted) allowed="expired" ;;
    rejected) allowed="expired" ;;
    expired) allowed="" ;;
  esac

  if ! il_enum_has "$allowed" "$new_status"; then
    log_error "허용되지 않은 상태 전이입니다: ${current} → ${new_status}"
    log_error "허용된 전이: candidate → validating, validating → promoted|rejected, 모든 상태 → expired"
    [[ -n "$allowed" ]] && log_error "${current} 에서 갈 수 있는 상태: ${allowed}" || log_error "${current} 는 최종 상태입니다."
    exit 1
  fi

  local tmp
  tmp="$(mktemp "${file}.XXXXXX")"
  awk -v new="$new_status" '
    !done && /^status:/ { print "status: " new; done = 1; next }
    { print }
  ' "$file" > "$tmp"
  # mv 로 갈아끼우면 mktemp 의 0600 이 원본의 0644 를 대체합니다. 공유 체크아웃이나
  # 다른 uid 로 도는 CI 에서는 그 뒤의 validate·list 가 파일을 읽지 못하고,
  # 필수 단계 log-schema 가 상태 전이 한 번으로 조용히 깨집니다.
  # 내용만 덮어써 원본의 모드와 소유권을 유지합니다.
  cat "$tmp" > "$file"
  rm -f "$tmp"
  printf '%s\n' "${id}: ${current} → ${new_status}"
}

# ---------------------------------------------------------------------------
[[ $# -ge 1 ]] || { usage; exit 3; }
COMMAND="$1"; shift
case "$COMMAND" in
  new) cmd_new "$@" ;;
  list) cmd_list "$@" ;;
  validate) cmd_validate "$@" ;;
  set-status) cmd_set_status "$@" ;;
  -h|--help|help) usage ;;
  *) log_error "알 수 없는 명령입니다: ${COMMAND}"; usage; exit 3 ;;
esac
