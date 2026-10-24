#!/usr/bin/env bash
# e2e.sh — spec 0006 D-6 (MVP-3): `e2e` 단계의 진입점. 격리 프로젝트(`-p aether-e2e`)에서
#   R-9  모델 볼륨이 비어 있으면 worker 가 **받는 방법을 적은 오류로** 멈춘다(조용히 받지 않는다).
#   R-8  네트워크를 끊은 compose 에서 Run 하나가 **진짜 openai-호환 서버**(소형 모델)로 succeeded.
#   C-5  "끊었다" 는 주장이 아니라 증명: 같은 네트워크의 worker 에서 외부 접속이 실패한다.
#   R-10 (MVP-4) 같은 스택에서 Knowledge 적재(실제 임베딩 모델, D-19)가 **청크를 쌓고**
#        -> MCP·knowledge 바인딩 Agent + 도구 허용 -> Workflow(START->AGENT->END) Run 이
#        succeeded. 청크 수는 psql 실측입니다 - 적재는 아무것도 쌓지 않아도 succeeded 입니다.
#   R-5  (MVP-4, D-20) 같은 스택의 web 이 다섯 경로와 `/` 에서 200 이고, 그중 넷이 이 실행이
#        만든 값(Run id·Agent·Knowledge Set·Workflow 이름)을 보인다(scripts/web_routes_check.py).
#   R-8  (spec 0007, P5-9) 같은 web 의 서버 액션 createWorkflowAction 을 지나 Workflow 하나를 만들고
#        그 이름이 /workflows 에 보인다(scripts/web_write_check.py).
# 단언하지 않는 것(spec 2.11): MCP 도구 호출이 실제로 일어났는지(소형 모델은 비결정적 -
# 그 경로는 smoke 가 fake 로 소유), 검색량, 답변 품질. 모델 품질은 판정하지 않습니다(D-12) -
# `succeeded` 와 경로만 봅니다. 응답 본문과 발급한 api 키는 어디에도 출력하지 않습니다.
#
# 순서: (1) 빈 볼륨으로 up -> 멈춤 확인 (2) `scripts/fetch-model.sh` 로 채팅·임베딩 모델 적재(온라인,
# 이 단계만 네트워크 필요) (3) 네트워크를 `internal: true` 로 바꿔 다시 up -> Run -> succeeded.
# 이미지 빌드·pull 도 (1) 에서 일어나므로 처음 실행은 온라인이어야 합니다.
#
# 사용:   scripts/e2e.sh        E2E_NO_BUILD=1 이면 compose.ci.yaml 이미지를 씁니다(CI 캐시 경로).
# 격리:   프로젝트 이름은 `aether-e2e*` 만 받고, `down -v` 는 `-p` 와 함께만 나갑니다.
#         (이름이 비면 compose 가 개발 프로젝트의 볼륨을 지웁니다 - improvement-log 2026-09-22-003)
# 비밀값: 임시 `.env`(랜덤)를 쓰고 지웁니다. 어떤 출력에도 남기지 않습니다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
cd "$ROOT"
export MSYS_NO_PATHCONV=1

PROJECT="${E2E_PROJECT-aether-e2e}"
TEST_MODEL="qwen2.5:0.5b"
# D-19: 적재는 임베딩 모델로 갑니다. 이 태그는 infra/docker/.env.example 의
# AETHER_EMBED_MODEL_ID 기본값과 같아야 합니다(다르면 worker 가 볼륨에 없는 모델을 찾습니다).
EMBED_MODEL="nomic-embed-text"

if ! [[ "$PROJECT" =~ ^aether-e2e[a-z0-9_-]*$ ]]; then
  echo "e2e: invalid E2E_PROJECT '${PROJECT}' - must match aether-e2e* (down -v runs against it)" >&2
  exit 2
fi

HOST_PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import sys" >/dev/null 2>&1; then
    HOST_PYTHON="$candidate"
    break
  fi
done
CLIENT_SCRIPT="scripts/smoke_client.py"

TMP_ENV="$(mktemp ./.env.e2e.XXXXXX)"
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    AETHER_MODEL_ADAPTER=*) printf 'AETHER_MODEL_ADAPTER=openai_compatible\n' ;;
    AETHER_MODEL_BASE_URL=*) printf 'AETHER_MODEL_BASE_URL=http://llm:11434/v1\n' ;;
    AETHER_MODEL_ID=*) printf 'AETHER_MODEL_ID=%s\n' "$TEST_MODEL" ;;
    AETHER_MODEL_API_KEY=*) printf 'AETHER_MODEL_API_KEY=\n' ;;
    *'=<generate>') printf '%s=%s\n' "${line%%=*}" "$(openssl rand -hex 24)" ;;
    *) printf '%s\n' "$line" ;;
  esac
done <infra/docker/.env.example >"$TMP_ENV"

FILES=(-f infra/docker/compose.yaml -f infra/docker/compose.llm.yaml -f infra/docker/compose.e2e.yaml)
BUILD_FLAG="--build"
if [ "${E2E_NO_BUILD:-}" = "1" ]; then
  FILES+=(-f infra/docker/compose.ci.yaml)
  BUILD_FLAG="--no-build"
fi
ONLINE=(docker compose -p "$PROJECT" --env-file "$TMP_ENV" "${FILES[@]}")
OFFLINE=(docker compose -p "$PROJECT" --env-file "$TMP_ENV" "${FILES[@]}" -f infra/docker/compose.offline.yaml)
ACTIVE=("${ONLINE[@]}")
STARTED=0

fail() { echo "e2e: FAIL $*" >&2; exit 1; }

cleanup() {
  local exit_code=$?
  trap - EXIT
  if [ "$exit_code" -ne 0 ] && [ "$STARTED" -eq 1 ]; then
    echo "e2e: failing - recent logs (worker, llm, migrate, web):" >&2
    "${ACTIVE[@]}" logs --no-color --tail 60 worker llm migrate web >&2 || true
  fi
  "${ONLINE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f "$TMP_ENV"
  exit "$exit_code"
}
trap cleanup EXIT

SERVICES=(postgres redis migrate llm worker)

# 지난 실행의 잔여를 치웁니다 - 볼륨이 확실히 비어 있어야 R-9 가 의미가 있습니다.
"${ONLINE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true

# --- (1) R-9: 빈 볼륨 ------------------------------------------------------------------
echo "e2e: [R-9] empty model volume -> worker must stop with a clear error (project=${PROJECT})..." >&2
STARTED=1
# 2단계(오프라인)는 --no-build 입니다 - 이미지는 여기서(온라인일 때) 모두 만들어 둡니다.
# 1단계가 올리는 서비스에 api 는 없으므로 따로 빌드합니다.
if [ "$BUILD_FLAG" = "--build" ]; then
  "${ONLINE[@]}" build api >/dev/null || fail "build: could not build the api image"
fi
# web 은 E2E_NO_BUILD=1 일 때도 빌드합니다 - compose.ci.yaml 이 api·migrate·worker 만 핀하고,
# 3단계는 --no-build 라서 이미지가 오프라인이 되기 전(여기)에 있어야 합니다.
"${ONLINE[@]}" build web >/dev/null || fail "build: could not build the web image"
if "${ONLINE[@]}" up -d --wait "$BUILD_FLAG" "${SERVICES[@]}" >/dev/null 2>&1; then
  fail "R-9: worker started although the model volume is empty (the failure must be explicit, not silent)"
fi
WORKER_LOGS="$("${ONLINE[@]}" logs --no-color worker 2>&1 || true)"
case "$WORKER_LOGS" in
  *scripts/fetch-model.sh*) ;;
  *) fail "R-9: worker stopped but its message does not tell how to load the model (scripts/fetch-model.sh)" ;;
esac
if "${ONLINE[@]}" exec -T llm ollama list 2>/dev/null | tr -d '\r' | awk -v m="$TEST_MODEL" 'NR>1 && $1==m {f=1} END {exit !f}'; then
  fail "R-9: the model appeared in the volume without fetch-model.sh - the boot path downloaded it"
fi
echo "e2e: [R-9] ok - stopped with the fetch hint, nothing downloaded at boot" >&2

# --- (2) 적재 (온라인) --------------------------------------------------------------------
"${SCRIPT_DIR}/fetch-model.sh" --test-model --project "$PROJECT" --env-file "$TMP_ENV" >&2 \
  || fail "fetch: could not load ${TEST_MODEL} (this phase needs network once)"
"${SCRIPT_DIR}/fetch-model.sh" --model "$EMBED_MODEL" --project "$PROJECT" --env-file "$TMP_ENV" >&2 \
  || fail "fetch-embed: could not load the embedding model ${EMBED_MODEL} (Knowledge ingestion needs it, D-19)"

# --- (3) R-8: 끊긴 네트워크 ----------------------------------------------------------------
"${ONLINE[@]}" down --remove-orphans >/dev/null 2>&1 || true   # 볼륨은 남깁니다(-v 없음)
ACTIVE=("${OFFLINE[@]}")
echo "e2e: [R-8] internal-only network, loaded volume -> Run must succeed..." >&2
"${OFFLINE[@]}" up -d --wait --no-build "${SERVICES[@]}" api >&2 \
  || fail "R-8: the stack did not come up on the offline network with the model loaded"

# C-5: 끊겼다는 증명. worker 가 외부(IP, 이름)에 닿으면 이 e2e 는 아무것도 증명하지 못합니다.
PROBE_CODE='
import sys, urllib.request
for url in ("http://1.1.1.1", "http://example.com"):
    try:
        urllib.request.urlopen(url, timeout=3)
    except Exception:
        continue
    sys.exit(7)
sys.exit(0)
'
set +e
"${OFFLINE[@]}" exec -T worker python -c "$PROBE_CODE" e2e-offline-probe
PROBE=$?
set -e
[ "$PROBE" -eq 0 ] || fail "C-5: the worker reached the outside world or the probe failed (exit ${PROBE}) - the network is not proven cut"
echo "e2e: [C-5] ok - the worker cannot reach the outside world" >&2

E2E_API_KEY="$("${OFFLINE[@]}" exec -T api aether-api keys create --label e2e 2>/dev/null | tr -d '\r\n')"
[ -n "$E2E_API_KEY" ] || fail "R-8: could not issue an API key"
export E2E_API_KEY
set +e
SCENARIO_JSON="$("${OFFLINE[@]}" exec -T -e SMOKE_API_KEY="$E2E_API_KEY" api python - scenario <"$CLIENT_SCRIPT")"
SCENARIO_RC=$?
set -e
if [ "$SCENARIO_RC" -ne 0 ] || ! printf '%s' "$SCENARIO_JSON" | grep -Eq '"status": ?"succeeded"'; then
  fail "R-8: the Run did not reach succeeded on the local model (scenario exit ${SCENARIO_RC})"
fi
# succeeded 만으로는 어느 어댑터가 답했는지 모릅니다. 진짜 openai-호환 서버가 chat 요청을
# 받았다는 흔적(서버 로그)이 있어야 "로컬 모델로" 라는 단언이 성립합니다.
LLM_LOGS="$("${OFFLINE[@]}" logs --no-color llm 2>&1 || true)"
case "$LLM_LOGS" in
  */v1/chat/completions*) ;;
  *) fail "R-8: succeeded, but the model server logged no /v1/chat/completions request - not proven to be answered by the local model" ;;
esac
RUN_ID=""
if [ -n "$HOST_PYTHON" ]; then
  RUN_ID="$(printf '%s' "$SCENARIO_JSON" | "$HOST_PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["run_id"])' 2>/dev/null || true)"
fi
echo "e2e: [R-8] ok - Run ${RUN_ID} succeeded on ${TEST_MODEL} with the network cut"

# --- R-10: 적재 -> Agent(MCP+knowledge) -> 도구 허용 -> Workflow Run ----------------------------
# 적재는 **아무것도 쌓지 않아도 `succeeded`** 가 됩니다 - 상태 API 가 청크 수를 내지 않으므로
# (spec 0004 2.4) 유일한 확인은 psql 실측입니다. `smoke` 가 같은 구멍을 같은 방식으로 막고
# 있습니다(scripts/smoke.sh). 실제 임베딩이 도는 자리는 여기뿐이라 더 느슨할 이유가 없습니다.
chunk_count() {
  "${OFFLINE[@]}" exec -T postgres sh -c \
    "PGPASSWORD=\"\$POSTGRES_PASSWORD\" psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc \"SELECT count(*) FROM data.knowledge_chunks\"" \
    | tr -d '\r\n'
}
BEFORE_CHUNKS="$(chunk_count)"
echo "e2e: [R-10] ingest -> agent -> allow -> workflow run (offline, embedding=${EMBED_MODEL})..." >&2
set +e
OFFLINE_JSON="$("${OFFLINE[@]}" exec -T -e SMOKE_API_KEY="$E2E_API_KEY" api python - scenario_offline <"$CLIENT_SCRIPT")"
OFFLINE_RC=$?
set -e
if [ "$OFFLINE_RC" -ne 0 ] || ! printf '%s' "$OFFLINE_JSON" | grep -Eq '"status": ?"succeeded"'; then
  fail "R-10: ingestion/agent/workflow chain did not reach a succeeded Workflow Run (scenario_offline exit ${OFFLINE_RC})"
fi
AFTER_CHUNKS="$(chunk_count)"
echo "e2e: [R-10] data.knowledge_chunks rows ${BEFORE_CHUNKS} -> ${AFTER_CHUNKS}" >&2
if ! [ "${AFTER_CHUNKS:-0}" -gt "${BEFORE_CHUNKS:-0}" ] 2>/dev/null; then
  fail "R-10: ingestion reported succeeded but stored no chunks (${BEFORE_CHUNKS} -> ${AFTER_CHUNKS}) - is /srv/knowledge-smoke in the worker image and is ${EMBED_MODEL} in the volume?"
fi
echo "e2e: [R-10] ok - Workflow Run succeeded (tool call is declared and allowed, not asserted)" >&2

# --- R-5: 화면 (D-20) ----------------------------------------------------------------------
# web 은 키가 발급된 **뒤에** 뜹니다(서버 env 로 읽습니다). 키는 이 호출의 환경에만 넣고 출력하지 않습니다.
# 호스트의 python 에 기대지 않습니다(`HOST_PYTHON` 은 없을 수 있습니다 - 위 RUN_ID 가 그래서 빕니다).
json_field() { printf '%s' "$2" | sed -n 's/.*"'"$1"'": *"\([^"]*\)".*/\1/p' | head -n1; }
EXPECT_AGENT="$(json_field agent_name "$OFFLINE_JSON")"
EXPECT_KNOWLEDGE="$(json_field knowledge_set_name "$OFFLINE_JSON")"
EXPECT_WORKFLOW="$(json_field workflow_name "$OFFLINE_JSON")"
# `/runs` 는 R-5 가 이름으로 부르는 화면입니다 - 기대값이 없으면 빈 목록도 통과합니다.
# Run 의 id 는 전체가 HTML 에 있습니다(`CopyableId` 의 `title`, 상세 링크의 href).
EXPECT_RUN="$(json_field run_id "$SCENARIO_JSON")"
if [ -z "$EXPECT_RUN" ]; then
  fail "R-5: the R-8 scenario did not report a run_id - /runs cannot be checked against real data"
fi
if [ -z "$EXPECT_AGENT" ] || [ -z "$EXPECT_KNOWLEDGE" ] || [ -z "$EXPECT_WORKFLOW" ]; then
  fail "R-5: scenario_offline did not report the names the screens must show"
fi
AETHER_WEB_API_KEY="$E2E_API_KEY" "${OFFLINE[@]}" up -d --wait --no-build web >&2 \
  || fail "R-5: web did not come up on the offline network"
set +e
"${OFFLINE[@]}" exec -T \
  -e WEB_EXPECT_AGENT="$EXPECT_AGENT" -e WEB_EXPECT_KNOWLEDGE="$EXPECT_KNOWLEDGE" \
  -e WEB_EXPECT_WORKFLOW="$EXPECT_WORKFLOW" -e WEB_EXPECT_RUN="$EXPECT_RUN" \
  api python - web-routes-check <scripts/web_routes_check.py >&2
WEB_RC=$?
set -e
[ "$WEB_RC" -eq 0 ] || fail "R-5: the screens did not show this run's data (web_routes_check exit ${WEB_RC})"
# 다섯 경로와 `/` 가 200 이고 오류 화면이 아니며, 그중 **넷**이 이 실행이 만든 값을 보입니다
# (`/`·`/settings` 는 목록이 아니라 기대값이 없습니다).
echo "e2e: [R-5] ok - six routes are up and four of them show this run's data" >&2

# --- spec 0007 R-8 (P5-9): 화면이 **만드는** 경로 ----------------------------------------------
# 서버 액션 createWorkflowAction 을 브라우저의 React 클라이언트와 같은 HTTP 호출로 지나고
# (액션 id 는 청크에서 **이름으로** 찾습니다 - 못 찾으면 실패), 그 이름이 /workflows 에 행으로
# 보여야 합니다. 이름은 이 실행만의 것입니다(R-5 의 workflow_name 과 겹치지 않습니다).
WRITE_NAME="e2e-ui-$$-${RANDOM}"
# 종료 코드만 보지 않습니다 - 아무것도 하지 않고 0 을 반환하는 확인도 초록이 되기 때문입니다.
# 출력을 받아 성공 표식(web_write_check: ok)을 확인하고, 로그에는 그대로 다시 내보냅니다.
set +e
WRITE_OUT="$("${OFFLINE[@]}" exec -T -e WEB_WRITE_NAME="$WRITE_NAME" \
  api python - web-write-check <scripts/web_write_check.py 2>&1)"
WRITE_RC=$?
set -e
printf '%s\n' "$WRITE_OUT" >&2
case "$WRITE_OUT" in
  *"web_write_check: ok"*) ;;
  *) fail "R-8 (spec 0007): web_write_check exited ${WRITE_RC} without its success marker - the write path was not proven" ;;
esac
[ "$WRITE_RC" -eq 0 ] || fail "R-8 (spec 0007): a Workflow made through the web server action was not created or not listed (web_write_check exit ${WRITE_RC})"
echo "e2e: [R-8/0007] ok - a Workflow created through the server action is listed on /workflows" >&2
echo "e2e: pass (project=${PROJECT}, model=${TEST_MODEL}, ${SECONDS}s)"
exit 0
