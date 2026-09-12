# Spec 0002 — Phase 1: Agent Runtime

| 키 | 값 |
| --- | --- |
| 번호 | 0002 |
| 근거 intent | [../intents/0002-phase-1-agent-runtime.md](../intents/0002-phase-1-agent-runtime.md) (승인됨 2026-09-12) |
| 작성일 | 2026-09-12 |
| 상태 | 초안 |
| 승인 | (비어 있음 — 4절 D-1 ~ D-16 을 전부 채택하는 것이 승인입니다) |
| 후속 plan | (승인 뒤 `plans/0002-phase-1-agent-runtime.md`) |

intent 가 정한 문제·범위·제약은 반복하지 않습니다. 이 문서는 intent 의 `Proposed Outcome` 여덟 항목을 판정 가능한 요구사항으로 옮기고, 그것을 만족시키는 경계와 계약을 정하고, intent 의 열린 질문 8건에 답을 제안해 사람이 내릴 결정을 한곳에 모읍니다. 작업 단위는 [../intents/mvp-backlog.md](../intents/mvp-backlog.md) 의 P1-1 ~ P1-9 이며, 이 spec 은 그 단위들이 공유하는 결정을 소유합니다. Phase 0 의 결정([0001-phase-0-foundation.md](0001-phase-0-foundation.md) D-1 ~ D-14)은 그대로 유효하고, 이 spec 이 바꾸는 것은 D-7 하나(2.11, D-15)뿐입니다.

## 1. 요구사항

판정 방법이 없는 요구사항은 요구사항이 아니므로, 모든 행에 판정을 붙였습니다. "Outcome n" 은 intent 0002 `Proposed Outcome` 의 n 번째 항목입니다.

| ID | 요구사항 | 유도 근거 | 판정 |
| --- | --- | --- | --- |
| R-1 | `POST /agents` 가 Agent 와 `Agent Version` 1 을 함께 만들고, `PUT /agents/{id}` 가 Version 2 를 만들며 Version 1 의 `definition` 은 바뀌지 않습니다. `GET /agents`, `GET /agents/{id}` 가 그것을 보여줍니다 | Outcome 1 | `api-integration`: 생성 → 조회 → 수정 → `GET /agents/{id}` 에 Version 2건, Version 1 의 `definition` 이 생성 시와 동일. 계약(OpenAPI)이 구현보다 먼저 커밋됨(`test_openapi_drift`) |
| R-2 | `POST /agents/{id}/run` 이 `queued` Run 을 즉시 돌려주고, worker 가 루프를 돌아 `GET /runs/{id}` 가 종결 상태(`succeeded` / `failed` / `cancelled` / `timed_out`)에 이릅니다. `POST /runs/{id}/cancel` 뒤에는 `cancelled` 입니다 | Outcome 2 | `api-integration`: testcontainers PostgreSQL + Redis 위에서 api 와 worker 를 같은 프로세스의 스레드로 띄워 fake 모델로 `succeeded` 까지. cancel 테스트는 `waiting` 을 주입해 `cancelled` 확인. `smoke`: 빌드된 이미지로 같은 흐름(2.11) |
| R-3 | Run 이벤트가 SSE 로 흘러나오고 순서가 상태 전이 순서와 같으며, 클라이언트가 끊겨도 Run 은 계속됩니다 | Outcome 3 | `api-integration`: 스트림에서 받은 `run.status` 이벤트의 `status` 열이 상태 기계의 전이 열과 같음. 스트림 소비자를 중간에 닫은 뒤 `GET /runs/{id}` 가 `succeeded` |
| R-4 | Run 타임아웃은 `timed_out`, 재시도 한도 초과는 사유 있는 `failed` 로 끝나고, 그 테스트는 **주입된 시계**로 결정적입니다 | Outcome 4 | `api-unit`(`packages/runtime`): `FakeClock` 을 전진시켜 `timed_out`, 실패하는 fake 모델로 `failed` + `failure_reason == "model_error"`. 테스트 코드에 `time.sleep` 없음(R-11) |
| R-5 | 한 Run 의 span 트리(Run → Task → 모델 호출 / 도구 호출)가 collector 에서 보이고 `GET /runs/{id}` 에 `trace_id` 가 있습니다 | Outcome 5 | `api-unit`: `InMemorySpanExporter` 로 부모–자식 관계 단언. `smoke`: `GET /runs/{id}` 의 `trace_id` 가 collector 의 file exporter 출력에 존재 |
| R-6 | 전부가 **fake 모델 어댑터로 네트워크 없이** 통과하고, OpenAI-호환 어댑터는 같은 포트 계약 테스트를 통과합니다 | Outcome 6, DP-4 | `api-unit`·`api-integration` 에 외부 네트워크 호출 0건(OpenAI-호환 어댑터의 테스트는 `httpx.MockTransport`). 실제 로컬 LLM 서버 실행은 사람의 수동 확인(2.5, 판정에 넣지 않음) |
| R-7 | AR-5 와 AR-7 이 실제로 발화합니다 — 위반 코드를 넣으면 `api-arch` 가 exit ≠ 0 | Outcome 6 | `tests/arch/` 부정 fixture: `aether_api` 가 `httpx` 를 직접 import, `aether_api` 가 `aether_runtime.application` 을 import → 둘 다 `lint-imports` 실패. 정상 코드에서 통과 |
| R-8 | 새 경로는 전부 인증 뒤에 있습니다. 인증 없는 요청은 401 | Outcome 8, DP-6 | `api-unit`: 라우트 표(2.2)의 모든 경로에 헤더 없는 요청 → 401. 라우터 등록 시 의존성이 빠진 경로를 잡는 구조 테스트 하나(`/healthz`·문서 경로만 예외 목록) |
| R-9 | `smoke` 가 `verify.sh` 에 집계되고, 로컬 verify 전체는 spec 0001 D-12 의 10분 안입니다 | Outcome 7 | `.harness/verify.json` 에 `smoke` 단계 `pass`, `duration_ms` 합계 ≤ 600,000. P1-9 에서 실측 기록 |
| R-10 | `{{성능_기준}}` 의 값이 사람이 고정한 숫자로 evaluation/README 에 적힙니다 | Outcome 7, EI-2 | `scripts/smoke.sh --bench` 의 출력(2.13)을 근거로 사람이 값을 적음. 에이전트는 값을 정하지 않음 |
| R-11 | 테스트는 결정적입니다 — 시간·난수·모델은 주입, `sleep` 으로 시계를 움직이지 않습니다 | Constraints | `tests/arch/test_no_sleep_in_tests.py`: `apps/*/tests`, `packages/*/tests` 에 `time.sleep(` 0건(허용 목록 없음). P0-9 의 `sleep(0.02)` 는 P1-2 에서 fake 에 시계를 주입해 제거 |
| R-12 | 계약이 구현보다 먼저입니다 — OpenAPI 와 이벤트 스키마가 커밋되어 있고 드리프트가 잡힙니다 | DP-1 | `test_openapi_drift`(기존) + `test_events_schema_drift`(신규): api 가 내보내는 이벤트 JSON Schema == 커밋된 `packages/sdk/events.schema.json`. `web-typecheck` 의 생성물 드리프트 검사가 `src/generated/events.d.ts` 도 덮음 |
| R-13 | worker 가 healthcheck 를 가집니다 — Redis 하트비트 키 | spec 0001 개정 8 이월 | compose 의 `worker` 가 `service_healthy` 가 됨. `api-integration`: 하트비트 키 TTL 이 갱신됨 |
| R-14 | `Observation` 은 모델에 **신뢰 경계 밖 데이터**로 표시되어 들어갑니다 | intent Constraints, AGENTS.md Trust | `api-unit`: 도구 결과가 모델 요청에 `role: tool` 메시지와 `trust: untrusted` 표지로만 들어가고 system 메시지에 섞이지 않음을 fake 모델이 받은 요청으로 단언 |

## 2. 설계

### 2.1 `packages/runtime` 의 배치

Phase 0 의 빈 껍데기를 채웁니다. 배치는 [../docs/architecture.md](../docs/architecture.md) 3.1(AR-8 ~ AR-12) 그대로이고, 이 절은 그 자리에 **무엇이** 들어가는지만 정합니다.

| 층 | 모듈 | 내용 |
| --- | --- | --- |
| `domain` | `agent.py` | `AgentDefinition`(pydantic, 2.3) — `schema_version`, 시스템 프롬프트, 모델, 도구 목록, 정책 |
| `domain` | `run.py` | `RunStatus`(enum, 값은 `data.run_execution_status` 와 동일), `transition(from, to)` 전이표(2.4), `RunState`(루프 진행 스냅숏 — 메시지 목록, 단계 번호, `Task` 목록) |
| `domain` | `task.py` | `Task` — Run 안에서 Planner 가 쪼갠 단위. Phase 1 은 모델 호출 1회 + 후속 도구 호출을 한 `Task` 로 봅니다 |
| `domain` | `events.py` | Run 이벤트 모델(2.7). `v: 1` |
| `domain` | `observation.py` | `Observation(tool, content, is_error, trust="untrusted")` — 도구 결과가 모델로 돌아가는 유일한 형태 |
| `domain` | `failure.py` | `FailureReason` 열거(2.8) |
| `application/ports/outbound` | `model_gateway.py` | `ModelGateway` Protocol — `complete`, `stream`, `embed`(2.5) |
| `application/ports/outbound` | `tools.py` | `ToolRegistry`(이름 → `Tool`), `Tool` Protocol(2.6) |
| `application/ports/outbound` | `run_state_store.py` | `RunStateStore` — `data.run_executions` 와 `data.run_states` 에 대한 계약 |
| `application/ports/outbound` | `event_sink.py` | `EventSink.publish(run_id, event)` — Redis 이벤트 스트림의 추상 |
| `application/ports/outbound` | `status_notifier.py` | `StatusNotifier.notify(run_id, status, at, …)` — `aether:runs:status` 의 추상 |
| `application/ports/outbound` | `clock.py` | `Clock.now()`, `Clock.monotonic()` — 시간은 전부 여기를 지납니다(R-4, R-11) |
| `application/ports/inbound` | `execute_run.py` | `ExecuteRun.__call__(run_id) -> RunStatus` — worker 가 부르는 유일한 문 |
| `application/usecases` | `execute_run.py` | Planner/Executor 루프(2.6). 위 포트만 봅니다 |
| `adapters/outbound/model_gateway` | `fake.py`, `openai_compatible.py` | 2.5. `httpx` 는 여기에만(AR-5, 2.12) |
| `adapters/outbound/tools` | `clock_tool.py`, `calculator.py`, `registry.py` | 프로세스 내부 도구 둘과 인메모리 레지스트리 |
| `adapters/outbound/db` | `run_state_store.py` | PostgreSQL 구현. `aether_data` 역할 |
| `adapters/outbound/redis` | `event_sink.py`, `status_notifier.py` | Redis Streams 구현 |
| `adapters/outbound/telemetry` | `spans.py` | span 생성 헬퍼. `opentelemetry` 는 어댑터에만(AR-9) |

`apps/worker` 는 `aether_runtime` 을 조립합니다(`main.py`, AR-10). worker 의 inbound 어댑터(`adapters/inbound/stream.py`)는 메시지를 받아 worker 의 inbound 포트 `HandleRunRequested` 를 부르고, 그 유스케이스가 runtime 의 `ExecuteRun` 포트를 부릅니다. worker 는 실행이 끝나야 메시지를 ack 합니다 — at-least-once(spec 0001 D-10)이므로 같은 Run 이 두 번 도착해도 `RunStateStore` 의 상태를 보고 재개하거나 무시합니다(2.4).

`apps/api` 는 `aether_runtime.domain` **만** import 합니다(AR-7 확장, 2.12) — `AgentDefinition` 검증과 `RunStatus`·이벤트 타입이 필요하기 때문입니다. `application`·`adapters` 는 import 하지 않습니다. api 는 실행하지 않고 선언합니다.

### 2.2 HTTP 계약 (DP-1)

전 경로가 `Authorization: Bearer` 뒤에 있습니다(spec 0001 2.9, R-8). 실패 응답 본문은 `{"detail": "<코드>"}` 하나의 형태입니다. OpenAPI 는 `packages/sdk/openapi.json` 에 커밋되고 구현이 그것을 만족합니다.

| 메서드·경로 | 요청 | 응답 | 비고 |
| --- | --- | --- | --- |
| `POST /agents` | `{ name, definition }` — `definition` 은 2.3 의 `AgentDefinition` | `201 { id, name, current_version: 1, created_at }` | `name` 중복 → `409 agent_name_taken`. `definition` 검증 실패 → `422` |
| `GET /agents` | `?limit=50&cursor=` | `200 { items: [{ id, name, current_version, updated_at }], next_cursor }` | 커서는 `(created_at, id)` |
| `GET /agents/{id}` | — | `200 { id, name, current_version, definition, versions: [{ version, created_at }], created_at, updated_at }` | `definition` 은 현재 버전의 것 |
| `PUT /agents/{id}` | `{ definition }` | `200` (GET 과 같은 본문, `current_version` +1) | 새 `Agent Version` 행 삽입 + `agents.updated_at` 갱신. 이전 버전 행은 트리거가 불변 보장 |
| `POST /agents/{id}/run` | `{ input: string, agent_version?: int }` | `202 { run_id, status: "queued", agent_version, requested_at }` | `control.runs` 삽입 → `aether:runs:requested` 통지. `agent_version` 생략 시 현재 버전. 응답 시각이 R-10 의 측정 대상 |
| `GET /runs/{id}` | — | `200 { run_id, agent_id, agent_version, status, requested_at, started_at, finished_at, failure_reason, trace_id, cancel_requested_at }` | `control.runs` 의 투영 열만 읽습니다(spec 0001 D-11). 투영이 아직 도착하지 않았으면 `queued` |
| `POST /runs/{id}/cancel` | — | `202 { run_id, status, cancel_requested_at }` | 멱등. `control.runs.cancel_requested_at` 기록 + `aether:runs:cancel` 통지. 이미 종결이면 현재 상태 그대로 `202` |
| `GET /runs/{id}/events` | 헤더 `Last-Event-ID` 선택 | `200 text/event-stream` | 2.7. Run 이 종결되고 `run.finished` 를 보낸 뒤 서버가 닫습니다 |

삭제(`DELETE /agents/{id}`)는 없습니다(backlog P1-1 범위 밖). `GET /runs` 목록도 Phase 1 에 없습니다 — Experience 화면이 없어 소비자가 없습니다(6절).

### 2.3 `AgentDefinition` — `agent_versions.definition` 의 내용 (열린 질문 3)

```json
{
  "schema_version": 1,
  "system_prompt": "You are …",
  "model": { "id": null },
  "tools": ["clock", "calculator"],
  "policy": {
    "timeout_seconds": 120,
    "max_steps": 8,
    "model_retries": 2,
    "tool_retries": 1,
    "backoff": { "base_seconds": 0.5, "max_seconds": 8.0 }
  }
}
```

| 키 | 뜻 | 검증 |
| --- | --- | --- |
| `schema_version` | 이 문서의 형태 번호. Phase 0 의 CHECK 제약이 요구하는 키 | `Literal[1]`. 다른 값은 422 |
| `system_prompt` | 모델의 system 메시지 | 비어 있지 않음 |
| `model.id` | 모델 식별자. `null` 이면 배포 설정 `AETHER_MODEL_ID` 를 씁니다(backlog P1-3 "모델 선택은 설정으로") | 문자열 또는 `null`. 어댑터 종류(fake / OpenAI-호환)는 `definition` 이 아니라 **배포 설정**입니다 — Agent 정의는 배포 환경과 무관해야 Cloud / On-Prem 을 같은 정의로 돕니다 |
| `tools` | 허용 도구 이름. 레지스트리에 없는 이름은 422 | 문자열 배열, 중복 없음 |
| `policy.timeout_seconds` | Run 전체 상한. 넘으면 `timed_out` | 1 ~ 3600 |
| `policy.max_steps` | Model → Tool 루프의 최대 반복. 넘으면 `failed(max_steps_exceeded)` | 1 ~ 64 |
| `policy.model_retries`, `policy.tool_retries` | 호출 단위 재시도 횟수. 넘으면 `failed(model_error / tool_error)` | 0 ~ 10 |
| `policy.backoff` | 재시도 사이 지수 백오프. `Clock` 을 통해 기다립니다 | `base_seconds` > 0, `max_seconds` ≥ `base_seconds` |

pydantic 모델 `AgentDefinition` 은 `aether_runtime.domain.agent` 에 있습니다(pydantic 은 AR-9 의 금지 목록에 없습니다 — 프레임워크가 아니라 데이터 검증 라이브러리이고, `Settings` 가 이미 씁니다). api 는 요청 본문을 이 모델로 검증한 뒤 `jsonb` 로 저장합니다. 이 모델의 JSON Schema 가 OpenAPI 에 그대로 실리므로 sdk 타입이 함께 생성됩니다. `schema_version` 을 올리는 것은 파괴적 변경 판정 대상입니다(DP-1).

### 2.4 Run 상태 기계 (P1-2)

값은 `data.run_execution_status` 와 같고(spec 0001 2.8), 전이는 코드가 소유합니다.

| 에서 → 로 | 누가 | 언제 |
| --- | --- | --- |
| (없음) → `queued` | api | `POST /agents/{id}/run`. `control.runs` 삽입 시점. `data.run_executions` 행은 worker 가 집을 때 `queued` 로 만듭니다 |
| `queued` → `running` | worker | 메시지를 집고 `cancel_requested_at` 이 비어 있음을 확인한 뒤 |
| `queued` → `cancelled` | worker | 집었을 때 `control.runs.cancel_requested_at` 이 이미 있음 |
| `running` → `waiting` | worker | 도구 호출 대기(Phase 1 에서는 도구가 프로세스 내부라 즉시 돌아오지만, 상태는 거칩니다 — Phase 2 의 MCP·Phase 4 의 HITL 이 이 상태를 씁니다) |
| `waiting` → `running` | worker | `Observation` 이 돌아옴 |
| `running` / `waiting` → `succeeded` | worker | 모델이 도구 호출 없이 최종 응답 |
| `running` / `waiting` → `failed` | worker | 재시도 한도 초과, `max_steps` 초과, 정의 오류(2.8) |
| `running` / `waiting` → `cancelled` | worker | 단계 사이에서 `aether:runs:cancel` 을 관측(협력적 취소 — 진행 중인 모델 호출은 끝나기를 기다립니다) |
| `running` / `waiting` → `timed_out` | worker | `Clock.monotonic()` 기준 `policy.timeout_seconds` 초과. 단계 사이와 모델·도구 호출의 자체 타임아웃(`timeout_seconds` 의 잔여)으로 판정 |

종결 상태(`succeeded`, `failed`, `cancelled`, `timed_out`)에서 나가는 전이는 없습니다. 허용되지 않은 전이는 `IllegalTransition` 예외이고 `api-unit` 이 전이표 전체를 테스트합니다.

**재개(P1-2 완료 판정).** `RunState`(메시지 목록, 단계 번호, `Task` 목록, 마지막 이벤트 `seq`)는 단계마다 `data.run_states` 에 저장됩니다. worker 가 죽었다 살아나면 consumer group 의 pending 메시지를 `XAUTOCLAIM` 으로 되찾고, `data.run_executions.status` 가 `running`/`waiting` 이면 저장된 `RunState` 에서 이어갑니다. 이미 종결이면 ack 만 합니다. 이 판정은 fake 저장소 + 유스케이스를 두 번 부르는 단위 테스트로 결정적으로 합니다 — 프로세스를 실제로 죽이는 테스트는 `smoke` 의 선택 항목으로 두되 Phase 1 판정에 넣지 않습니다.

**투영(열린 질문 2, D-2).** worker 는 전이마다 `aether:runs:status` 에 알리고, **api 프로세스 안의 소비자**(consumer group `aether-api`, FastAPI lifespan 에서 시작하는 백그라운드 태스크)가 그것을 읽어 `control.runs` 의 투영 열을 갱신합니다. 갱신은 멱등입니다 — 전이표가 허용하지 않는 역행(예: `succeeded` 뒤에 도착한 `running`)은 무시하고 ack 합니다. DB 커밋 뒤에 ack 하므로 at-least-once 중복 전달은 멱등 갱신으로 흡수됩니다. 별도 프로세스를 두지 않는 이유: Phase 1 의 api 인스턴스는 하나이고, 프로세스가 늘면 그때 같은 코드가 별도 프로세스로 옮겨갑니다(consumer group 이라 소비자 수는 자유). api 가 내려가 있는 동안의 메시지는 스트림에 남아 다음 기동 때 소비됩니다.

### 2.5 Model gateway (P1-3, 열린 질문 1 · Q6)

| 항목 | 결정 |
| --- | --- |
| 인터페이스 | `ModelGateway` Protocol — `complete(request: ModelRequest) -> ModelResponse`, `stream(request) -> Iterator[ModelDelta]`, `embed(texts: list[str]) -> list[list[float]]`. `ModelRequest` 는 메시지 목록(`system` / `user` / `assistant` / `tool`)과 도구 스키마 목록, `ModelResponse` 는 텍스트 또는 도구 호출 목록 |
| 어댑터 1 | `FakeModelGateway` — 시나리오 주입(스크립트된 응답 열). 도구를 부르는 시나리오·부르지 않는 시나리오·실패 시나리오. 전 테스트와 `smoke` 의 기본 |
| 어댑터 2 | `OpenAICompatibleGateway(base_url, model_id, api_key?)` — `/v1/chat/completions`(`stream: true` 포함)와 `/v1/embeddings`. **`httpx` 직접 호출, 벤더 SDK 없음.** 로컬 LLM 서버가 이 형식을 냅니다 |
| 선택 | 배포 설정. `AETHER_MODEL_ADAPTER=fake|openai_compatible`(기본 `fake`), `AETHER_MODEL_BASE_URL`, `AETHER_MODEL_ID`, `AETHER_MODEL_API_KEY`(선택, 비밀값 — 환경변수만, `.env.example` 은 `<optional>`) |
| **로컬 LLM 서버(Q6)** | **Ollama** 를 기본 후보로 채택합니다(D-1). 근거: 개발자 머신(Windows + Docker Desktop, Linux, macOS)에서 27B 양자화(GGUF)를 가장 적은 준비로 내고, `/v1/chat/completions` OpenAI-호환 API 가 있으며, 모델 pull 뒤에는 오프라인입니다. vLLM 은 Linux + NVIDIA 전제와 AWQ/GPTQ 양자화가 필요해 개발 기본으로는 무겁고, 서버 부하 시나리오가 오는 Phase 에 재판정합니다. compose 에는 `llm` 프로파일(`profiles: ["llm"]`)로 두어 기본 `up` 과 `probe`(spec 0001 R-4)에 영향이 없습니다 |
| **기본 테스트 모델** | intent Q6 의 사람 결정 그대로 — **Qwen3.8 27B 양자화**. 정확한 모델 태그(양자화 형식 포함, 예: `q4_K_M`)는 Ollama 레지스트리에서 **사람이 확인**해 `.env.example` 의 `AETHER_MODEL_ID` 기본값으로 적습니다(P1-3 의 H 항목). 27B 4-bit 는 VRAM 약 18 GB 이상이 필요합니다 — 없는 머신은 fake 어댑터만 씁니다. 이 모델은 판정(R-6)의 대상이 아니라 사람의 수동 확인 대상입니다 |
| 계약 테스트 | fake 와 OpenAI-호환 어댑터가 같은 포트 계약 테스트를 통과합니다. OpenAI-호환 쪽은 `httpx.MockTransport` 로 응답을 흉내내어 네트워크 0(R-6). 스트리밍은 SSE 청크 파싱을 포함 |

`embed` 는 Phase 1 의 루프가 쓰지 않지만 인터페이스에 둡니다(backlog P1-3 범위). 구현은 두 어댑터 모두 하고, 소비자는 Phase 3(Context Engine)입니다.

### 2.6 Planner/Executor 루프와 도구 (P1-4, 열린 질문 5)

루프는 `ExecuteRun` 유스케이스 하나입니다.

```text
RunState 로드(없으면 초기화: system_prompt + user input)
반복 (단계 ≤ max_steps, 시계 ≤ timeout):
  cancel 관측 → cancelled
  running: ModelGateway.complete(messages, tools) [재시도: model_retries]
  응답에 도구 호출 없음 → 최종 응답 저장 → succeeded
  도구 호출 있음 → Task 생성 → waiting
    ToolRegistry[name].run(arguments) [재시도: tool_retries] → Observation
    messages += role=tool, trust=untrusted → running
  RunState 저장, 이벤트 publish
```

**도구 인터페이스(D-5).** 지금부터 MCP tool 과 같은 모양입니다: `Tool.name`, `Tool.description`, `Tool.input_schema`(JSON Schema object), `Tool.run(arguments: dict) -> ToolResult(content: str, is_error: bool)`. Phase 2 는 `ToolRegistry` 의 구현을 MCP 클라이언트로 바꾸고 유스케이스는 바뀌지 않습니다. 이 모양이 아니면 Phase 2 가 루프를 다시 씁니다.

Phase 1 의 도구 둘 — `clock`(현재 시각, `Clock` 포트를 통해 얻으므로 테스트에서 결정적)과 `calculator`(사칙연산과 괄호만 받는 파서. `eval` 을 쓰지 않습니다).

**`Observation` 의 신뢰 경계(R-14).** 도구 결과는 `Observation(trust="untrusted")` 로만 루프에 들어오고, 모델 요청에서는 `role: tool` 메시지로만 나타납니다. system 메시지나 user 메시지에 이어 붙이지 않습니다. 모델 요청을 만드는 함수는 `Observation` 을 받으면 내용 앞뒤에 표지(`[observation tool=… trust=untrusted]` … `[/observation]`)를 붙입니다 — 모델이 그것을 지시로 읽지 않게 하는 완전한 방법은 없지만, 경계가 코드에 있어야 Phase 2 의 MCP Firewall 이 그 지점에 걸립니다. 도구 결과 크기는 `AETHER_OBSERVATION_MAX_CHARS`(기본 16,000)로 잘라 `truncated: true` 를 표시합니다.

### 2.7 Streaming (P1-6, 열린 질문 4)

| 항목 | 결정 |
| --- | --- |
| 전송 | worker 가 Run 마다 Redis Stream `aether:runs:{run_id}:events` 에 이벤트를 `XADD`(`MAXLEN ~ 10000`, 종결 뒤 TTL 24시간). api 의 `GET /runs/{id}/events` 는 그 스트림을 `XREAD` 로 읽어 SSE 로 내보냅니다(consumer group 없음 — 읽는 클라이언트가 여럿일 수 있습니다) |
| SSE 필드 | `id: <seq>` (Run 안에서 1 부터 단조 증가하는 정수), `event: <type>`, `data: <JSON>` |
| `data` 봉투 | `{ "v": 1, "run_id", "seq", "at", "type", "payload" }` |
| 이벤트 종류 | `run.status { status, failure_reason? }` · `task.started { task_id, step }` · `task.finished { task_id }` · `model.delta { text }` · `model.completed { finish_reason, usage? }` · `tool.called { task_id, name, arguments }` · `tool.result { task_id, name, is_error, content, truncated }` · `run.finished { status }`(항상 마지막) |
| 순서 | `seq` 순. `run.status` 의 순서가 2.4 의 전이 순서와 같습니다(R-3) |
| 재접속 | `Last-Event-ID` 를 받으면 그 `seq` 다음부터 보냅니다. 스트림이 남아 있는 동안(TTL) 이어보기가 **부수적으로** 성립하지만, Phase 1 의 판정 항목은 아닙니다(intent Non-goals). 보장하지 않습니다 |
| 클라이언트 단절 | api 는 읽기를 멈출 뿐입니다. worker 는 api 를 모릅니다(AR-7) |
| 스키마 소유 | 이벤트 모델은 `aether_runtime.domain.events`. `aether-api events-schema` 서브커맨드가 pydantic JSON Schema 를 내보내 `packages/sdk/events.schema.json` 에 커밋하고, `pnpm -F sdk run generate` 가 `json-schema-to-typescript` 로 `src/generated/events.d.ts` 를 만듭니다. 드리프트는 R-12 |

이벤트는 Phase 1 에서 **영속되지 않습니다**(Redis TTL 뒤 사라짐). Run 의 결과는 `data.run_states` 의 최종 `RunState` 에 있습니다. 이벤트 이력의 영속은 6절.

### 2.8 Retry / Timeout / Error Handling (P1-7)

| 항목 | 결정 |
| --- | --- |
| 타임아웃 | Run 시작(`running` 진입)의 `Clock.monotonic()` 을 기준으로 `policy.timeout_seconds`. 단계 사이마다 검사하고, 모델·도구 호출에는 잔여 시간을 자체 타임아웃으로 넘깁니다. 초과 → `timed_out` |
| 재시도 | 모델 호출 `model_retries`, 도구 호출 `tool_retries`. 백오프는 `policy.backoff` 의 지수 백오프를 `Clock.sleep(seconds)` 로 — 테스트의 `FakeClock` 은 즉시 전진합니다(R-11) |
| 사유 | `FailureReason` 열거: `model_error`(재시도 소진), `tool_error`(재시도 소진), `max_steps_exceeded`, `unknown_tool`(정의가 레지스트리에 없는 도구를 요구), `definition_invalid`(저장된 `definition` 이 현재 스키마로 검증 실패), `internal`. `data.run_executions.failure_reason` 과 `control.runs.failure_reason`(투영), `run.status` 이벤트의 `failure_reason` 에 같은 문자열 |
| 사람 개입 | 없음. HITL 은 Phase 4. `waiting` 은 Phase 1 에서 도구 대기만 뜻합니다 |

### 2.9 Trace (P1-8, 열린 질문 6)

| 항목 | 결정 |
| --- | --- |
| span 트리 | `run`(worker, 루트에 가까움) → `task` → `model.complete` / `tool.run`. 속성: `aether.run_id`, `aether.agent_version_id`, `aether.task_id`, `aether.tool.name`, `aether.model.id`. 프롬프트·응답 본문은 속성에 넣지 않습니다(비밀·용량) |
| 전파 | api 의 `POST /agents/{id}/run` span 이 `traceparent` 를 `aether:runs:requested` 메시지 필드에 넣고, worker 가 그것을 부모로 삼습니다 — 한 Run 이 한 trace 입니다. `trace_id` 는 worker 가 `data.run_executions.trace_id` 에 쓰고 status 알림에 실어 `control.runs.trace_id` 로 투영됩니다 |
| collector(D-7) | compose 에 `otel-collector` 서비스(`otel/opentelemetry-collector-contrib`, digest 고정)를 **기본 서비스**로 둡니다. 수신 OTLP/HTTP 4318, exporter 는 `debug`(로그)와 `file`(볼륨의 JSON Lines). `smoke` 는 `GET /runs/{id}` 의 `trace_id` 를 그 파일에서 grep 해 R-5 를 판정합니다. 이미지 하나가 늘지만 오프라인(`probe`)에는 영향이 없고 부팅 경로에 외부 호출도 없습니다(DP-4) |
| 테스트 | `api-unit` 은 `InMemorySpanExporter` 로 부모–자식을 단언. collector 는 `smoke` 에서만 |
| 대시보드 | 없음(6절). 파일과 로그가 Phase 1 의 "확인" 입니다 |

### 2.10 데이터 모델 변경 (마이그레이션 0002)

[../docs/data-model.md](../docs/data-model.md) 를 P1-1·P1-2·P1-5 가 갱신합니다. 여기는 경계와 제약만입니다.

| 대상 | 변경 | 누가 쓰는가 |
| --- | --- | --- |
| `control.runs` | 투영 열 추가 — `status`(text, 기본 `queued`), `started_at`, `finished_at`, `failure_reason`, `trace_id`, `cancel_requested_at`(전부 nullable, `status` 제외). `input` text(Run 의 사용자 입력 — 선언의 일부) | api(`aether_control`) 만 씁니다. worker 는 SELECT(기존 권한) |
| `data.run_states` | 신설 — `run_id` uuid PK·FK → `control.runs`, `state` jsonb, `updated_at`. `RunState` 스냅숏 | worker(`aether_data`) |
| `data.run_executions` | 변경 없음. `started_at`/`finished_at` nullable 은 spec 0001 개정 7 대로 유지 — 전이 규칙이 정해진 지금도 `queued` 행에는 값이 없는 것이 맞습니다 | worker |
| GRANT | `aether_data` 에 `data.run_states` 전부. 기존 권한 변경 없음 — `aether_control` 은 여전히 `data` 에 권한 없음(spec 0001 R-7 유지) | 마이그레이션 |

`control.runs.status` 는 text 로 두고 enum 을 만들지 않습니다 — 투영이지 정본이 아니며, 정본 enum 은 `data` 스키마에 있습니다. cross-schema FK 가 하나 더 늘어납니다(`data.run_states.run_id`) — spec 0001 C-8 의 soft reference 전환 대상에 추가하고 `docs/data-model.md` 4절에 적습니다.

### 2.11 검증 단계 — `smoke` 와 D-7 (P1-9, 열린 질문 8)

**`scripts/smoke.sh`**(에이전트가 만듦): `docker compose -f infra/docker/compose.yaml up --build -d --wait` → API 키 발급(`aether-api keys create`) → `POST /agents` → `POST /agents/{id}/run` → `GET /runs/{id}` 가 `succeeded` 가 될 때까지 폴링(상한 60초) → `trace_id` 를 collector 파일에서 확인 → `down`. 모델은 `AETHER_MODEL_ADAPTER=fake`(compose 기본값). `--bench` 옵션은 2.13.

**단계 수(D-15).** spec 0001 D-7 은 제품 단계를 **10개까지**로 확정했고 P0-7 이 그 10개를 다 썼습니다. 선택지는 둘입니다.

| 선택 | 무엇 | 대가 |
| --- | --- | --- |
| (a) 접기 | `smoke` 를 `api-integration` 안의 pytest 로 넣어 단계 수 16 유지 | `api-integration` 이 이미지 빌드까지 포함해 수 분짜리 단계가 되고, 통합 테스트 실패와 e2e 실패가 한 로그에 섞여 원인 분리가 나빠집니다. `layer` 도 `correctness` 로 묶여 `behavior` 계층은 self-check 의 `protection` 하나만 남습니다 |
| (b) 별도 단계 | `smoke\|behavior\|true\|scripts/smoke.sh` 를 11번째 제품 단계로. spec 0001 D-7 을 [실질] 개정 — "정확히 10개" → "11개(`smoke` 포함), 총 17" | 상한의 출처(harness-adoption.md 3.3 "열 개 넘게 늘리지 않습니다")를 한 번 더 넘습니다. 그래서 이 결정은 사람의 것이고, 근거를 `improvement-log/` 에 1건 남깁니다(EI-2 와 같은 절차) |

**이 spec 은 (b) 를 제안합니다(D-15).** 근거: 상한의 취지는 반복을 죽이지 않는 **시간** 예산이고, 그것은 D-12 의 10분이 지킵니다. 단계 하나가 더 늘어 나빠지는 것은 없고, 접으면 실패 원인 분리와 `behavior` 계층 점수가 나빠집니다. 시간을 지키는 장치는 둘 — `smoke` 는 web 을 띄우지 않고(`--no-deps` 로 api·worker·postgres·redis·otel-collector 만), 이미지는 `--build` 의 레이어 캐시를 씁니다. CI 는 `harness.yml` 에 buildx 캐시(`cache-from: type=gha`)를 더합니다(보호 파일, H). P1-9 가 로컬·CI 실측을 기록하고 D-12 를 넘으면 그때 (a) 로 돌아갑니다 — 그 판정도 사람이 합니다.

`harness.config` 의 배열 원소는 큰따옴표 문자열이라 명령 안의 따옴표는 작은따옴표입니다(spec 0001 2.11). 후보 파일은 `bash -c` 로 **실제 실행**해 검증합니다(improvement-log `2026-09-11-014`).

### 2.12 아키텍처 규칙의 변경 (보호 파일 `.importlinter`, 사람)

| 규칙 | 변경 | 왜 지금 |
| --- | --- | --- |
| AR-5 | `forbidden_modules` 에 `httpx` 추가, `ignore_imports` 에 `aether_runtime.adapters.outbound.model_gateway.** -> httpx`. `unmatched_ignore_imports_alerting` 을 `warn` → `error` 로 되돌림 | OpenAI-호환 어댑터가 SDK 대신 `httpx` 를 쓰므로 "LLM 호출은 gateway 한 곳" 이 `httpx` 에도 걸려야 합니다. 어댑터가 생기면 ignore 가 실제로 매칭되어 `error` 가 맞습니다(`.importlinter` 주석의 예고) |
| AR-7 | `aether_api` → `aether_runtime.application`, `aether_runtime.adapters` 금지 추가(`aether_runtime.domain` 만 허용) | 2.1. Control Plane 은 타입만 알고 실행을 모릅니다 |
| AR-10 | **구조 테스트로 승격** — `tests/arch/test_composition_only_in_main.py`: `adapters.inbound` 와 `adapters.outbound` 를 함께 import 하는 모듈은 `apps/*/main.py` 만. 보호 파일 변경 없음 | `.importlinter` 로는 "main 만 예외" 를 표현하기 어렵고, AST 검사 하나로 충분합니다 |

Phase 2 의 MCP HTTP 전송이 `httpx` 를 쓰게 되면 AR-5 의 ignore 에 `aether_mcp.adapters.outbound.**` 를 더하는 것은 그때의 spec 이 정합니다.

### 2.13 `{{성능_기준}}` 의 측정 정의 (열린 질문 7)

| 항목 | 정의 |
| --- | --- |
| 지표 | `POST /agents/{id}/run` 의 응답 지연 **P95**(요청 전송 → 202 수신). Run 의 실행 시간이 아닙니다 — 선언의 비용을 봅니다 |
| 절차 | `scripts/smoke.sh --bench`: smoke 와 같은 compose 위에서 같은 Agent 에 **순차** 200회 요청, 처음 20회는 워밍업으로 제외, 나머지 180회의 P50·P95·max 를 `.harness/smoke-bench.json` 에 기록 |
| 환경 | 기록에 머신(OS, CPU, Docker), 모델 어댑터(`fake`), 커밋 해시를 함께 남깁니다. 값은 환경 종속이므로 기준값에는 환경 이름이 붙습니다 |
| 값 | **사람이** P1-9 에서 실측을 보고 `evaluation/README.md` 의 `{{성능_기준}}` 에 적습니다(EI-2). 에이전트는 실측을 보고하고 값을 정하지 않습니다 |

### 2.14 worker healthcheck (spec 0001 개정 8 이월)

worker 는 5초마다 Redis 키 `aether:worker:{consumer}:heartbeat` 를 TTL 15초로 `SET` 합니다. compose 의 healthcheck 는 `python -c` 한 줄로 그 키의 존재를 확인합니다(worker 이미지에 `redis-cli` 가 없습니다). 이제 `worker` 도 `service_healthy` 가 되고, `smoke` 는 `--wait` 로 worker 가 준비된 뒤 Run 을 만듭니다.

### 2.15 설정 (추가되는 환경변수)

| 변수 | 앱 | 기본값 | 뜻 |
| --- | --- | --- | --- |
| `AETHER_MODEL_ADAPTER` | worker | `fake` | `fake` / `openai_compatible` |
| `AETHER_MODEL_BASE_URL` | worker | (없음) | OpenAI-호환 서버. compose `llm` 프로파일에서는 `http://llm:11434/v1` |
| `AETHER_MODEL_ID` | worker | (사람이 적음, 2.5) | 기본 모델 태그. `definition.model.id` 가 `null` 일 때 |
| `AETHER_MODEL_API_KEY` | worker | (없음) | 선택. 비밀값 — `.env.example` 은 `<optional>` |
| `AETHER_OBSERVATION_MAX_CHARS` | worker | `16000` | 2.6 |
| `AETHER_EVENTS_MAXLEN` / `AETHER_EVENTS_TTL_SECONDS` | worker | `10000` / `86400` | 2.7 |
| `AETHER_WORKER_HEARTBEAT_SECONDS` | worker | `5` | 2.14 |
| `AETHER_REDIS_URL` | api | `redis://localhost:6379/0` | api 가 처음으로 Redis 를 씁니다(통지·투영·이벤트 읽기) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | api, worker | (없음) | compose 에서 `http://otel-collector:4318`. 없으면 no-op(spec 0001 2.3) |

## 3. 우려 지점

| ID | 우려 | 어떻게 다루는가 |
| --- | --- | --- |
| C-1 | **at-least-once 와 중복.** Redis Streams 의 재전달로 같은 `requested` 메시지가 두 번 오거나, `status` 알림이 두 번 옵니다 | worker 는 `data.run_executions` 의 현재 상태로 재개·무시를 결정하고(2.4), api 의 투영 갱신은 전이표로 역행을 걸러 멱등(2.4). 둘 다 단위 테스트 |
| C-2 | **Redis 가 메시지를 잃으면 Run 이 `queued` 에 머뭅니다.** 선언(`control.runs`)은 남지만 아무도 집지 않습니다 | Phase 1 은 이 상태를 **관측 가능하게만** 합니다 — `GET /runs/{id}` 가 `queued` 와 `requested_at` 을 보여줍니다. 고아 Run 재통지(reconciliation)는 6절. AOF 가 켜져 있어(spec 0001 2.7) 손실 창은 좁습니다 |
| C-3 | **취소는 협력적입니다.** 진행 중인 모델 호출은 끝나기를 기다리므로 `cancel` 뒤 `cancelled` 까지 최대 한 호출의 시간이 걸립니다 | 계약에 적습니다(`202` + 최종 상태는 이벤트/GET 으로). 강제 중단은 프로세스 격리가 오는 Phase 의 일 |
| C-4 | **AR-7 과 `cancel`.** Control → Data 방향의 두 번째 스트림(`aether:runs:cancel`)이 생깁니다 | 방향은 같습니다(Control 이 선언, Data 가 읽음). `cancel_requested_at` 이 `control.runs` 에 있어 메시지를 잃어도 worker 가 집을 때 봅니다(2.4). AR-7 계약(`.importlinter`)에는 변화가 없습니다 |
| C-5 | **api 가 Redis 를 처음 씁니다.** 투영 소비자가 api 프로세스 안에 있어 api 의 기동이 Redis 에 걸립니다 | 소비자는 lifespan 에서 백오프 재시도로 붙고, 붙지 못해도 HTTP 는 뜹니다(`/healthz` 는 liveness). 투영이 멈추면 `GET /runs/{id}` 가 낡은 상태를 답하는 것이 관측 가능한 증상입니다 — readiness 는 6절 |
| C-6 | **이벤트 스트림의 메모리.** Run 마다 스트림 하나 | `MAXLEN ~ 10000` 과 종결 뒤 TTL 24시간(2.7). 부하 시나리오는 `load` 단계의 일 |
| C-7 | **모델은 비결정적입니다.** 실제 LLM 으로 도는 테스트는 재현되지 않습니다 | 판정은 전부 fake(R-6). 실제 모델은 사람의 수동 확인이며 그 절차는 README 에 적습니다. `AETHER_MODEL_ADAPTER` 기본값이 `fake` 라 실수로 실제 모델이 CI 에 들어가지 않습니다 |
| C-8 | **비밀값 하나가 늘 수 있습니다** — `AETHER_MODEL_API_KEY` | 환경변수만, 로그·span 속성·이벤트에 넣지 않음. 로컬 Ollama 는 키가 없어 기본은 비어 있습니다. 비밀값 스캔 job 이 계속 봅니다 |
| C-9 | **보호 파일 변경이 네 곳입니다** — `.importlinter`(2.12), `harness.config`(2.11 `smoke`), `harness.yml`(빌드 캐시), `evaluation/README.md`(2.13 값) | 각각 별도 PR, `harness-change` 라벨, 사람. 순서와 준비물은 plan 0002 의 "사람 손" 절이 정합니다. `.importlinter` 는 P1-3 **착수 전**(AR-5 가 어댑터 첫 커밋부터 걸려야 함), 나머지 셋은 P1-9 |
| C-10 | **D-7 을 넘습니다**(2.11) | 사람 결정 D-15 + `improvement-log/` 1건. 시간 예산(D-12)은 유지하고 P1-9 가 실측으로 확인. 넘으면 (a) 로 회귀 |
| C-11 | **`Observation` 표지는 완화이지 방어가 아닙니다**(2.6) | Phase 1 의 도구는 신뢰할 수 있는 프로세스 내부 함수 둘입니다. 외부 콘텐츠가 도구로 들어오는 Phase 2 에서 MCP Firewall 이 같은 지점에 붙습니다. 경계를 지금 코드로 두는 것이 그 준비입니다 |

## 4. 결정 요청

이 spec 을 승인하면 아래가 채택됩니다. 하나라도 다르게 하려면 그 항목을 먼저 고친 뒤 승인합니다.

| ID | 결정 | 닫히는 질문 | 근거 |
| --- | --- | --- | --- |
| D-1 | 로컬 LLM 서버의 기본은 **Ollama**(compose `llm` 프로파일, OpenAI-호환 API). 기본 테스트 모델은 intent 의 결정대로 **Qwen3.8 27B 양자화**이고 정확한 태그는 사람이 확인해 `.env.example` 에 적습니다. 판정은 전부 fake 어댑터로 | **Q6 (intent OQ 1)** | 2.5 |
| D-2 | `control.runs` 의 투영은 **api 프로세스 안의 `aether:runs:status` 소비자**(consumer group `aether-api`, lifespan 백그라운드)가 갱신합니다. 갱신은 전이표로 멱등, DB 커밋 뒤 ack | intent OQ 2 | 2.4, C-1, C-5 |
| D-3 | `agent_versions.definition` 은 2.3 의 `AgentDefinition`(`schema_version: 1`, `system_prompt`, `model.id`, `tools`, `policy`). 어댑터 종류는 정의가 아니라 배포 설정 | intent OQ 3 | 2.3 |
| D-4 | SSE 이벤트는 2.7 의 봉투(`v: 1`, `seq`, `type`, `payload`)와 8종. 전송은 Run 별 Redis Stream. 스키마는 `events.schema.json` 으로 커밋, TS 타입 생성 | intent OQ 4 | 2.7, R-12 |
| D-5 | 프로세스 내부 도구도 **MCP tool 모양**(`name`, `description`, `input_schema`, `run → ToolResult`) | intent OQ 5 | 2.6 |
| D-6 | `Observation` 은 `role: tool` + `trust: untrusted` 표지로만 모델에 들어갑니다 | — | 2.6, R-14 |
| D-7 | compose 에 `otel-collector` 를 **기본 서비스**로, exporter 는 `debug` + `file`. 대시보드 없음 | intent OQ 6 | 2.9 |
| D-8 | `{{성능_기준}}` 은 `POST /agents/{id}/run` 응답 P95, `smoke.sh --bench` 순차 200회(워밍업 20 제외), 환경 이름을 붙여 **사람이** 값을 적음 | intent OQ 7 | 2.13 |
| D-9 | HTTP 계약은 2.2 의 8개 경로. 수정은 `PUT /agents/{id}` 로 새 Version. 삭제와 Run 목록은 없음 | — | 2.2 |
| D-10 | 상태 기계는 2.4 의 전이표. `waiting` 을 Phase 1 에서도 거칩니다. 재개는 `data.run_states` 스냅숏 + `XAUTOCLAIM` | — | 2.4 |
| D-11 | 취소는 **협력적**: `cancel_requested_at` + `aether:runs:cancel`. 단계 사이에서 관측 | — | 2.4, C-3 |
| D-12 | 마이그레이션 0002: `control.runs` 투영 열 + `input`, `data.run_states` 신설. `aether_control` 의 `data` 권한은 여전히 없음 | — | 2.10 |
| D-13 | AR-5 에 `httpx` 를 더하고 alerting 을 `error` 로, AR-7 에 `aether_api → aether_runtime.application/adapters` 금지를 더함(`.importlinter`, 사람). AR-10 은 구조 테스트로 승격 | — | 2.12 |
| D-14 | 테스트에 `time.sleep` 금지를 구조 테스트로 고정하고, P0-9 의 `sleep(0.02)` 는 P1-2 에서 시계 주입으로 제거 | — | R-11, improvement-log 016 |
| D-15 | **`smoke` 는 11번째 제품 단계**(`behavior` 계층, `scripts/smoke.sh`). spec 0001 **D-7 을 [실질] 개정** — 제품 단계 11개, 총 17. 시간 예산 D-12(10분)는 유지하고 P1-9 가 실측. 근거를 `improvement-log/` 에 1건 | intent OQ 8 | 2.11, C-10 |
| D-16 | worker healthcheck 는 Redis 하트비트 키(2.14). api 도 Redis 를 씁니다(`AETHER_REDIS_URL`) | — | 2.14, 2.15 |

승인과 함께 [../intents/0002-phase-1-agent-runtime.md](../intents/0002-phase-1-agent-runtime.md) 의 Open Questions 1 ~ 8 을 닫고(7 은 "측정 정의는 닫힘, 값은 P1-9" 로), [../intents/intent.md](../intents/intent.md) 의 머리 표를 갱신하고, spec 0001 에 D-15 의 [실질] 개정 행을 남깁니다.

## 5. 검증 매핑

| R | 단위 | 판정 명령 또는 절차 |
| --- | --- | --- |
| R-1 | P1-1 | `api-integration`: 생성·조회·수정 테스트. `api-unit`: `test_openapi_drift` |
| R-2 | P1-2, P1-4, P1-5 | `api-integration`: PG + Redis testcontainers, worker 스레드, fake 모델 → `succeeded` / `cancelled`. `smoke` |
| R-3 | P1-6 | `api-integration`: 이벤트 순서 == 전이 순서, 단절 뒤 `succeeded` |
| R-4 | P1-7 | `api-unit`(`packages/runtime/tests`): `FakeClock` 타임아웃·재시도 |
| R-5 | P1-8 | `api-unit`: `InMemorySpanExporter`. `smoke`: collector 파일에서 `trace_id` |
| R-6 | P1-3 | `api-unit`: 두 어댑터 계약 테스트(`httpx.MockTransport`). 네트워크 0 |
| R-7 | P1-3, P1-5 | `api-arch` + `tests/arch/` 부정 fixture(`httpx` in api, `aether_runtime.application` in api) |
| R-8 | P1-1, P1-5, P1-6 | `api-unit`: 경로별 401 + 의존성 누락 구조 테스트 |
| R-9 | P1-9 | `.harness/verify.json`: `smoke` pass, `duration_ms` 합계 ≤ 600,000 |
| R-10 | P1-9 | `scripts/smoke.sh --bench` → `.harness/smoke-bench.json` → 사람이 evaluation/README 에 값 |
| R-11 | P1-2 | `tests/arch/test_no_sleep_in_tests.py` |
| R-12 | P1-1, P1-6 | `api-unit`: `test_openapi_drift`, `test_events_schema_drift`. `web-typecheck` 생성물 드리프트 |
| R-13 | P1-5 | compose `worker` healthy. `api-integration`: 하트비트 키 TTL |
| R-14 | P1-4 | `api-unit`: fake 모델이 받은 요청의 메시지 구조 |

## 6. Non-goals

intent 의 것을 반복하고, 설계하면서 새로 뺀 것을 더합니다.

| 항목 | 언제 |
| --- | --- |
| MCP Gateway·Firewall, 외부 시스템 연동 | Phase 2. 도구 인터페이스(D-5)가 그 자리 |
| Context Compiler, RAG, Memory, Knowledge | Phase 3. `embed` 는 인터페이스만 |
| HITL, Approval, Workflow | Phase 4. `waiting` 상태가 그 자리 |
| Permission, Policy, 조직·사용자, SSO | Phase 8 |
| Model Registry, 벤더 SDK, 프롬프트 캐싱, 비용 집계, vLLM 등 다른 서버 | Phase 6 / 서버 부하가 오는 Phase |
| `apps/web` 화면, `GET /runs` 목록, `DELETE /agents/{id}` | Experience 의 Phase. 소비자가 생길 때 |
| SSE 재접속 이어보기의 **보장**, WebSocket | 이후. `seq` 와 `Last-Event-ID` 만 남깁니다 |
| 이벤트 이력의 영속(DB) | 이후. Phase 1 은 Redis TTL |
| 고아 Run 재통지(reconciliation), 강제 취소 | 이후. C-2, C-3 |
| readiness 엔드포인트 | 이후. Phase 1 의 compose 는 healthcheck 로 충분 |
| 부하 테스트(`load`), 대시보드, 샘플링 정책, 프로세스를 실제로 죽이는 재개 테스트 | 이후 |
| Kubernetes, Air-Gapped 번들 | Month 6 / Phase 11 |

## 관련 문서

- [../intents/0002-phase-1-agent-runtime.md](../intents/0002-phase-1-agent-runtime.md) — 근거 intent
- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — P1-1 ~ P1-9
- [0001-phase-0-foundation.md](0001-phase-0-foundation.md) — 유효한 Phase 0 결정(D-7 만 D-15 로 개정)
- [../docs/architecture.md](../docs/architecture.md) — AR-*, DP-*, 3.1 배치
- [../docs/domain.md](../docs/domain.md) — `Run`, `Task`, `State`, `Observation`
- [../docs/data-model.md](../docs/data-model.md) — 열 단위 정본(P1 이 갱신)
- [../evaluation/README.md](../evaluation/README.md) — `{{성능_기준}}`, REP-2·4·8
- [../harness/rules/evaluation-integrity.rule.md](../harness/rules/evaluation-integrity.rule.md) — EI-2
- [README.md](README.md) — spec 의 규칙
