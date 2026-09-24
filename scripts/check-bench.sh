#!/usr/bin/env bash
# check-bench.sh — AD-2 후보 2026-09-17-004: `scripts/smoke.sh --bench` 가 남긴
# `infra/docker/out/smoke-bench.json` 의 p95 를 `harness.config` 의
# `HARNESS_BENCH_P95_MAX_MS` 임계값과 비교해 게이트합니다. 이 값이 아직 verify 단계에
# 걸리지 않아 성능 회귀가 조용히 통과한 사고(2026-09-17, Run 생성 경로 N+1, 실측
# p95 1613 ms)가 있었습니다.
#
# AD-2 후보 2026-09-19-002: 신선도 판정을 벽시계 현재 시각이 아니라 "같은 verify 실행에서
# 나온 측정인가" 로 바꿨습니다. 같은 실행 안에서 smoke 가 벤치를 기록했는데 프로세스가
# 느려져 판정이 47분 뒤에 돌아, 기준 안인 측정(p95 62.2 ms)이 "측정이 오래됨" 으로 거짓
# 실패한 사고가 있었습니다. 기준 시각을 `.harness/logs/smoke.log`(verify 의 smoke 단계가
# 끝날 때 쓰는 로그)의 수정 시각으로 삼으면, 실행이 느려질 때 벤치의 measured_at 과 smoke
# 로그의 수정 시각이 함께 밀리므로 거짓 실패가 사라지고, 직전 실행의 오래된 벤치 파일은
# smoke 로그가 그보다 나중에 갱신되어 있어 여전히 걸립니다. smoke 로그가 없으면(깨끗한
# 체크아웃, check-bench.sh 단독 실행) 비교할 기준이 없으므로 기존 벽시계 규칙으로
# 폴백합니다.
#
# 임계값은 `harness.config`(보호 파일, EI-2 — 사람이 소유)가 정본입니다. 이 스크립트에
# 기본값을 넣지 않습니다 — 변수가 없으면 실패로 알립니다.
#
# AD-2 후보 2026-09-22-002: p95 가 기준을 넘으면 같은 실행 안에서 한 번 더 측정하고,
# 두 측정이 모두 기준을 넘을 때만 실패시킵니다. 2026-09-23 에 문서만 바꾼 PR 의 CI 가
# p95 165.6 ms 로 떨어졌는데(기준 150) 같은 커밋의 다른 두 실행은 65~79 ms 였고, 실패한
# job 을 재실행하니 65.9 ms 로 통과했습니다 — 공유 러너의 지연 꼬리가 기준값 자체가
# 아니라 판정의 잡음이었습니다. 재측정 명령은 기본 `scripts/smoke.sh --bench` 이고
# `HARNESS_BENCH_REMEASURE_CMD` 로 덮어쓸 수 있습니다(테스트가 도커 없이 검증하기
# 위함). 재측정이 실패하거나 결과 파일을 갱신하지 못하면 잡음을 이유로 게이트를 열지
# 않고 그대로 실패시킵니다.
#
# 사용:
#   scripts/check-bench.sh                                              # 저장소 기본 경로
#   scripts/check-bench.sh --bench <경로> --config <경로> --smoke-log <경로>  # 테스트용 경로 지정
#
# 종료 코드:
#   0 — p95 가 기준 이하이고 같은 실행에서 나온 측정임(또는 smoke 로그가 없어 벽시계
#       30분 폴백을 만족함). 1차 측정이 기준을 넘었어도 재측정이 기준 이하면 0.
#   1 — 기준 초과, 측정이 이전 실행 것이거나(벽시계 폴백이면 30분보다 오래됨), 결과
#       파일이 없거나 깨짐, harness.config 에 임계값이 없거나 숫자가 아님, 또는
#       재측정까지 두 번 모두 기준을 넘거나 재측정 자체가 실패/미갱신인 경우.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

BENCH_PATH="${ROOT}/infra/docker/out/smoke-bench.json"
CONFIG_PATH="${ROOT}/harness.config"
SMOKE_LOG_PATH="${ROOT}/.harness/logs/smoke.log"

while [ $# -gt 0 ]; do
  case "$1" in
    --bench)
      BENCH_PATH="$2"
      shift 2
      ;;
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --smoke-log)
      SMOKE_LOG_PATH="$2"
      shift 2
      ;;
    *)
      echo "check-bench: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

# 신선도 상한(초, 벽시계 폴백용). 재측정 없이 오래된 결과로 게이트를 통과하는 것을
# 막습니다 — 30분은 로컬에서 smoke --bench 를 돌리고 곧바로 verify 를 실행하는 흐름을
# 넉넉히 덮으면서, 어제 결과가 오늘 커밋을 대변한다고 속이지는 못하게 고른 값입니다.
# smoke.log 가 있으면 이 값 대신 SAME_RUN_MAX_LAG_SECONDS 를 씁니다.
FRESHNESS_MAX_SECONDS=1800

# 벤치 결과가 "같은 실행" 것으로 인정되는 최대 지연(초) — smoke.log 수정 시각보다
# 이만큼 이상 이전이면 다른(더 이전) 실행의 결과로 간주해 실패시킵니다. 600 은 smoke
# 단계 종료부터 bench 판정 시작까지 정상적으로 걸리는 시간을 넉넉히 덮으면서, 2026-
# 09-19-002 사고의 지연(2820초)은 여전히 걸러내는 값입니다.
SAME_RUN_MAX_LAG_SECONDS=600

if [ ! -f "$BENCH_PATH" ]; then
  echo "check-bench: bench 결과 파일이 없습니다: ${BENCH_PATH}" >&2
  exit 1
fi

# 호스트에서 JSON 을 다룰 파이썬을 고릅니다(scripts/smoke.sh 와 동일한 방식) — 이름만
# 보고 고르지 않고 실제로 동작하는지 확인합니다. Windows 에서 "python3" 는 Microsoft
# Store 스텁으로 존재는 하지만(`command -v` 성공) 실행하면 조용히 0 이 아닌 코드로
# 끝나는 경우가 있습니다(실측).
HOST_PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import sys" >/dev/null 2>&1; then
    HOST_PYTHON="$candidate"
    break
  fi
done
if [ -z "$HOST_PYTHON" ]; then
  echo "check-bench: no working python interpreter found on host (tried python3, python)" >&2
  exit 1
fi

# bench 결과 파일에서 p95_ms/measured_at 을 뽑아 두 줄로 출력하는 함수 — 1차 측정과
# 재측정(2026-09-22-002) 모두 같은 파싱·검증을 거쳐야 하므로 공유합니다.
parse_bench() {
  local path="$1"
  "$HOST_PYTHON" - "$path" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except (OSError, json.JSONDecodeError) as exc:
    print(f"check-bench: bench 결과 파일을 읽을 수 없습니다({exc})", file=sys.stderr)
    sys.exit(1)

if not isinstance(data, dict) or "p95_ms" not in data:
    print("check-bench: bench 결과에 p95_ms 키가 없습니다", file=sys.stderr)
    sys.exit(1)

if "measured_at" not in data:
    print("check-bench: bench 결과에 measured_at 키가 없습니다", file=sys.stderr)
    sys.exit(1)

print(data["p95_ms"])
print(data["measured_at"])
PY
}

if ! PARSED="$(parse_bench "$BENCH_PATH")"; then
  exit 1
fi

P95_MS="$(printf '%s\n' "$PARSED" | sed -n '1p')"
MEASURED_AT="$(printf '%s\n' "$PARSED" | sed -n '2p')"

if [ ! -f "$CONFIG_PATH" ]; then
  echo "check-bench: harness.config 를 찾을 수 없습니다: ${CONFIG_PATH}" >&2
  exit 1
fi

# harness.config 는 bash 변수 대입 파일입니다 — 서브셸에서 source 해 변수 하나만
# 뽑아내고, 그 안의 다른 변수(HARNESS_STEPS 등)가 이 스크립트의 상태를 건드리지
# 않게 합니다. 기본값을 여기 두지 않습니다 — 임계값은 harness.config 가 소유합니다.
THRESHOLD="$(
  set +u
  # shellcheck disable=SC1090
  source "$CONFIG_PATH"
  printf '%s' "${HARNESS_BENCH_P95_MAX_MS:-}"
)"

if [ -z "$THRESHOLD" ]; then
  echo "check-bench: harness.config 에 HARNESS_BENCH_P95_MAX_MS 가 없습니다" >&2
  exit 1
fi

if ! [[ "$THRESHOLD" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
  echo "check-bench: HARNESS_BENCH_P95_MAX_MS 값이 숫자가 아닙니다: ${THRESHOLD}" >&2
  exit 1
fi

MEASURED_EPOCH="$(date -u -d "$MEASURED_AT" +%s 2>/dev/null || true)"
if [ -z "$MEASURED_EPOCH" ]; then
  echo "check-bench: measured_at 형식을 해석할 수 없습니다: ${MEASURED_AT}" >&2
  exit 1
fi

# 마지막 줄에 실측값·기준과 함께 사유(통과/초과/신선도)까지 담습니다 — verify.sh 의
# summary 는 각 단계 로그의 마지막 줄만 남기므로, 그 한 줄만 보고도 경우를 구분할
# 수 있어야 합니다(리뷰 지적, 2026-09-17 N+1 회귀를 놓친 사고와 같은 결).
if [ -f "$SMOKE_LOG_PATH" ]; then
  # 같은 verify 실행에서 나온 측정인지를 벽시계 대신 확인합니다(2026-09-19-002).
  SMOKE_LOG_EPOCH="$(date -u -r "$SMOKE_LOG_PATH" +%s)"
  LAG_SECONDS=$((SMOKE_LOG_EPOCH - MEASURED_EPOCH))
  if [ "$LAG_SECONDS" -ge "$SAME_RUN_MAX_LAG_SECONDS" ]; then
    echo "check-bench: bench 결과가 이전 실행 것입니다 (measured_at=${MEASURED_AT}, smoke_log=${SMOKE_LOG_PATH}, lag=${LAG_SECONDS}s >= ${SAME_RUN_MAX_LAG_SECONDS}s)" >&2
    printf 'p95=%s ms, 기준=%s ms — 측정이 이전 실행 것(bench 가 smoke 로그보다 %ss 이전)\n' \
      "$P95_MS" "$THRESHOLD" "$LAG_SECONDS"
    exit 1
  fi
else
  # smoke.log 가 없으면(깨끗한 체크아웃, check-bench.sh 단독 실행) 같은 실행인지 비교할
  # 기준이 없으므로 벽시계 현재 시각과 비교하는 기존 규칙으로 폴백합니다.
  NOW_EPOCH="$(date -u +%s)"
  AGE_SECONDS=$((NOW_EPOCH - MEASURED_EPOCH))
  if [ "$AGE_SECONDS" -gt "$FRESHNESS_MAX_SECONDS" ]; then
    echo "check-bench: bench 결과가 오래되었습니다 (measured_at=${MEASURED_AT}, age=${AGE_SECONDS}s > ${FRESHNESS_MAX_SECONDS}s)" >&2
    printf 'p95=%s ms, 기준=%s ms — 측정이 오래됨(age=%ss > %ss)\n' \
      "$P95_MS" "$THRESHOLD" "$AGE_SECONDS" "$FRESHNESS_MAX_SECONDS"
    exit 1
  fi
fi

if awk -v p95="$P95_MS" -v thr="$THRESHOLD" 'BEGIN { exit (p95 + 0 <= thr + 0) ? 0 : 1 }'; then
  printf 'p95=%s ms, 기준=%s ms — 통과\n' "$P95_MS" "$THRESHOLD"
  exit 0
fi

# 1차 초과 — 같은 실행 안에서 한 번 더 측정합니다(2026-09-22-002). 기준값과 측정
# 부하는 바꾸지 않고, 잡음으로 인한 단발성 초과만 걸러냅니다.
REMEASURE_CMD="${HARNESS_BENCH_REMEASURE_CMD:-${SCRIPT_DIR}/smoke.sh --bench}"
ORIG_P95_MS="$P95_MS"
ORIG_MEASURED_AT="$MEASURED_AT"

if ! bash -c "$REMEASURE_CMD"; then
  echo "check-bench: 재측정 명령이 실패했습니다: ${REMEASURE_CMD}" >&2
  printf 'p95=%s ms → 재측정 실패, 기준=%s ms — 초과(재측정 명령 실패)\n' "$ORIG_P95_MS" "$THRESHOLD"
  exit 1
fi

if [ ! -f "$BENCH_PATH" ]; then
  echo "check-bench: 재측정 후 bench 결과 파일이 없습니다: ${BENCH_PATH}" >&2
  printf 'p95=%s ms → 재측정 실패, 기준=%s ms — 초과(재측정 결과 없음)\n' "$ORIG_P95_MS" "$THRESHOLD"
  exit 1
fi

if ! PARSED2="$(parse_bench "$BENCH_PATH")"; then
  printf 'p95=%s ms → 재측정 실패, 기준=%s ms — 초과(재측정 결과 파싱 실패)\n' "$ORIG_P95_MS" "$THRESHOLD"
  exit 1
fi

P95_MS_2="$(printf '%s\n' "$PARSED2" | sed -n '1p')"
MEASURED_AT_2="$(printf '%s\n' "$PARSED2" | sed -n '2p')"

# "갱신되었는가" 는 measured_at 문자열만으로 판단하지 않습니다 — 초 단위 타임스탬프는
# 1차·2차 측정이 같은 초 안에 끝나면 텍스트가 우연히 같아질 수 있습니다(실측). p95 값과
# measured_at 이 **둘 다** 원래 측정과 같을 때만 "갱신되지 않음" 으로 판단합니다.
if [ "$MEASURED_AT_2" = "$ORIG_MEASURED_AT" ] && [ "$P95_MS_2" = "$ORIG_P95_MS" ]; then
  echo "check-bench: 재측정 후에도 결과 파일이 갱신되지 않았습니다 (measured_at=${MEASURED_AT_2}, p95_ms=${P95_MS_2})" >&2
  printf 'p95=%s ms → 재측정 갱신 안 됨, 기준=%s ms — 초과(재측정 결과 미갱신)\n' "$ORIG_P95_MS" "$THRESHOLD"
  exit 1
fi

if awk -v p95="$P95_MS_2" -v thr="$THRESHOLD" 'BEGIN { exit (p95 + 0 <= thr + 0) ? 0 : 1 }'; then
  printf 'p95=%s ms → 재측정 %s ms, 기준=%s ms — 통과(1차 초과, 2차 이내)\n' "$ORIG_P95_MS" "$P95_MS_2" "$THRESHOLD"
  exit 0
fi

printf 'p95=%s ms → 재측정 %s ms, 기준=%s ms — 초과(2회 연속)\n' "$ORIG_P95_MS" "$P95_MS_2" "$THRESHOLD"
exit 1
