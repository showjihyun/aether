#!/usr/bin/env bash
# check-bench.sh — AD-2 후보 2026-09-17-004: `scripts/smoke.sh --bench` 가 남긴
# `infra/docker/out/smoke-bench.json` 의 p95 를 `harness.config` 의
# `HARNESS_BENCH_P95_MAX_MS` 임계값과 비교해 게이트합니다. 이 값이 아직 verify 단계에
# 걸리지 않아 성능 회귀가 조용히 통과한 사고(2026-09-17, Run 생성 경로 N+1, 실측
# p95 1613 ms)가 있었습니다.
#
# 임계값은 `harness.config`(보호 파일, EI-2 — 사람이 소유)가 정본입니다. 이 스크립트에
# 기본값을 넣지 않습니다 — 변수가 없으면 실패로 알립니다.
#
# 사용:
#   scripts/check-bench.sh                                  # 저장소 기본 경로
#   scripts/check-bench.sh --bench <경로> --config <경로>    # 테스트용 경로 지정
#
# 종료 코드:
#   0 — p95 가 기준 이하이고 결과가 신선함(30분 이내).
#   1 — 기준 초과, 결과가 오래됨, 결과 파일이 없거나 깨짐, 또는 harness.config 에
#       임계값이 없거나 숫자가 아님.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

BENCH_PATH="${ROOT}/infra/docker/out/smoke-bench.json"
CONFIG_PATH="${ROOT}/harness.config"

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
    *)
      echo "check-bench: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

# 신선도 상한(초). 재측정 없이 오래된 결과로 게이트를 통과하는 것을 막습니다 — 30분은
# 로컬에서 smoke --bench 를 돌리고 곧바로 verify 를 실행하는 흐름을 넉넉히 덮으면서,
# 어제 결과가 오늘 커밋을 대변한다고 속이지는 못하게 고른 값입니다.
FRESHNESS_MAX_SECONDS=1800

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

if ! PARSED="$("$HOST_PYTHON" - "$BENCH_PATH" <<'PY'
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
)"; then
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
NOW_EPOCH="$(date -u +%s)"
AGE_SECONDS=$((NOW_EPOCH - MEASURED_EPOCH))

# 마지막 줄에 실측값·기준과 함께 사유(통과/초과/신선도)까지 담습니다 — verify.sh 의
# summary 는 각 단계 로그의 마지막 줄만 남기므로, 그 한 줄만 보고도 세 경우를 구분할
# 수 있어야 합니다(리뷰 지적, 2026-09-17 N+1 회귀를 놓친 사고와 같은 결).
if [ "$AGE_SECONDS" -gt "$FRESHNESS_MAX_SECONDS" ]; then
  echo "check-bench: bench 결과가 오래되었습니다 (measured_at=${MEASURED_AT}, age=${AGE_SECONDS}s > ${FRESHNESS_MAX_SECONDS}s)" >&2
  printf 'p95=%s ms, 기준=%s ms — 측정이 오래됨(age=%ss > %ss)\n' \
    "$P95_MS" "$THRESHOLD" "$AGE_SECONDS" "$FRESHNESS_MAX_SECONDS"
  exit 1
fi

if awk -v p95="$P95_MS" -v thr="$THRESHOLD" 'BEGIN { exit (p95 + 0 <= thr + 0) ? 0 : 1 }'; then
  printf 'p95=%s ms, 기준=%s ms — 통과\n' "$P95_MS" "$THRESHOLD"
  exit 0
fi

printf 'p95=%s ms, 기준=%s ms — 초과\n' "$P95_MS" "$THRESHOLD"
exit 1
