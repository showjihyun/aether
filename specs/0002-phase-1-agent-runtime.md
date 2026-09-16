# Spec 0002 — Phase 1: Agent Runtime

| 키 | 값 |
| --- | --- |
| 번호 | 0002 |
| 근거 intent | [../intents/0002-phase-1-agent-runtime.md](../intents/0002-phase-1-agent-runtime.md) (승인됨 2026-09-12) |
| 작성일 | 2026-09-12 |
| 상태 | 승인됨 |
| 승인 | showjihyun, 2026-09-12 (D-1 ~ D-19 채택. 리뷰 F-1 ~ F-21 반영본 — F-2 는 (a) lease, F-18 은 11번째 단계 유지) |
| 후속 plan | [../plans/0002-phase-1-agent-runtime.md](../plans/0002-phase-1-agent-runtime.md) (승인됨 2026-09-12) |
| 개정 8 | [편집] 2026-09-16. R-9·R-10 실측 기록 — 로컬 verify 17단계 163.4초(smoke 39.7초, api-integration 37.7초), CI `verify` job 2분 58초 ~ 3분 16초(bake 캐시 포함). D-15 회귀 조건(smoke ≤ 240초, CI ≤ 8분, 합계 ≤ 600초) 전부 충족. `{{성능_기준}}` 은 사람이 **150 ms** 로 고정(H-7, EI-2) — 실측 p50 33.4 · p95 36.8 · max 40.1 ms |
| 개정 7 | [편집] 2026-09-16. P1-9 실측 — (a) 2.11 격리에 `infra/docker/compose.smoke.yaml`(api 호스트 포트 `!reset []`, collector 출력 `./out/otel-smoke`): 개발 스택과 포트 충돌 없음을 확인. (b) 시나리오의 HTTP 호출은 호스트가 아니라 **api 컨테이너 안에서** `scripts/smoke_client.py`(stdin 으로 넘김, 표준 라이브러리만) — 호스트에 curl·jq·포트를 가정하지 않음. (c) CI 캐시: bake 는 compose 의 상대 빌드 컨텍스트를 **실행 위치** 기준으로 해석하므로 `docker/bake-action@v6` 의 `source: .` + `workdir: infra/docker`(v7 에는 `workdir` 없음, improvement-log `2026-09-16-002`). (d) 2.13 측정 위치는 api 컨테이너 안(`localhost:8000`) — 호스트·Docker 네트워크 왕복을 포함하지 않음, 결과 파일 `infra/docker/out/smoke-bench.json`. (e) C-12: 로컬 compose v2.29.7 에서 `up --wait` + 일회성 `migrate` 가 그대로 성공. D-15 근거 `2026-09-16-001` |
| 개정 6 | [편집] 2026-09-15. P1-8 구현에서 드러난 배치 — api 에 outbound 포트 `RequestTracing`(`span`·`current_traceparent`)과 어댑터 `otel_request_tracing.py` 를 두어 `RequestRun` 이 `run.request` span 안에서 선언·통지하고 그 `traceparent` 를 실음(application 은 `opentelemetry` 를 모름, AR-9). worker 는 `adapters/outbound/otel_trace_context.py` 가 `TraceContext` 를 구현. 어댑터는 `TracerProvider` 를 주입받아 테스트가 전역을 덮지 않음. R-5 판정 경로를 2.9·2.11 과 같은 `infra/docker/out/otel-smoke/spans.jsonl` 로. collector 이미지는 `0.160.0` digest 고정 |
| 개정 5 | [편집] 2026-09-15. P1-7 구현이 2.8 을 구체화 — (a) 타임아웃 기준 시계는 `Clock.monotonic()` 이 아니라 저장된 `started_at` 과 `Clock.now()`: monotonic 값은 재개(R-16, 프로세스 재시작)를 넘어 보존되지 않아 재개한 Run 이 예산을 새로 받는 구멍이 생김. (b) 검사 지점 셋(단계 시작·호출 직전·백오프 직전). (c) 재시도 가능한 모델 오류의 분류(timeout·protocol·5xx·429, 그 밖 4xx 는 즉시 실패). (d) 도구는 예외만 재시도, `is_error` 결과는 `Observation`. (e) 백오프 공식. (f) C-13 의 갱신 스레드를 outbound 포트 `LeaseKeeper` 로 — 잃은 단계는 저장·발행·release 없이 `LeaseHeld`. R-4 의 뜻은 그대로 |
| 개정 4 | [편집] 2026-09-13. P1-5a 실측 — (a) 2.7 의 Redis 오류 문자열: redis-py 는 `ResponseError` 의 `str()` 에서 `ERR ` 접두어를 떼므로 어댑터는 `The ID specified in XADD is equal or smaller` 로 매칭(뜻 동일). (b) 2.16: 테스트 **파일** basename 도 저장소 전체에서 유일해야 함 — pytest 기본(prepend) import 는 `__init__.py` 없는 tests 디렉터리의 테스트 모듈을 basename 으로 올리므로 `apps/worker/tests/test_settings.py` 는 `test_worker_settings.py` 로. `explicit_package_bases`/`pythonpath` 는 헬퍼 import 만 해결하고 테스트 파일 이름 충돌은 해결하지 않음 |
| 개정 3 | [편집] 2026-09-12. P1-2a 실행에서 드러난 사실 — pytest 9 는 `pytest_plugins` 를 **rootdir 의 conftest 에서만** 허용합니다(`Failed: Defining 'pytest_plugins' in a non-top-level conftest is no longer supported`, 실측). 2.16 의 "api conftest 가 `pytest_plugins` 로 재사용" 을 "루트 `conftest.py` 가 한 번 등록, `apps/api/tests/conftest.py` 는 삭제" 로. fixture 이름·동작은 그대로 |
| 개정 2 | [편집] 2026-09-12. plan 0002 리뷰 반영 — 2.7 `EventSink` 는 같은 `seq` 재발행을 성공으로(Redis 가 top ID 이하의 explicit `XADD` 를 거부하므로 어댑터가 흡수), 2.9·2.11 collector 출력은 `.harness/`(가드 보호 패턴) 대신 `infra/docker/out/`, 2.11 smoke 는 `compose.ci.yaml` 의 `image:` + `--no-build`·bake target `api worker`·`docker/bake-action`, 2.12 R-7 은 `src` 만 복사해 `PYTHONPATH` 앞에, 2.16 `wait_until`·PG fixture 는 `tests/support/`, 2.4 `XAUTOCLAIM min-idle` 은 설정, C-9 의 `.importlinter` 시점 |
| 개정 1 | [실질] 2026-09-12. plan 0002 리뷰 — **D-18 교체**: `--import-mode=importlib` 는 기존 `from fakes import …` 를 깨고, `explicit_package_bases` 단독은 src 레이아웃 모듈 이름을 갈라 놓습니다(실험으로 확인). 채택은 pytest `pythonpath = ["."]`(기본 prepend) + mypy `explicit_package_bases = true` + `mypy_path` 9개 `src` + 테스트의 네임스페이스 경로 import. `pytest-socket` 은 `--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1` 을 `addopts` 에(단독 `--disable-socket` 은 `TestClient` 9건을 깸), `integration` 은 `enable_socket` — R-6 은 "loopback 외 네트워크 0". **D-13**: 벤더 SDK ignore 셋 삭제(매칭되지 않는 ignore 는 `error` 를 실패시킴), `.importlinter` 변경은 P1-3 병합 뒤 한 번. plan 0002 승인(showjihyun, 2026-09-12)이 이 개정의 승인 |

intent 가 정한 문제·범위·제약은 반복하지 않습니다. 이 문서는 intent 의 `Proposed Outcome` 여덟 항목을 판정 가능한 요구사항으로 옮기고, 그것을 만족시키는 경계와 계약을 정하고, intent 의 열린 질문 8건에 답을 제안해 사람이 내릴 결정을 한곳에 모읍니다. 작업 단위는 [../intents/mvp-backlog.md](../intents/mvp-backlog.md) 의 P1-1 ~ P1-9 이며, 이 spec 은 그 단위들이 공유하는 결정을 소유합니다. Phase 0 의 결정([0001-phase-0-foundation.md](0001-phase-0-foundation.md) D-1 ~ D-14)은 그대로 유효하고, 이 spec 이 바꾸는 것은 D-7 하나(2.11, D-15)뿐입니다. 2.3 의 스트림 문장은 [편집] 으로 사실에 맞춥니다(4절 끝).

## 1. 요구사항

판정 방법이 없는 요구사항은 요구사항이 아니므로, 모든 행에 판정을 붙였습니다. "Outcome n" 은 intent 0002 `Proposed Outcome` 의 n 번째 항목입니다.

| ID | 요구사항 | 유도 근거 | 판정 |
| --- | --- | --- | --- |
| R-1 | `POST /agents` 가 Agent 와 `Agent Version` 1 을 함께 만들고, `PUT /agents/{id}` 가 Version 2 를 만들며 Version 1 의 `definition` 은 바뀌지 않습니다 | Outcome 1 | `api-integration`: 생성 → 수정 → `GET /agents/{id}` 의 `current_version == 2`, `GET /agents/{id}/versions/1` 의 `definition` 이 생성 시 본문과 동일 — **API 로만** 판정. 계약(OpenAPI)이 구현보다 먼저 커밋됨(`test_openapi_drift`) |
| R-2 | `POST /agents/{id}/run` 이 `queued` Run 을 즉시 돌려주고, worker 가 루프를 돌아 `GET /runs/{id}` 가 종결 상태(`succeeded` / `failed` / `cancelled` / `timed_out`)에 이릅니다. `POST /runs/{id}/cancel` 뒤에는 `cancelled` 입니다 | Outcome 2 | `api-integration`: testcontainers PostgreSQL + Redis 위에서 api 와 worker 를 같은 프로세스의 스레드로 띄워 fake 모델로 `succeeded` 까지. cancel 은 fake 모델을 단계 사이에서 멈춰 세운 뒤 요청해 `cancelled` 확인. `smoke`: 빌드된 이미지로 같은 흐름(2.11) |
| R-3 | Run 이벤트가 SSE 로 흘러나오고 순서가 상태 전이 순서와 같으며, 클라이언트가 끊겨도 Run 은 계속됩니다 | Outcome 3 | `api-integration`: 스트림에서 받은 `run.status` 의 `status` 열 == 상태 기계의 전이 열. 소비자를 중간에 닫은 뒤 `GET /runs/{id}` 가 `succeeded` — 비동기 투영은 `wait_until(predicate, timeout)` 헬퍼(조건 폴링, 2.16) 하나로만 기다립니다 |
| R-4 | Run 타임아웃은 `timed_out`, 재시도 한도 초과는 사유 있는 `failed` 로 끝나고, 그 테스트는 **주입된 시계**로 결정적입니다 | Outcome 4 | `api-unit`(`packages/runtime/tests`): `FakeClock` 을 전진시켜 `timed_out`, 실패하는 fake 모델로 `failed` + `failure_reason == "model_error"` |
| R-5 | 한 Run 의 span 트리(Run → Task → 모델 호출 / 도구 호출)가 collector 에서 보이고 `GET /runs/{id}` 에 `trace_id` 가 있습니다 | Outcome 5 | `api-unit`: `Tracer` 포트의 인메모리 구현으로 부모–자식 단언. `smoke`: `GET /runs/{id}` 의 `trace_id` 가 collector 의 file exporter 출력(`infra/docker/out/otel-smoke/spans.jsonl`, 개정 2·6)에 상한 30초 폴링 안에 나타남 |
| R-6 | 전부가 **fake 모델 어댑터로 네트워크 없이** 통과하고, OpenAI-호환 어댑터는 같은 포트 계약 테스트를 통과합니다 | Outcome 6, DP-4 | `api-unit` 은 `pytest-socket` 으로 **loopback 외 소켓을 차단**한 채 돕니다(`addopts` 의 `--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1` — `TestClient` 의 이벤트 루프가 `socketpair` 를 쓰므로 단독 차단은 불가. 개정 1). `integration` 은 `enable_socket`. OpenAI-호환 어댑터의 테스트는 `httpx.MockTransport`. 실제 로컬 LLM 서버 실행은 사람의 수동 확인(2.5) |
| R-7 | AR-5 와 AR-7 이 **실제 `.importlinter`** 로 발화합니다 | Outcome 6 | `tests/arch/test_real_importlinter_fires.py`: `apps/*/src`·`packages/*/src` 만 임시 디렉터리에 복사하고 그 경로들을 **`PYTHONPATH` 앞**에 넣어(editable 설치의 `.pth` 보다 앞 — 아니면 복사본이 아니라 실제 src 를 검사합니다) 실제 `.importlinter` 그대로 `aether_api/_bad.py`(`import httpx`, `import aether_runtime.application`)를 주입해 `lint-imports --no-cache` exit ≠ 0(개정 2). 더해 실제 파일의 contract 본문(`httpx` ∈ AR-5 forbidden, `aether_runtime.application` ∈ AR-7 forbidden)을 단언 |
| R-8 | 새 경로는 전부 인증 뒤에 있습니다. 인증 없는 요청은 401 | Outcome 8, DP-6 | `api-unit`: `app.routes` 를 순회해 예외 목록(`/healthz`, 문서 경로) 밖의 모든 `APIRoute` 에 헤더 없는 요청 → 401 |
| R-9 | `smoke` 가 `verify.sh` 에 집계되고, 로컬 verify 전체는 spec 0001 D-12 의 10분 안입니다 | Outcome 7 | `.harness/verify.json` 에 `smoke` 단계 `pass`, `duration_ms` 합계 ≤ 600,000, `smoke` 단독 ≤ 240,000. P1-9 에서 로컬·CI 실측 기록 |
| R-10 | `{{성능_기준}}` 의 값이 사람이 고정한 숫자로 evaluation/README 에 적힙니다 | Outcome 7, EI-2 | `scripts/smoke.sh --bench` 의 출력(2.13)을 근거로 사람이 값을 적음. 에이전트는 값을 정하지 않음 |
| R-11 | 테스트는 결정적입니다 — 시간·난수·모델은 주입, `sleep` 으로 기다리지 않습니다 | Constraints | `tests/arch/test_no_sleep_in_tests.py`: `apps/*/tests`, `packages/*/tests`, `tests/` 에 `time.sleep(`, `from time import sleep`, `asyncio.sleep(` 0건(허용 목록 없음). 기존 2곳(`apps/api/tests/test_api_key_store_contract.py`, `apps/worker/tests/test_connect.py`)은 P1-2 에서 시계 주입으로 제거 |
| R-12 | 계약이 구현보다 먼저입니다 — OpenAPI 와 이벤트 스키마가 커밋되어 있고 드리프트가 잡힙니다 | DP-1 | `test_openapi_drift`(기존) + `test_events_schema_drift`(신규): api 가 내보내는 이벤트 JSON Schema == 커밋된 `packages/sdk/events.schema.json`. `web-typecheck` 의 생성물 드리프트 검사가 `src/generated/events.d.ts` 도 덮음 |
| R-13 | worker 가 healthcheck 를 가집니다 — Redis 하트비트 키 | spec 0001 개정 8 이월 | compose 의 `worker` 가 `service_healthy`. `api-integration`: 하트비트 키 TTL 갱신 |
| R-14 | `Observation` 은 모델에 **신뢰 경계 밖 데이터**로 표시되어 들어갑니다 | intent Constraints, Trust | `api-unit`: 도구 결과가 fake 모델이 받은 요청에 `role: tool` + 표지로만 있고 system 메시지에 섞이지 않음 |
| R-15 | 한 Run 은 한 시점에 **하나의 worker 만** 실행합니다 | 리뷰 F-2 | `api-unit`: fake `RunStateStore` 에 살아 있는 lease 가 있을 때 두 번째 `ExecuteRun` 이 실행하지 않고 `LeaseHeld` 로 돌아옴. lease 만료 뒤에는 재개 |
| R-16 | 종결 알림은 **반드시 도달**합니다 — 커밋 뒤 발행 사이에 죽어도 재개가 재발행합니다 | 리뷰 F-1 | `api-unit`: 종결 커밋 뒤 `StatusNotifier` 가 실패하는 fake → 두 번째 `ExecuteRun(run_id)` 가 `run.status(종결)`·`run.finished` 를 다시 발행하고 ack |

## 2. 설계

### 2.1 배치 — `packages/runtime`, `apps/worker`, `apps/api`

배치 규칙은 [../docs/architecture.md](../docs/architecture.md) 3.1(AR-8 ~ AR-12) 그대로이고, 이 절은 그 자리에 **무엇이** 들어가는지만 정합니다.

**`packages/runtime`**

| 층 | 모듈 | 내용 |
| --- | --- | --- |
| `domain` | `agent.py` | `AgentDefinition`(pydantic, 2.3) |
| `domain` | `tools.py` | `BUILTIN_TOOL_NAMES = frozenset({"clock", "calculator"})`, `Tool` 의 값 타입(`ToolCall(id, name, arguments)`, `ToolResult(content, is_error)`). api 가 `definition.tools` 를 검증할 때 쓰는 유일한 근거 — 레지스트리(어댑터)를 알 필요가 없습니다 |
| `domain` | `run.py` | `RunStatus`(enum, 값은 `data.run_execution_status` 와 동일), `transition(from, to)` 전이표(2.4), `RunState`(메시지 목록, 단계 번호, `Task` 목록, 마지막 이벤트 `seq`), `IllegalTransition`, `LeaseHeld` |
| `domain` | `task.py` | `Task` — **모델 호출 1회**와 그에 딸린 도구 호출들. 단계마다 하나(2.6). span 트리의 `task` 와 1:1 |
| `domain` | `events.py` | Run 이벤트 모델(2.7). `v: 1` |
| `domain` | `observation.py` | `Observation(tool_call_id, tool, content, is_error, truncated, trust="untrusted")` |
| `domain` | `failure.py` | `FailureReason` 열거(2.8) |
| `application/ports/outbound` | `model_gateway.py` | `ModelGateway` — `complete`, `stream`, `embed`(2.5). `ModelResponse.tool_calls[].id` 와 `tool` 메시지의 `tool_call_id` 를 가집니다(OpenAI-호환 API 필수) |
| `application/ports/outbound` | `tools.py` | `ToolRegistry.get(name) -> Tool`, `Tool` Protocol(2.6) |
| `application/ports/outbound` | `run_state_store.py` | `RunStateStore` — `data.run_executions`(상태·lease)와 `data.run_states`(스냅숏) 계약: `load`, `save`, `acquire_lease(run_id, owner, until)`, `renew_lease`, `release` |
| `application/ports/outbound` | `run_declaration_reader.py` | `RunDeclarationReader` — `control.runs`(`input`, `agent_version_id`, `cancel_requested_at`)와 `control.agent_versions.definition` 읽기. `aether_data` 의 SELECT 권한이 그 실체 |
| `application/ports/outbound` | `event_sink.py` | `EventSink.publish(run_id, event)` |
| `application/ports/outbound` | `status_notifier.py` | `StatusNotifier.notify(StatusMessage)`(2.18) |
| `application/ports/outbound` | `tracer.py` | `Tracer.span(name, attributes) -> ContextManager`, `Tracer.current_trace_id()`. 유스케이스는 이 포트로만 span 을 만듭니다 — `opentelemetry` 는 어댑터에만(AR-9). 테스트용 인메모리 구현이 부모–자식을 기록 |
| `application/ports/outbound` | `lease_keeper.py` | `LeaseKeeper.keep(run_id, owner, ttl_seconds) -> ContextManager[LeaseStatus]`(`lost: bool`) — 모델·도구 호출 동안 lease 를 갱신(C-13, 개정 5). 프로덕션은 `adapters/outbound/threaded_lease_keeper.py` |
| `application/ports/outbound` | `clock.py` | `Clock.now()`, `Clock.monotonic()`, `Clock.sleep(seconds)`. 시간은 전부 여기를 지납니다(R-4, R-11) |
| `application/ports/inbound` | `execute_run.py` | `ExecuteRun.__call__(run_id) -> RunStatus` — worker 가 부르는 유일한 문 |
| `application/usecases` | `execute_run.py` | 2.4 의 lease·재개·재발행 규칙과 2.6 의 루프 |
| `adapters/outbound/model_gateway` | `fake.py`, `openai_compatible.py` | 2.5. `httpx` 는 여기에만(AR-5, 2.12) |
| `adapters/outbound/tools` | `clock_tool.py`, `calculator.py`, `registry.py` | 프로세스 내부 도구 둘과 인메모리 레지스트리 |
| `adapters/outbound/db` | `run_state_store.py`, `run_declaration_reader.py` | PostgreSQL 구현. `aether_data` 역할 |
| `adapters/outbound/redis` | `event_sink.py`, `status_notifier.py` | Redis Streams 구현 |
| `adapters/outbound/telemetry` | `otel_tracer.py` | `Tracer` 의 OpenTelemetry 구현. `TracerProvider` 를 주입받음(없으면 전역) — 개정 6 |

**`apps/worker`** — `aether_runtime` 을 조립합니다(`main.py`, AR-10).

| 층 | 모듈 | 내용 |
| --- | --- | --- |
| `application/ports/inbound` | `handle_run_requested.py` | `HandleRunRequested.__call__(message) -> None` |
| `application/usecases` | `handle_run_requested.py` | `traceparent` 복원 → runtime `ExecuteRun` 호출 → ack 여부 결정 |
| `adapters/inbound/stream` | `requested_consumer.py` | 기존 `stream.py` 의 후속. `count=1`, 재시작 시 **자기 PEL 먼저**(`XREADGROUP … 0`), 그 뒤 `XAUTOCLAIM`(2.4) |
| `adapters/outbound/redis` | `heartbeat.py` | 2.14 |
| `adapters/outbound` | `otel_trace_context.py` | `TraceContext` 의 OTel 구현 — `requested` 메시지의 `traceparent` 를 부모 컨텍스트로 복원(없거나 잘못되면 새 root). 개정 6 |

**`apps/api`** — 선언·조회·투영만. `aether_runtime.domain` **만** import 합니다(AR-7 확장, 2.12).

| 층 | 모듈 | 내용 |
| --- | --- | --- |
| `application/ports/inbound` | `agents.py`, `runs.py`, `apply_run_status.py`, `read_run_events.py` | 유스케이스 인터페이스: `CreateAgent`, `ListAgents`, `GetAgent`, `GetAgentVersion`, `UpdateAgent`, `RequestRun`, `GetRun`, `CancelRun`, `ApplyRunStatus`, `ReadRunEvents` |
| `application/ports/outbound` | `request_tracing.py` | `RequestTracing.span(name, attributes)`, `current_traceparent()` — `RequestRun` 이 `run.request` span 안에서 선언·통지. 구현은 `adapters/outbound/otel_request_tracing.py`(개정 6) |
| `application/ports/outbound` | `agent_repository.py`, `run_declaration_store.py`, `run_notifier.py`, `run_event_reader.py` | `AgentRepository`(`control.agents`·`agent_versions`, `FOR UPDATE` 포함), `RunDeclarationStore`(`control.runs` 삽입·투영 갱신·`cancel_requested_at`), `RunNotifier`(`aether:runs:requested` XADD), `RunEventReader`(Run 이벤트 스트림 읽기, 비동기) |
| `application/usecases` | 위 인터페이스마다 하나 | `ApplyRunStatus` 는 2.4 의 `seq` 멱등 규칙을 가집니다 |
| `adapters/inbound/http` | `agents.py`, `runs.py`, `events.py` | 라우터. 전부 `require_principal(app.state.authenticate)` 뒤. `events.py` 는 SSE(2.7) |
| `adapters/inbound/stream` | `status_consumer.py` | `aether:runs:status` 의 consumer group `aether-api` 소비자. lifespan 백그라운드 태스크에서 `ApplyRunStatus` 포트를 부름 |
| `adapters/outbound/db` | `agent_repository.py`, `run_declaration_store.py` | PostgreSQL. `aether_control` |
| `adapters/outbound/redis` | `run_notifier.py`, `run_event_reader.py` | Redis Streams. 리더는 `redis.asyncio` |
| `adapters/inbound/cli.py` | `events-schema` 서브커맨드 추가 | 2.7 |

### 2.2 HTTP 계약 (DP-1)

전 경로가 `Authorization: Bearer` 뒤에 있습니다(spec 0001 2.9, R-8). 오류 응답은 `{"detail": "<코드>"}` 이고, **예외는 FastAPI 의 요청 검증 422** — 그 `detail` 은 FastAPI 기본 형태(배열)를 그대로 둡니다(sdk 가 둘을 구분). OpenAPI 는 `packages/sdk/openapi.json` 에 커밋되고 구현이 그것을 만족합니다.

| 메서드·경로 | 요청 | 성공 응답 | 오류 |
| --- | --- | --- | --- |
| `POST /agents` | `{ name, definition }` | `201 { id, name, current_version: 1, created_at, updated_at }` | `409 agent_name_taken` · `422`(정의 검증) |
| `GET /agents` | `?limit=50&cursor=` | `200 { items: [{ id, name, current_version, updated_at }], next_cursor }` | — |
| `GET /agents/{id}` | — | `200 { id, name, current_version, definition, versions: [{ version, created_at }], created_at, updated_at }` | `404 agent_not_found` |
| `GET /agents/{id}/versions/{version}` | — | `200 { agent_id, version, definition, created_at }` | `404 agent_not_found` · `404 agent_version_not_found` |
| `PUT /agents/{id}` | `{ definition }` | `200`(`GET /agents/{id}` 와 같은 본문, `current_version` +1) | `404` · `409 agent_version_conflict`(동시 수정) · `422` |
| `POST /agents/{id}/run` | `{ input: string, agent_version?: int }` | `202 { run_id, agent_id, agent_version, status: "queued", requested_at, requested_by }` | `404 agent_not_found` · `404 agent_version_not_found` · `422` |
| `GET /runs/{id}` | — | `200 { run_id, agent_id, agent_version, status, requested_at, requested_by, started_at, finished_at, failure_reason, trace_id, cancel_requested_at }` | `404 run_not_found` |
| `POST /runs/{id}/cancel` | — | `202 { run_id, status, cancel_requested_at }` | `404 run_not_found` |
| `GET /runs/{id}/events` | 헤더 `Last-Event-ID` 선택 | `200 text/event-stream`(2.7) | `404 run_not_found` |

계약의 세부:

- **`PUT /agents/{id}`** 는 `definition` 만 바꿉니다. `name` 은 Phase 1 에서 **불변**입니다. 새 버전 번호는 같은 트랜잭션에서 `control.agents` 행을 `SELECT … FOR UPDATE` 로 잠근 뒤 `current_version + 1` 로 정하고 `agents.current_version`·`updated_at` 을 함께 갱신합니다 — 동시 요청은 직렬화되고, 그래도 unique 위반이 나면(잠금 밖 경로) `409 agent_version_conflict`. 이전 버전 행은 트리거가 불변을 보장합니다.
- **`POST /agents/{id}/run`** 은 `control.runs` 에 `input`, `agent_version_id`, `requested_by = principal.key_id`, `status = queued` 로 삽입하고 **커밋한 뒤** `aether:runs:requested` 에 XADD 합니다(2.18). XADD 가 실패하면 그래도 `202` 를 돌려주고 WARNING 을 남깁니다 — Run 은 `queued` 로 남아 관측 가능하고(C-2), 선언은 잃지 않습니다. 재시도 시 Run 이 중복 생성되는 것은 계약대로입니다 — 멱등키는 6절.
- **`POST /runs/{id}/cancel`** 은 멱등입니다. `control.runs.cancel_requested_at` 이 비어 있으면 지금 시각을 적고, 이미 있으면 그대로 둡니다. Run 이 이미 종결이면 현재 상태로 `202`. 취소를 실제로 반영하는 것은 worker(2.4) 이고 그 결과는 `GET`/이벤트로 봅니다.
- **`GET /runs/{id}`** 는 `control.runs` 의 투영 열만 읽습니다(spec 0001 D-11). 투영이 아직 도착하지 않았으면 `queued` 입니다.
- 삭제(`DELETE /agents/{id}`)와 `GET /runs` 목록은 없습니다(6절).

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
| `model.id` | 모델 식별자. `null` 이면 배포 설정 `AETHER_MODEL_ID` | 문자열 또는 `null`. 어댑터 종류(fake / OpenAI-호환)와 thinking 여부는 `definition` 이 아니라 **배포 설정**(2.15) — Agent 정의는 배포 환경과 무관해야 Cloud / On-Prem 을 같은 정의로 돕니다 |
| `tools` | 허용 도구 이름 | 문자열 배열, 중복 없음, 전부 `aether_runtime.domain.tools.BUILTIN_TOOL_NAMES` 안 — api 는 이 상수로만 검증합니다(레지스트리는 어댑터라 api 가 볼 수 없음). 밖의 이름은 422 |
| `policy.timeout_seconds` | Run 전체 상한. 넘으면 `timed_out` | 1 ~ 3600 |
| `policy.max_steps` | Model → Tool 루프의 최대 반복. 넘으면 `failed(max_steps_exceeded)` | 1 ~ 64 |
| `policy.model_retries`, `policy.tool_retries` | 호출 단위 재시도 횟수 | 0 ~ 10 |
| `policy.backoff` | 재시도 사이 지수 백오프. `Clock.sleep` 로 기다립니다 | `base_seconds` > 0, `max_seconds` ≥ `base_seconds` |

pydantic 모델 `AgentDefinition` 은 `aether_runtime.domain.agent` 에 있습니다(pydantic 은 AR-9 의 금지 목록에 없습니다 — 프레임워크가 아니라 데이터 검증 라이브러리이고 `Settings` 가 이미 씁니다). api 는 요청 본문을 이 모델로 검증한 뒤 `jsonb` 로 저장합니다. 이 모델의 JSON Schema 가 OpenAPI 에 그대로 실리므로 sdk 타입이 함께 생성됩니다. `schema_version` 을 올리는 것은 파괴적 변경 판정 대상입니다(DP-1).

### 2.4 Run 상태 기계, lease, 재개, 투영 (P1-2, P1-5)

**전이표.** 값은 `data.run_execution_status` 와 같고(spec 0001 2.8), 전이는 코드가 소유합니다.

| 에서 → 로 | 누가 | 언제 |
| --- | --- | --- |
| (없음) → `queued` | api | `POST /agents/{id}/run`. `control.runs.status` 의 초기값. `data.run_executions` 행은 worker 가 집을 때 `queued` 로 만듭니다 |
| `queued` → `running` | worker | lease 를 얻고 `cancel_requested_at` 이 비어 있음을 확인한 뒤 |
| `queued` → `cancelled` | worker | 집었을 때 `control.runs.cancel_requested_at` 이 이미 있음 |
| `running` → `waiting` | worker | 도구 호출 대기(Phase 1 의 도구는 즉시 돌아오지만 상태는 거칩니다 — Phase 2 MCP·Phase 4 HITL 이 이 상태를 씁니다) |
| `waiting` → `running` | worker | `Observation` 이 돌아옴 |
| `running` / `waiting` → `succeeded` | worker | 모델이 도구 호출 없이 최종 응답 |
| `running` / `waiting` → `failed` | worker | 재시도 소진, `max_steps` 초과, 정의 오류(2.8) |
| `running` / `waiting` → `cancelled` | worker | 단계 사이에서 `cancel_requested_at` 을 관측(협력적 — 진행 중인 모델 호출은 끝나기를 기다립니다) |
| `running` / `waiting` → `timed_out` | worker | `Clock.monotonic()` 기준 `policy.timeout_seconds` 초과 |

종결 상태에서 나가는 전이는 없습니다. 허용되지 않은 전이는 `IllegalTransition` 이고 `api-unit` 이 전이표 전체를 테스트합니다.

**취소의 정본은 `control.runs.cancel_requested_at` 하나입니다(D-11).** worker 는 단계 사이마다 `RunDeclarationReader` 로 그 열을 읽습니다(`aether_data` 의 SELECT 권한). 취소 스트림은 두지 않습니다 — consumer group 이면 다른 worker 가 먹고, 그룹이 없으면 last-id 관리가 생기는데, 단계 사이 SELECT 한 번이 같은 지연으로 같은 일을 합니다.

**lease(D-10, R-15).** `XAUTOCLAIM` 의 idle 은 "전달 뒤 경과" 이지 "활동 없음" 이 아니라, 1시간짜리 Run 을 살아 있는 worker 가 실행 중인데 다른 worker 가 가로챌 수 있습니다. 그래서 실행 권한은 메시지가 아니라 **`data.run_executions` 의 lease** 가 정합니다.

- `acquire_lease(run_id, owner, until = now + AETHER_WORKER_LEASE_SECONDS)` 는 `lease_until` 이 비었거나 지난 행만 잡습니다(조건부 UPDATE, 원자적). 잡지 못하면 `LeaseHeld` — 그 worker 는 메시지를 ack 하지 않고 지나갑니다(다음 `XAUTOCLAIM` 주기에 다시 봅니다).
- 단계마다 `renew_lease`. 종결 시 `release`.
- worker 는 재시작 시 **자기 PEL 을 먼저** 처리하고(`XREADGROUP … 0`), 그 뒤 `XAUTOCLAIM` 을 `min-idle ≥ 3600초(timeout 상한) + 300초` 로만 돕니다(`AETHER_WORKER_XAUTOCLAIM_MIN_IDLE_MS`, 기본 3,900,000 — 테스트는 0 을 주입해 가로채기 경로를 실행합니다). `count=1`. consumer 이름은 `AETHER_WORKER_CONSUMER`(기본 hostname)로 고정할 수 있습니다 — compose 재생성으로 hostname 이 바뀌면 자기 PEL 을 못 찾고 `XAUTOCLAIM` 만 남기 때문입니다.

**재개와 재발행(R-16).** `ExecuteRun(run_id)` 은 `data.run_executions` 의 현재 상태로 분기합니다.

| 현재 상태 | 동작 |
| --- | --- |
| 행 없음 | `queued` 행 생성 → lease → 실행 |
| `queued` | lease → 실행 |
| `running` / `waiting` (lease 만료) | 저장된 `RunState` 에서 이어감. 마지막 `seq` 다음부터 이벤트 발행 |
| `running` / `waiting` (lease 유효) | `LeaseHeld`. ack 하지 않음 |
| 종결 | **`run.status(종결)` 와 `run.finished` 를 다시 발행**한 뒤 ack. 커밋 뒤 발행 사이에 죽은 경우를 여기서 닫습니다 — 소비자는 `seq` 로 멱등이라 중복은 무해합니다 |

worker 는 실행이 끝나야 메시지를 ack 합니다(at-least-once, spec 0001 D-10). 종결 커밋 → status 알림 → 이벤트 `run.finished` → ack 순서이며, 어느 지점에서 죽어도 위 표가 수렴시킵니다.

**투영(열린 질문 2, D-2).** worker 는 전이마다 `aether:runs:status` 에 `StatusMessage`(2.18)를 보내고, **api 프로세스 안의 소비자**(`adapters/inbound/stream/status_consumer.py`, consumer group `aether-api`, consumer 이름 `hostname-pid`, lifespan 백그라운드)가 `ApplyRunStatus` 를 부릅니다. 멱등의 근거는 전이표가 아니라 **Run 단위 `seq`** 입니다 — `running ↔ waiting` 이 양방향 합법이라 전이표로는 중복·역행을 걸러내지 못합니다. `control.runs.status_seq` 에 마지막 적용 `seq` 를 두고, `seq > status_seq` 인 메시지만 적용합니다. 적용은 한 UPDATE(`WHERE id = %s AND (status_seq IS NULL OR status_seq < %s)`), DB 커밋 뒤 ack. 별도 프로세스를 두지 않는 이유: Phase 1 의 api 인스턴스는 하나이고, 늘어나면 consumer group 이 소비자 수를 흡수합니다. api 가 내려가 있는 동안의 메시지는 스트림에 남아 다음 기동 때 소비됩니다.

### 2.5 Model gateway (P1-3, 열린 질문 1 · Q6)

| 항목 | 결정 |
| --- | --- |
| 인터페이스 | `ModelGateway` — `complete(request: ModelRequest) -> ModelResponse`, `stream(request) -> Iterator[ModelDelta]`, `embed(texts) -> list[list[float]]`. `ModelRequest` 는 메시지 목록(`system` / `user` / `assistant` / `tool(tool_call_id)`)과 도구 스키마 목록, `ModelResponse` 는 `text`, `tool_calls: [{ id, name, arguments }]`, `reasoning: str | None`, `finish_reason` |
| 어댑터 1 | `FakeModelGateway` — 시나리오 주입(스크립트된 응답 열). 도구를 부르는·부르지 않는·실패하는·`reasoning` 을 내는 시나리오. 전 테스트와 `smoke` 의 기본 |
| 어댑터 2 | `OpenAICompatibleGateway(base_url, model_id, api_key?, thinking: bool)` — `/v1/chat/completions`(`stream: true` 포함)와 `/v1/embeddings`. **`httpx` 직접 호출, 벤더 SDK 없음** |
| thinking(D-19) | Qwen3.8 계열은 기본이 thinking 이라 응답에 `reasoning_content`(또는 `<think>` 블록)가 옵니다. 어댑터는 그것을 `ModelResponse.reasoning` 으로 **분리**하고 `text` 에는 넣지 않습니다. `AETHER_MODEL_THINKING=false`(기본) 이면 요청에 서버의 thinking 비활성 옵션(Ollama `think: false`)을 보냅니다. `reasoning` 은 로그·span·이벤트에 넣지 않습니다(용량·비밀) |
| 선택 | 배포 설정(2.15). `AETHER_MODEL_ADAPTER=fake` 가 기본 |
| **로컬 LLM 서버(Q6, D-1)** | **Ollama.** 근거: 개발자 머신(Windows + Docker Desktop, Linux, macOS)에서 27B 양자화(GGUF)를 가장 적은 준비로 내고, `/v1/chat/completions` OpenAI-호환 API 가 있으며, 모델 pull 뒤에는 오프라인입니다. vLLM 은 Linux + NVIDIA 와 AWQ/GPTQ 전제라 개발 기본으로 무겁고, 서버 부하 시나리오가 오는 Phase 에 재판정합니다. compose 에는 `llm` 프로파일(`profiles: ["llm"]`)로 두어 기본 `up` 과 `probe`(spec 0001 R-4)에 영향이 없습니다 |
| **기본 테스트 모델** | intent Q6 의 결정 그대로 **Qwen3.8 27B 양자화**. Ollama 태그 **`qwen3.8:27b`**(2026-09-12 확인: 존재, 약 18 GB, 256K 컨텍스트, vision·tools·thinking). `.env.example` 의 `AETHER_MODEL_ID` 기본값은 이 태그이고 사람이 P1-3 에서 한 번 더 확인합니다. 태그가 사라지면 같은 계열의 최근접 모델을 **사람이** 골라 `.env.example` 과 `improvement-log/` 에 적습니다. VRAM 은 약 18 GB 이상(추정) — 없는 머신은 fake 어댑터만 씁니다. 이 모델은 판정(R-6)의 대상이 아니라 사람의 수동 확인 대상입니다 |
| 계약 테스트 | fake 와 OpenAI-호환 어댑터가 같은 포트 계약 테스트를 통과합니다. OpenAI-호환 쪽은 `httpx.MockTransport`(R-6). 항목: 도구 호출 응답의 `tool_calls[].id` 보존, `tool` 메시지의 `tool_call_id` 전송, **tools + stream 동시** 요청의 청크 파싱, `reasoning_content` 분리, `think: false` 옵션 전송, 5xx·타임아웃 → `ModelError` |

`embed` 는 Phase 1 의 루프가 쓰지 않지만 인터페이스에 둡니다(backlog P1-3 범위). 구현은 두 어댑터 모두, 소비자는 Phase 3.

### 2.6 Planner/Executor 루프와 도구 (P1-4, 열린 질문 5)

루프는 `ExecuteRun` 유스케이스 하나이고, Phase 1 은 `complete` 만 씁니다(`stream` 은 어댑터에 있으되 루프가 부르지 않습니다 — 2.7 의 `model.delta` 는 Phase 1 에 발생하지 않습니다).

```text
RunState 로드(없으면 초기화: system_prompt + user input)
반복 (단계 ≤ max_steps, 시계 ≤ timeout):
  cancel_requested_at 관측 → cancelled
  Task 생성(단계마다 하나), span task
  running: ModelGateway.complete(messages, tools) [재시도: model_retries] (span model.complete)
  응답에 tool_calls 없음 → 최종 응답 저장 → succeeded
  tool_calls 있음 → waiting
    각 호출: ToolRegistry.get(name).run(arguments) [재시도: tool_retries] (span tool.run) → Observation(tool_call_id)
    messages += role=tool, tool_call_id, 표지 → running
  RunState 저장(seq 포함), 이벤트 publish, lease 갱신
```

**도구 인터페이스(D-5).** 지금부터 MCP tool 과 같은 모양입니다: `Tool.name`, `Tool.description`, `Tool.input_schema`(JSON Schema object), `Tool.run(arguments: dict) -> ToolResult(content: str, is_error: bool)`. Phase 2 는 `ToolRegistry` 의 구현을 MCP 클라이언트로 바꾸고 유스케이스는 바뀌지 않습니다.

Phase 1 의 도구 둘 — `clock`(현재 시각, `Clock` 포트를 통해 얻으므로 결정적)과 `calculator`(사칙연산과 괄호만 받는 파서. `eval` 을 쓰지 않습니다). 이름은 `BUILTIN_TOOL_NAMES`(2.1) 와 같아야 하고 그것을 단언하는 테스트가 있습니다.

**`Observation` 의 신뢰 경계(R-14).** 도구 결과는 `Observation(trust="untrusted")` 로만 루프에 들어오고, 모델 요청에서는 `role: tool` 메시지로만 나타납니다. system·user 메시지에 이어 붙이지 않습니다. 내용 앞뒤에 표지(`[observation tool=… trust=untrusted]` … `[/observation]`)를 붙입니다 — 완전한 방어는 아니지만 경계가 코드에 있어야 Phase 2 의 MCP Firewall 이 그 지점에 걸립니다. 크기는 `AETHER_OBSERVATION_MAX_CHARS`(기본 16,000)로 잘라 `truncated: true` 를 표시합니다.

### 2.7 Streaming (P1-6, 열린 질문 4)

| 항목 | 결정 |
| --- | --- |
| 전송 | worker 가 Run 마다 Redis Stream `aether:runs:{run_id}:events` 에 `XADD` — **explicit ID `<seq>-0`**(`seq` 는 Run 안에서 1 부터 단조 증가). `MAXLEN ~ 10000`, 종결 뒤 TTL 24시간. api 의 `GET /runs/{id}/events` 는 그 스트림을 **`redis.asyncio` 의 블록 `XREAD`** 로 읽어 SSE 로 내보냅니다(consumer group 없음 — 독자가 여럿). 동기 클라이언트로 스레드풀을 점유하지 않습니다 — 클라이언트 단절 시 읽기를 취소할 수 있어야 R-3 이 성립합니다. **같은 `seq` 의 재발행(2.4 의 재개)은 성공으로 취급**합니다 — Redis 는 top ID 이하의 explicit `XADD` 를 `ERR The ID specified in XADD is equal or smaller` 로 거부하므로 `EventSink` 어댑터가 그 오류를 흡수하고, fake 도 계약대로 성공합니다(개정 2) |
| SSE 필드 | `id: <seq>`, `event: <type>`, `data: <JSON>` |
| `data` 봉투 | `{ "v": 1, "run_id", "seq", "at", "type", "payload" }` |
| 이벤트 종류 | `run.status { status, failure_reason? }` · `task.started { task_id, step }` · `task.finished { task_id }` · `model.completed { finish_reason, usage? }` · `tool.called { task_id, tool_call_id, name, arguments }` · `tool.result { task_id, tool_call_id, name, is_error, content, truncated }` · `run.finished { status }`(항상 마지막) · `model.delta { text }`(**예약**. Phase 1 은 발생시키지 않습니다) |
| 순서 | `seq` 순. `run.status` 의 순서가 2.4 의 전이 순서와 같습니다(R-3) |
| `Last-Event-ID` | 값 `n` 을 받으면 스트림 ID `n-0` 다음부터 읽습니다 — explicit ID 덕에 매핑이 직접입니다. `MAXLEN` 으로 잘려 나간 구간은 건너뛰어집니다(보장 안 함, 6절) |
| 스트림이 없을 때 | `control.runs` 가 종결이면 `run.finished { status }` 하나를 **합성**해 보내고 닫습니다(TTL 뒤 늦게 온 독자, 또는 발행 전 crash — 2.4 의 재발행이 곧 채우지만 기다리지 않습니다). 종결이 아니면 스트림이 생길 때까지 블록(`XREAD BLOCK` 은 없는 키에도 동작) |
| 종료 | `run.finished` 를 보낸 뒤 서버가 닫습니다. 클라이언트 단절은 api 의 읽기 취소로 끝나고 worker 는 api 를 모릅니다(AR-7) |
| 스키마 소유 | 이벤트 모델은 `aether_runtime.domain.events`. `aether-api events-schema` 가 pydantic JSON Schema 를 내보내 `packages/sdk/events.schema.json` 에 커밋하고, `pnpm -F sdk run generate` 가 `json-schema-to-typescript` 로 `src/generated/events.d.ts` 를 만듭니다. 드리프트는 R-12 |

이벤트는 Phase 1 에서 **영속되지 않습니다**(Redis TTL). Run 의 결과는 `data.run_states` 의 최종 `RunState` 에 있습니다.

### 2.8 Retry / Timeout / Error Handling (P1-7)

| 항목 | 결정 |
| --- | --- |
| 타임아웃 | 기준은 **저장된 `started_at` 과 `Clock.now()`** — `deadline = started_at + policy.timeout_seconds`, 잔여 = `deadline - now`. `Clock.monotonic()` 은 재개(R-16)를 넘어 보존되지 않아 쓰지 않습니다(개정 5). 검사 지점은 셋 — 매 단계 시작(취소 확인 직후), 모델·도구 호출 직전, 재시도 백오프 직전(잔여가 지연 이하면 기다리지 않음). 잔여 ≤ 0 → `timed_out`(`failure_reason` 없음). 모델 호출에는 잔여를 `ModelRequest.timeout_seconds` 로 넘기고, 그 호출이 `timeout` 으로 끝났는데 잔여 ≤ 0 이면 재시도하지 않고 `timed_out` |
| 재시도 | 모델: 총 시도 `model_retries + 1`. **재시도 가능한 오류**는 `kind` 가 `timeout`·`protocol` 이거나 `http` 이면서 `status ≥ 500` 또는 `429`. 그 밖의 `http` 4xx 는 재시도 없이 즉시 `failed(model_error)`. 도구: `Tool.run` 이 **예외**를 던질 때만 재시도(총 `tool_retries + 1`) — `ToolResult(is_error=True)` 는 재시도 대상이 아니라 정상 `Observation` 으로 모델에 돌아갑니다. 백오프: n 번째 재시도 전 `min(base_seconds · 2^(n-1), max_seconds)`, 지터 없음, `Clock.sleep` 으로 — `FakeClock` 은 즉시 전진(R-11) |
| lease 유지 | 모델·도구 호출은 `LeaseKeeper.keep(...)` 로 감쌉니다. 그 동안 갱신이 실패하면(`False` 또는 예외) `lost` — 호출이 끝난 뒤 그 단계는 **저장·발행·release 없이** `LeaseHeld` 로 물러납니다. 단계 끝 `renew_lease` 는 저장 **전**에 부르고 `False` 도 같은 처리. 새 소유자는 마지막 저장 스냅숏에서 이어가며 같은 `seq` 재발행은 `EventSink` 가 흡수합니다(C-13, 개정 5) |
| 사유 | `FailureReason`: `model_error`, `tool_error`, `max_steps_exceeded`, `unknown_tool`(정의가 레지스트리에 없는 도구를 요구 — api 검증을 지나쳐도 worker 가 막음), `definition_invalid`, `internal`. `data.run_executions.failure_reason`, `control.runs.failure_reason`(투영), `run.status` 이벤트의 `failure_reason` 에 같은 문자열 |
| 사람 개입 | 없음. HITL 은 Phase 4 |

### 2.9 Trace (P1-8, 열린 질문 6)

| 항목 | 결정 |
| --- | --- |
| span 트리 | `run` → `task` → `model.complete` / `tool.run`. 유스케이스는 `Tracer` 포트로만 만듭니다(AR-9). 속성: `aether.run_id`, `aether.agent_version_id`, `aether.task_id`, `aether.tool.name`, `aether.model.id`. 프롬프트·응답·`reasoning` 본문은 속성에 넣지 않습니다 |
| 전파 | api 의 `POST /agents/{id}/run` span 이 `traceparent` 를 `requested` 메시지 필드에 넣고(2.18), worker 가 부모로 삼습니다 — 한 Run 이 한 trace. `trace_id` 는 worker 가 `data.run_executions.trace_id` 에 쓰고 `StatusMessage` 에 실어 `control.runs.trace_id` 로 투영 |
| collector(D-7) | compose 에 `otel-collector`(`otel/opentelemetry-collector-contrib`, digest 고정)를 **기본 서비스**로. 수신 OTLP/HTTP 4318, exporter 는 `debug` 와 `file`. 파일은 **호스트 bind mount** `infra/docker/out/otel/spans.jsonl`(`AETHER_OTEL_DIR`, gitignore. `.harness/*` 는 가드 보호 패턴이라 피합니다 — 개정 2. 이미지에 셸이 없어 `exec cat` 이 불가하고 `docker cp` 보다 단순). Linux CI 에서는 없는 디렉터리를 Docker 가 root 소유로 만들어 uid 10001 의 collector 가 쓰지 못하므로 `smoke.sh` 가 `mkdir -p && chmod 0777` 을 먼저 합니다. `smoke` 는 그 파일을 상한 30초로 폴링합니다 — `BatchSpanProcessor` 의 기본 지연이 있어 즉시 나타나지 않습니다 |
| 테스트 | `api-unit` 은 인메모리 `Tracer` 로 부모–자식. collector 는 `smoke` 에서만 |

### 2.10 데이터 모델 변경 (마이그레이션 0002)

[../docs/data-model.md](../docs/data-model.md) 를 P1-1·P1-2·P1-5 가 갱신합니다. 여기는 경계와 제약만입니다.

| 대상 | 변경 | 누가 쓰는가 |
| --- | --- | --- |
| `control.agents` | `current_version` integer NOT NULL 기본 1 — `PUT` 의 직렬화 잠금 대상이자 조회의 정본(매 조회 집계를 피함) | api |
| `control.runs` | 투영·선언 열 추가 — `input` text NOT NULL, `status` text NOT NULL 기본 `queued`, `status_seq` integer nullable, `started_at`, `finished_at`, `failure_reason`, `trace_id`, `cancel_requested_at`(nullable) | api(`aether_control`) 만 씁니다. worker 는 SELECT(기존 권한) |
| `data.run_executions` | `lease_owner` text nullable, `lease_until` timestamptz nullable 추가. 나머지 변경 없음 — `started_at`/`finished_at` nullable 은 개정 7 대로 |
| `data.run_states` | 신설 — `run_id` uuid PK·FK → `control.runs`, `state` jsonb NOT NULL, `updated_at` | worker(`aether_data`) |
| GRANT | `aether_data` 에 `data.run_states` 전부. 기존 권한 변경 없음 — `aether_control` 은 여전히 `data` 에 권한 없음(spec 0001 R-7 유지) | 마이그레이션 |

`control.runs.status` 는 text 로 두고 enum 을 만들지 않습니다 — 투영이지 정본이 아닙니다. cross-schema FK 가 하나 더 늘어납니다(`data.run_states.run_id`) — spec 0001 C-8 의 soft reference 전환 대상에 추가하고 `docs/data-model.md` 4절에 적습니다.

### 2.11 검증 단계 — `smoke` 와 D-7 (P1-9, 열린 질문 8)

**`scripts/smoke.sh`**(에이전트가 만듦). 개발자의 compose 스택과 **격리**됩니다.

| 단계 | 내용 |
| --- | --- |
| 격리 | compose 프로젝트 `-p aether-smoke`. `infra/docker/.env` 를 쓰지 않고 **임시 `.env`** 를 생성해 `--env-file` 로 넘깁니다 — 값은 랜덤(`openssl rand -hex 24`)이고 실행 뒤 지웁니다. 비밀값이 아니라 일회용 시험값이지만 어디에도 커밋·출력하지 않습니다. CI 에 `.env` 가 없어도 뜹니다. 오버라이드 `infra/docker/compose.smoke.yaml` 이 api 의 호스트 포트를 비우고(`ports: !reset []`) collector 출력을 `./out/otel-smoke` 로 돌려 개발 스택과 겹치지 않습니다(개정 7) |
| 기동 | `docker compose -p aether-smoke --env-file <tmp> -f infra/docker/compose.yaml [-f infra/docker/compose.ci.yaml] up --build -d --wait postgres redis migrate otel-collector api worker` — web 은 띄우지 않습니다. `--wait` 와 일회성 `migrate`(`service_completed_successfully`)의 조합은 compose 버전에 따라 실패 사례가 있어 **P1-9 착수 전 확인 항목**입니다(C-12). 실패하면 `up -d` 뒤 `migrate` 종료 코드와 healthcheck 를 스크립트가 직접 기다립니다 |
| 시나리오 | `docker compose exec -T api aether-api keys create --label smoke`(원문은 변수로만) → **api 컨테이너 안에서** `scripts/smoke_client.py scenario`(stdin 으로 넘김 — 호스트 포트·curl·jq 불필요, 개정 7): `POST /agents` → `POST /agents/{id}/run` → `GET /runs/{id}` 가 `succeeded` 가 될 때까지 상한 60초 폴링 → `trace_id` 가 `infra/docker/out/otel-smoke/spans.jsonl`(smoke 전용 디렉터리 — 개발 스택과 공유하지 않음) 에 나타날 때까지 상한 30초 폴링 |
| 종료 | 항상 `down -v --remove-orphans`(trap). 임시 `.env` 삭제. Windows Git Bash 는 `MSYS_NO_PATHCONV=1`, `exec -T` |
| 모델 | `AETHER_MODEL_ADAPTER=fake`(compose 기본값) |
| `--bench` | 2.13 |

**단계 수(D-15).** spec 0001 D-7 은 제품 단계를 **10개까지**로 확정했고 P0-7 이 그 10개를 다 썼습니다.

| 선택 | 무엇 | 대가 |
| --- | --- | --- |
| (a) 접기 | `smoke` 를 `api-integration` 안의 pytest 로 | `api-integration` 이 이미지 빌드까지 포함해 수 분짜리 단계가 되고, 통합 실패와 e2e 실패가 한 로그에 섞여 원인 분리가 나빠집니다. `behavior` 계층은 self-check 의 `protection` 하나만 남습니다 |
| (b) 별도 단계 | `smoke\|behavior\|true\|scripts/smoke.sh` 를 11번째 제품 단계로. spec 0001 D-7 을 [실질] 개정 — "정확히 10개" → "11개(`smoke` 포함), 총 17" | 상한의 출처(harness-adoption.md 3.3)를 한 번 더 넘습니다. 사람의 결정이고 `improvement-log/` 에 1건 |
| (c) 합치기 | 싼 단계 둘을 하나로(예: `web-lint` + `web-arch` → `web-static`) 하고 `smoke` 를 넣어 10 유지 | **기각.** 합친 단계는 실패 시 어느 검사가 깨졌는지 로그를 열어야 알고, `architecture` 계층 점수에서 `web-arch` 가 사라져 AR-1 의 판정이 `quality` 로 섞입니다. 상한 숫자를 지키기 위해 계층 구분을 흐리는 것은 상한의 취지(반복을 죽이지 않기)와 무관한 대가입니다 |

**실측(P1-9, 2026-09-16)**: 로컬 17단계 163.4초(smoke 39.7초), CI `verify` job 약 3분. 회귀 조건 전부 충족 — (a) 로 돌아갈 이유가 없습니다(개정 8).

**이 spec 은 (b) 를 채택합니다(D-15).** 상한의 취지는 **시간** 예산이고 그것은 D-12(10분)가 지킵니다. 시간을 지키는 장치는 셋 — `smoke` 는 web 을 띄우지 않음, 이미지 레이어 캐시, 그리고 **숫자로 된 회귀 조건**: `smoke` 단독 ≤ 4분(로컬), CI `verify` job 전체 ≤ 8분. P1-9 가 실측하고, 넘으면 (a) 로 돌아갑니다 — 그 판정도 사람이 합니다.

**CI 빌드 캐시.** compose 파일의 `cache_from` 한 줄로는 되지 않습니다. CI 는 `docker/setup-buildx-action` 뒤 **`docker buildx bake -f infra/docker/compose.yaml -f infra/docker/compose.ci.yaml --set '*.cache-from=type=gha' --set '*.cache-to=type=gha,mode=max' --load`** 로 **`api`·`worker` 두 target 만** 이미지를 먼저 만들고(`docker/bake-action@v6` 이 런타임 토큰 노출을 대신합니다. bake 는 compose 의 상대 빌드 컨텍스트를 실행 위치 기준으로 해석하므로 `source: .` + `workdir: infra/docker` + `files: compose.yaml, compose.ci.yaml` — 개정 7. target 을 주지 않으면 `web`·`migrate` 까지 빌드해 8분 조건을 위협합니다), `smoke.sh` 는 `SMOKE_NO_BUILD=1` 이면 `-f compose.ci.yaml` 을 더해 `--no-build` 로 그 이미지를 씁니다. `compose.ci.yaml` 은 `api`·`migrate` 에 같은 `image:`, `worker` 에 `image:`, `pull_policy: never` 를 주며 로컬 `docker compose build` 에 영향이 없습니다(개정 2). 이 절차는 실재를 확인했습니다(bake 의 `type=gha`). `harness.yml` 변경은 보호 파일이라 사람(C-9).

`harness.config` 의 배열 원소는 큰따옴표 문자열이라 명령 안의 따옴표는 작은따옴표입니다(spec 0001 2.11). 후보 파일은 `bash -c` 로 **실제 실행**해 검증합니다(improvement-log `2026-09-11-014`).

### 2.12 아키텍처 규칙의 변경 (보호 파일 `.importlinter`, 사람)

| 규칙 | 변경 | 왜 지금 |
| --- | --- | --- |
| AR-5 | `forbidden_modules` 에 `httpx` 추가, `ignore_imports` 에 `aether_runtime.adapters.outbound.model_gateway.** -> httpx`. `unmatched_ignore_imports_alerting` 을 `warn` → `error` | OpenAI-호환 어댑터가 SDK 대신 `httpx` 를 쓰므로 "LLM 호출은 gateway 한 곳" 이 `httpx` 에도 걸려야 합니다. 어댑터가 생기면 ignore 가 매칭되어 `error` 가 맞습니다. 이것이 spec 0001 C-6("HTTP 로 Data Plane 을 부르지 않는다" 를 정적 도구가 못 잡음)의 Phase 1 답입니다 — api 의 outbound HTTP 는 0 이고 `httpx` 자체가 금지됩니다 |
| AR-7 | `aether_api` → `aether_runtime.application`, `aether_runtime.adapters` 금지 추가(`aether_runtime.domain` 만 허용) | 2.1. Control Plane 은 타입만 알고 실행을 모릅니다. backlog P1-1 의 "`apps/api` 가 `packages/runtime` 의 내부 모듈을 import 하지 않음" 은 이 뜻으로 [편집] |
| AR-10 | **구조 테스트로 승격** — `tests/arch/test_composition_only_in_main.py`: `adapters.inbound` 와 `adapters.outbound` 를 함께 import 하는 모듈은 `apps/*/main.py` 만 | `.importlinter` 로는 "main 만 예외" 를 표현하기 어렵고, AST 검사 하나로 충분합니다 |

**R-7 의 판정 방식.** 기존 `tests/arch` 는 fixture 전용 설정으로 돌아 "fixture 의 규칙이 동작한다" 만 증명합니다. Phase 1 은 **실제 `.importlinter`** 를 돌립니다: `apps/*/src`·`packages/*/src`·`.importlinter` 를 임시 디렉터리에 복사하고(통째 복사는 `node_modules`·`.next` 를 끌고 옵니다), 복사된 9개 `src` 경로를 **`PYTHONPATH` 앞**에 넣어 editable 설치보다 먼저 잡히게 한 뒤 `aether_api/_bad.py` 에 위반 import 를 주입하고 `lint-imports --config <임시>/.importlinter --no-cache` 로 exit ≠ 0 을 단언합니다(개정 2). 정상 트리에서는 exit 0. 이 테스트는 `api-unit` 안에서 돕니다(수 초).

Phase 2 의 MCP HTTP 전송이 `httpx` 를 쓰면 AR-5 ignore 에 `aether_mcp.adapters.outbound.**` 를 더하는 것은 그때의 spec 이 정합니다.

### 2.13 `{{성능_기준}}` 의 측정 정의 (열린 질문 7)

| 항목 | 정의 |
| --- | --- |
| 지표 | `POST /agents/{id}/run` 의 응답 지연 **P95**(요청 전송 → 202 수신). Run 의 실행 시간이 아닙니다 |
| 절차 | `scripts/smoke.sh --bench`: smoke 와 같은 격리 compose 위에서 같은 Agent 에 **순차** 200회, 처음 20회 워밍업 제외, 180회의 P50·P95·max(nearest-rank)를 `infra/docker/out/smoke-bench.json` 에 기록. 요청은 api 컨테이너 안에서 `localhost:8000` 으로 보냅니다 — 호스트·Docker 네트워크 왕복은 포함하지 않습니다(개정 7) |
| 환경 | 머신(OS, CPU, Docker), 어댑터(`fake`), 커밋 해시를 함께. 기준값에는 환경 이름이 붙습니다 |
| 값 | **사람이** P1-9 에서 실측을 보고 `evaluation/README.md` 에 적습니다(EI-2) |

### 2.14 worker healthcheck (spec 0001 개정 8 이월)

worker 는 `AETHER_WORKER_HEARTBEAT_SECONDS`(기본 5)마다 Redis 키 `aether:worker:{consumer}:heartbeat` 를 TTL 3배로 `SET` 합니다. compose 의 healthcheck 는 `python -c` 한 줄로 그 키를 확인합니다(이미지에 `redis-cli` 없음). `worker` 도 `service_healthy` 가 되고 `smoke` 의 `--wait` 가 그것을 기다립니다.

### 2.15 설정 (추가·변경되는 환경변수)

| 변수 | 앱 | 기본값 | 뜻 |
| --- | --- | --- | --- |
| `AETHER_DATABASE_URL` | **worker** | (compose: `aether_data` URL) | worker 가 처음으로 DB 를 씁니다 — `data.run_executions`·`data.run_states` 쓰기, `control.runs`·`agent_versions` 읽기. api 의 같은 이름 변수(`aether_control`)와 **역할이 다릅니다**. `.env.example` 과 compose 갱신 |
| `AETHER_REDIS_URL` | **api** | `redis://localhost:6379/0` | api 가 처음으로 Redis 를 씁니다(통지·투영·이벤트 읽기) |
| `AETHER_MODEL_ADAPTER` | worker | `fake` | `fake` / `openai_compatible` |
| `AETHER_MODEL_BASE_URL` | worker | (없음) | compose `llm` 프로파일에서 `http://llm:11434/v1` |
| `AETHER_MODEL_ID` | worker | `qwen3.8:27b` | `definition.model.id` 가 `null` 일 때 |
| `AETHER_MODEL_API_KEY` | worker | (없음) | 선택. 비밀값 — `.env.example` 은 `<optional>` |
| `AETHER_MODEL_THINKING` | worker | `false` | 2.5 |
| `AETHER_OBSERVATION_MAX_CHARS` | worker | `16000` | 2.6 |
| `AETHER_EVENTS_MAXLEN` / `AETHER_EVENTS_TTL_SECONDS` | worker | `10000` / `86400` | 2.7 |
| `AETHER_WORKER_LEASE_SECONDS` | worker | `60` | 2.4. 단계마다 갱신 |
| `AETHER_WORKER_CONSUMER` | worker | hostname | 2.4 |
| `AETHER_WORKER_XAUTOCLAIM_MIN_IDLE_MS` | worker | `3900000` | 2.4. 테스트는 0 |
| `AETHER_WORKER_HEARTBEAT_SECONDS` | worker | `5` | 2.14 |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | api, worker | (없음) | compose 에서 `http://otel-collector:4318`. 없으면 no-op |

### 2.16 의존성과 테스트 도구 설정

| 대상 | 추가 | 단위 |
| --- | --- | --- |
| `packages/runtime/pyproject.toml` | `pydantic`, `httpx`, `redis`, `psycopg[binary]`, `opentelemetry-sdk`(어댑터용) | P1-2a(pydantic·psycopg·redis), P1-3(httpx), P1-8(otel) |
| `apps/api/pyproject.toml` | `redis`, `aether-runtime`(workspace) | P1-1 |
| `apps/worker/pyproject.toml` | `psycopg[binary]`, `aether-runtime`(workspace) | P1-5a |
| 루트 dev 그룹 | `pytest-socket`(R-6) | P1-2a |
| `packages/sdk/package.json` | `json-schema-to-typescript`(devDependency) | P1-6 |
| `uv.lock`, `pnpm-lock.yaml` | 위와 함께 갱신 — Dockerfile 이 `--frozen` 이라 lock 이 빠지면 이미지 빌드가 실패합니다 | 각 단위 |

**테스트 모듈 이름(D-18).** `packages/runtime/tests` 에 `conftest.py`·`fakes.py` 가 생기면 루트 mypy(`files = ["apps", "packages", "tests"]`)가 `apps/api/tests` 의 같은 이름과 "Duplicate module named" 로 실패합니다(지금은 api 한 곳뿐이라 통과). P1-2a 가 `pyproject.toml`(보호 파일 아님)에 `[tool.mypy] explicit_package_bases = true` 와 **`mypy_path` 에 9개 `src` 경로**(없으면 `apps/api/src/aether_api` 가 `apps.api.src.aether_api` 로 잡혀 설치된 이름과 갈라집니다), `[tool.pytest.ini_options] pythonpath = ["."]` 를 넣고, 테스트는 헬퍼를 **네임스페이스 경로**로 import 합니다(`from apps.api.tests.fakes import …`). `--import-mode=importlib` 는 쓰지 않습니다 — `sys.path` 를 바꾸지 않아 기존 `from fakes import …` 가 깨지고, 기본 모드에서 basename 이 겹치면 다른 앱의 fake 를 import 합니다(둘 다 실험 확인, 개정 1). 네임스페이스 import 뒤에는 헬퍼(`fakes.py` 류) basename 이 겹쳐도 됩니다. 단 **테스트 파일**(`test_*.py`)의 basename 은 저장소 전체에서 유일해야 합니다 — pytest 의 기본 import 는 `__init__.py` 없는 디렉터리의 테스트 모듈을 basename 으로 `sys.modules` 에 올려 같은 이름이 두 번 나오면 import 불일치 오류가 납니다(P1-5a 실측, 개정 4). 앱 이름을 접두로 붙입니다(`test_worker_settings.py`).

**기다림과 공용 fixture(R-3, R-11).** PostgreSQL 세션 fixture(컨테이너·역할·`alembic upgrade`·접속 팩토리)는 `tests/support/pg.py` 로 올려 `apps/api`·`apps/worker`·`packages/runtime` 의 테스트가 함께 씁니다(개정 2). 등록은 **루트 `conftest.py` 의 `pytest_plugins = ["tests.support.pg"]` 한 곳** — pytest 9 는 top-level 이 아닌 conftest 의 `pytest_plugins` 를 거부하므로 `apps/api/tests/conftest.py` 는 없어졌습니다(개정 3). fixture 는 요청될 때만 실행되어 전역 등록이 다른 테스트에 부작용을 주지 않습니다. 통합 테스트가 비동기 결과를 기다릴 때는 `tests/support/waiting.py` 의 `wait_until(predicate, timeout, interval)` 하나만 씁니다 — 내부는 `threading.Event.wait(interval)` 로 폴링합니다(`time.sleep` 아님). 단위 테스트는 기다리지 않습니다(전부 주입).

### 2.17 `packages/sdk` (spec 0001 D-2 유지)

타입은 생성(`openapi.json` → `src/generated/openapi.d.ts`, `events.schema.json` → `src/generated/events.d.ts`), 호출은 수기입니다. `createClient({ baseUrl, apiKey, fetch? })` 에 함수를 더합니다.

| 함수 | 경로 |
| --- | --- |
| `createAgent(body)`, `listAgents({ limit, cursor })`, `getAgent(id)`, `getAgentVersion(id, version)`, `updateAgent(id, body)` | 2.2 |
| `runAgent(id, body)`, `getRun(runId)`, `cancelRun(runId)` | 2.2 |
| `streamRunEvents(runId, { lastEventId?, signal? })` → `AsyncIterable<RunEvent>` | `fetch` 로 `text/event-stream` 을 열고 SSE 를 직접 파싱합니다 — 브라우저 `EventSource` 는 `Authorization` 헤더를 붙일 수 없습니다(C-4). `signal` 로 중단 |

sdk 의 단위 테스트(`web-unit`)는 SSE 파서(청크 경계, `id`/`event`/`data` 조립, `Last-Event-ID` 전달)를 fake `fetch` 로 검증합니다.

### 2.18 스트림 계약 (spec 0001 2.3 의 확장)

| 스트림 | 방향 | 필드 | 소비 |
| --- | --- | --- | --- |
| `aether:runs:requested` | Control → Data | `run_id`, `agent_version_id`, `traceparent` | worker consumer group `aether-worker`, `count=1`, PEL 먼저 → `XAUTOCLAIM`(2.4) |
| `aether:runs:status` | Data → Control | `StatusMessage`: `run_id`, `seq`, `status`, `at`, `started_at?`, `finished_at?`, `failure_reason?`, `trace_id?` | api consumer group `aether-api`(2.4 투영). `seq` 는 Run 의 이벤트 `seq` 와 같은 수열 |
| `aether:runs:{run_id}:events` | Data → 독자 | 2.7 의 봉투. explicit ID `<seq>-0` | api SSE 리더(그룹 없음, `XREAD`) |

Control Plane 은 `requested` 에 쓰고 `status` 와 events 를 **읽습니다**. Data Plane 은 `requested` 를 읽고 `status`·events 에 씁니다. 서로의 코드를 import 하지 않습니다. spec 0001 2.3 의 "Control Plane 은 `requested` 에 쓰기만" 은 이 표로 [편집] 개정됩니다(4절 끝) — 방향(선언은 Control, 실행은 Data)은 그대로입니다.

## 3. 우려 지점

| ID | 우려 | 어떻게 다루는가 |
| --- | --- | --- |
| C-1 | **at-least-once 와 중복.** `requested` 재전달, `status` 중복 | worker 는 `data.run_executions` 의 상태와 lease 로(2.4), api 의 투영은 `seq` 단조 증가로(2.4) 멱등. 둘 다 단위 테스트(R-15, R-16) |
| C-2 | **Redis 가 메시지를 잃으면 Run 이 `queued` 에 머뭅니다** | Phase 1 은 **관측 가능하게만** — `GET /runs/{id}` 가 `queued` 와 `requested_at` 을 보여줍니다. XADD 실패도 같은 상태로 수렴(2.2). 고아 Run 재통지는 6절. AOF 가 켜져 있어 손실 창은 좁습니다 |
| C-3 | **취소는 협력적입니다.** 진행 중인 모델 호출은 끝나기를 기다립니다 | 계약에 적습니다(`202` + 최종 상태는 이벤트/GET). 강제 중단은 프로세스 격리가 오는 Phase |
| C-4 | **SSE 의 인증은 브라우저 `EventSource` 와 맞지 않습니다** 🔒 | Phase 1 의 소비자는 sdk 의 `fetch` 기반 파서뿐이라 문제가 없습니다. 브라우저 화면이 SSE 를 직접 열어야 하는 시점(MVP-2 이전)에 쿠키·단기 토큰 등 인증 변경이 필요하고, 그것은 인증에 닿으므로 **사람 결정(🔒)**. 지금 결정하지 않고 기록만 합니다 |
| C-5 | **api 가 Redis 를 처음 씁니다** — 투영 소비자가 api 안에 | lifespan 에서 백오프로 붙고, 붙지 못해도 HTTP 는 뜹니다(`/healthz` 는 liveness). 투영이 멈추면 `GET /runs/{id}` 가 낡은 상태를 답하는 것이 증상 — readiness 는 6절 |
| C-6 | **이벤트 스트림의 메모리** | `MAXLEN ~ 10000`, TTL 24시간. 부하는 `load` 단계의 일 |
| C-7 | **모델은 비결정적입니다** | 판정은 전부 fake(R-6, `pytest-socket`). 실제 모델은 사람의 수동 확인. `AETHER_MODEL_ADAPTER` 기본 `fake` |
| C-8 | **비밀값 하나가 늘 수 있습니다** — `AETHER_MODEL_API_KEY` | 환경변수만, 로그·span·이벤트에 넣지 않음. `reasoning` 본문도 같은 취급. 비밀값 스캔 job 이 계속 봅니다 |
| C-9 | **보호 파일 변경이 네 곳** — `.importlinter`(2.12, **P1-3 병합 뒤·P1-1 착수 전 한 번** — `httpx` ignore 는 어댑터가 있어야 매칭되고 `error` 는 매칭되지 않는 ignore 를 실패로 봅니다. 개정 1), `harness.config`(`smoke`, P1-9), `harness.yml`(bake 캐시, P1-9), `evaluation/README.md`(값, P1-9) | 각각 별도 PR, `harness-change` 라벨, 사람. `pyproject.toml`·`compose.yaml`·`compose.ci.yaml` 은 보호 파일이 아닙니다 |
| C-10 | **D-7 을 넘습니다**(2.11) | 사람 결정 D-15 + `improvement-log/` 1건. 회귀 조건은 숫자(`smoke` ≤ 4분, CI ≤ 8분). 넘으면 (a) |
| C-11 | **`Observation` 표지는 완화이지 방어가 아닙니다**(2.6) | Phase 1 의 도구는 신뢰할 수 있는 프로세스 내부 함수 둘. Phase 2 에서 MCP Firewall 이 같은 지점에 붙습니다 |
| C-12 | **`up --wait` + 일회성 `migrate`** 조합의 compose 동작이 버전마다 다릅니다(로컬 v2.29, CI 는 최신) | P1-9 착수 전 확인 항목. 실패하면 `smoke.sh` 가 `migrate` 종료 코드와 healthcheck 를 직접 기다립니다(2.11) |
| C-13 | **lease 와 시계.** lease 만료 판정은 DB 의 `now()` 기준이고 worker 의 `Clock` 과 다른 시계입니다 | 조건부 UPDATE 를 DB 쪽 `now()` 로 하나의 시계만 씁니다. `AETHER_WORKER_LEASE_SECONDS`(60) 는 한 단계의 최대 길이(모델 호출 타임아웃 잔여)보다 짧을 수 있으므로, 모델 호출 중에도 별도 스레드가 lease 를 갱신합니다 — 갱신 실패(DB 단절)는 현재 단계를 마친 뒤 `LeaseHeld` 로 물러납니다 |

## 4. 결정 요청

이 spec 을 승인하면 아래가 채택됩니다. 하나라도 다르게 하려면 그 항목을 먼저 고친 뒤 승인합니다.

| ID | 결정 | 닫히는 질문 | 근거 |
| --- | --- | --- | --- |
| D-1 | 로컬 LLM 서버의 기본은 **Ollama**(compose `llm` 프로파일). 기본 테스트 모델은 **Qwen3.8 27B 양자화, 태그 `qwen3.8:27b`**(실재 확인 2026-09-12). 태그가 사라지면 사람이 대체를 고르고 기록. 판정은 전부 fake | **Q6 (intent OQ 1)** | 2.5 |
| D-2 | `control.runs` 의 투영은 **api 프로세스 안의 `aether:runs:status` 소비자**가 갱신하며, 멱등의 근거는 **Run 단위 `seq`**(`control.runs.status_seq`). DB 커밋 뒤 ack | intent OQ 2 | 2.4, C-1, C-5 |
| D-3 | `agent_versions.definition` 은 2.3 의 `AgentDefinition`. 도구 이름 검증은 `aether_runtime.domain.tools.BUILTIN_TOOL_NAMES` 로. 어댑터 종류·thinking 은 배포 설정 | intent OQ 3 | 2.3 |
| D-4 | SSE 이벤트는 2.7 의 봉투와 8종(`model.delta` 는 예약). Run 별 Redis Stream, **explicit ID `<seq>-0`**. 스키마는 `events.schema.json` 으로 커밋, TS 타입 생성 | intent OQ 4 | 2.7, R-12 |
| D-5 | 프로세스 내부 도구도 **MCP tool 모양**(`name`, `description`, `input_schema`, `run → ToolResult`). `Task` 는 모델 호출마다 하나 | intent OQ 5 | 2.6 |
| D-6 | `Observation` 은 `role: tool` + `tool_call_id` + `trust: untrusted` 표지로만 모델에 들어갑니다 | — | 2.6, R-14 |
| D-7 | compose 에 `otel-collector` 를 **기본 서비스**로, exporter 는 `debug` + `file`(host bind mount `infra/docker/out/otel/`, 개정 2). 대시보드 없음 | intent OQ 6 | 2.9 |
| D-8 | `{{성능_기준}}` 은 `POST /agents/{id}/run` 응답 P95, `smoke.sh --bench` 순차 200회(워밍업 20 제외), 환경 이름을 붙여 **사람이** 값을 적음 | intent OQ 7 | 2.13 |
| D-9 | HTTP 계약은 2.2 의 **9개 경로**(`GET /agents/{id}/versions/{version}` 포함). `PUT` 은 `definition` 만, `name` 은 Phase 1 불변, 버전 번호는 `control.agents.current_version` + `SELECT … FOR UPDATE`, 충돌 시 `409 agent_version_conflict`. `requested_by` 를 기록·응답. 삭제·Run 목록 없음 | — | 2.2, 2.10 |
| D-10 | 상태 기계는 2.4 의 전이표. 실행 권한은 **`data.run_executions` 의 lease**(`lease_owner`, `lease_until`, 단계마다 갱신). worker 는 자기 PEL 먼저, `XAUTOCLAIM` 은 `min-idle ≥ 3900초`, `count=1`. 재개 시 종결이면 **알림·`run.finished` 재발행** 뒤 ack | — | 2.4, R-15, R-16 |
| D-11 | 취소의 정본은 **`control.runs.cancel_requested_at` 하나**. worker 가 단계 사이에 SELECT. 취소 스트림 없음. 협력적 | — | 2.4, C-3 |
| D-12 | 마이그레이션 0002: `control.agents.current_version`, `control.runs` 투영·선언 열(`input`, `status`, `status_seq`, …), `data.run_executions` lease 열, `data.run_states` 신설. `aether_control` 의 `data` 권한은 여전히 없음 | — | 2.10 |
| D-13 | AR-5 에 `httpx` 추가 + `-> httpx` ignore, **벤더 SDK ignore 셋 삭제**(forbidden 은 유지), alerting `error`; AR-7 에 `aether_api → aether_runtime.application/adapters` 금지. `.importlinter` 는 **P1-3 병합 뒤 한 번**(사람). AR-10 은 구조 테스트. R-7 은 **실제 `.importlinter`** 로 판정(src 복사 + `PYTHONPATH`) | — | 2.12, 개정 1 |
| D-14 | 테스트의 `sleep` 금지를 구조 테스트로(`time.sleep(`, `from time import sleep`, `asyncio.sleep(`). 기존 2곳은 P1-2 에서 시계 주입으로 제거. 기다림은 `wait_until` 하나 | — | R-11, 2.16 |
| D-15 | **`smoke` 는 11번째 제품 단계**(`behavior`, `scripts/smoke.sh`, 격리 프로젝트·임시 `.env`). spec 0001 **D-7 을 [실질] 개정** — 제품 단계 11개, 총 17. (c) 합치기는 기각. 회귀 조건: `smoke` 단독 ≤ 4분(로컬), CI `verify` ≤ 8분 — 넘으면 (a). CI 캐시는 `buildx bake … type=gha` + `compose.ci.yaml`. `improvement-log/` 1건 | intent OQ 8 | 2.11, C-10 |
| D-16 | worker healthcheck 는 Redis 하트비트 키. worker 가 DB(`aether_data`)를, api 가 Redis 를 처음 씁니다 | — | 2.14, 2.15 |
| D-17 | sdk 는 새 경로 함수 8개 + `streamRunEvents`(`fetch` 기반 SSE 파서). 타입은 생성, 호출은 수기(spec 0001 D-2 유지) | — | 2.17 |
| D-18 | 테스트 도구(개정 1): pytest `pythonpath = ["."]`(기본 prepend, importlib 아님) + `addopts` 에 `pytest-socket` 의 `--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1`(`integration` 은 `enable_socket`); mypy `explicit_package_bases = true` + `mypy_path` 9개 `src`; 테스트 헬퍼는 네임스페이스 경로 import; 공용 fixture 는 `tests/support/`(`pyproject.toml`, P1-2a) | — | 2.16, R-6 |
| D-19 | OpenAI-호환 어댑터는 `reasoning` 을 `text` 에서 분리하고 `AETHER_MODEL_THINKING`(기본 `false`)으로 서버 옵션을 보냅니다. `reasoning` 은 로그·span·이벤트에 넣지 않습니다 | — | 2.5, C-8 |

승인과 함께 다음을 같은 커밋에서 합니다: [../intents/0002-phase-1-agent-runtime.md](../intents/0002-phase-1-agent-runtime.md) 의 Open Questions 1 ~ 8 을 닫음(7 은 "측정 정의 닫힘, 값은 P1-9"); [../intents/intent.md](../intents/intent.md) 머리 표 갱신; spec 0001 에 **개정 12 [실질]**(D-7 → 11개, 근거 D-15) 과 **개정 13 [편집]**(2.3 스트림 문장 → 2.18 의 표, C-6 은 2.12 로 닫힘) 행; [../intents/mvp-backlog.md](../intents/mvp-backlog.md) P1-1 완료 판정 문구를 [편집] 로 고침 — `aether_runtime.domain` 만 허용, P1-5 산출물에 `docs/api.md`([../docs/README.md](../docs/README.md) 가 Phase 1 에 약속) 추가.

## 5. 검증 매핑

| R | 단위 | 판정 명령 또는 절차 |
| --- | --- | --- |
| R-1 | P1-1 | `api-integration`: 생성·수정·`versions/{version}` 조회. `api-unit`: `test_openapi_drift` |
| R-2 | P1-2, P1-4, P1-5 | `api-integration`: PG + Redis testcontainers, worker 스레드, fake 모델 → `succeeded` / `cancelled`. `smoke` |
| R-3 | P1-6 | `api-integration`: 이벤트 순서 == 전이 순서, 단절 뒤 `wait_until` 로 `succeeded` |
| R-4 | P1-7 | `api-unit`(`packages/runtime/tests`): `FakeClock` 타임아웃·재시도 |
| R-5 | P1-4, P1-8 | `api-unit`: 인메모리 `Tracer`. `smoke`: `infra/docker/out/otel-smoke/spans.jsonl` 에서 `trace_id` |
| R-6 | P1-2a, P1-3 | `api-unit`(`addopts` 소켓 차단, loopback 만 허용): 두 어댑터 계약 테스트(`httpx.MockTransport`) |
| R-7 | P1-1 (+H-4) | `api-arch` + `tests/arch/test_real_importlinter_fires.py`(실제 `.importlinter`, `src` 복사 + `PYTHONPATH`, 위반 주입) |
| R-8 | P1-1, P1-5, P1-6 | `api-unit`: `app.routes` 순회 401 |
| R-9 | P1-9 | `.harness/verify.json`: `smoke` pass, 합계 ≤ 600,000 ms, `smoke` ≤ 240,000 ms |
| R-10 | P1-9 | `scripts/smoke.sh --bench` → `.harness/smoke-bench.json` → 사람이 evaluation/README 에 값 |
| R-11 | P1-2 | `tests/arch/test_no_sleep_in_tests.py` |
| R-12 | P1-1, P1-6 | `api-unit`: `test_openapi_drift`, `test_events_schema_drift`. `web-typecheck` 생성물 드리프트 |
| R-13 | P1-5 | compose `worker` healthy. `api-integration`: 하트비트 키 TTL |
| R-14 | P1-4 | `api-unit`: fake 모델이 받은 요청의 메시지 구조 |
| R-15 | P1-2 | `api-unit`: lease 유효 시 `LeaseHeld`, 만료 시 재개 |
| R-16 | P1-2, P1-5 | `api-unit`: 종결 뒤 알림 실패 → 재개가 재발행 |

## 6. Non-goals

intent 의 것을 반복하고, 설계하면서 새로 뺀 것을 더합니다.

| 항목 | 언제 |
| --- | --- |
| MCP Gateway·Firewall, 외부 시스템 연동 | Phase 2. 도구 인터페이스(D-5)가 그 자리 |
| Context Compiler, RAG, Memory, Knowledge | Phase 3. `embed` 는 인터페이스만 |
| HITL, Approval, Workflow | Phase 4. `waiting` 상태가 그 자리 |
| Permission, Policy, 조직·사용자, SSO | Phase 8 |
| **브라우저용 SSE 인증**(쿠키·단기 토큰) 🔒 | MVP-2 전 사람 결정(C-4) |
| Model Registry, 벤더 SDK, 프롬프트 캐싱, 비용 집계, vLLM 등 다른 서버 | Phase 6 / 서버 부하가 오는 Phase |
| `apps/web` 화면, `GET /runs` 목록, `DELETE /agents/{id}`, `name` 변경 | Experience 의 Phase. 소비자가 생길 때 |
| `POST /agents/{id}/run` 의 멱등키 | 클라이언트 재시도가 문제로 관측될 때 |
| SSE 재접속 이어보기의 **보장**, `MAXLEN` 너머의 재생, WebSocket, `model.delta` 발생 | 이후. `seq` 와 `Last-Event-ID` 만 남깁니다 |
| 이벤트 이력의 영속(DB), outbox 테이블 | 이후. Phase 1 은 Redis TTL + 재개 재발행 |
| 고아 Run 재통지(reconciliation), 강제 취소, 다중 worker 의 부하 분산 검증 | 이후. C-2, C-3. lease 는 정확성만 보장합니다 |
| readiness 엔드포인트 | 이후. Phase 1 의 compose 는 healthcheck 로 충분 |
| 부하 테스트(`load`), 대시보드, 샘플링 정책, 프로세스를 실제로 죽이는 재개 테스트 | 이후 |
| Kubernetes, Air-Gapped 번들 | Month 6 / Phase 11 |

## 관련 문서

- [../intents/0002-phase-1-agent-runtime.md](../intents/0002-phase-1-agent-runtime.md) — 근거 intent
- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — P1-1 ~ P1-9
- [0001-phase-0-foundation.md](0001-phase-0-foundation.md) — 유효한 Phase 0 결정(D-7 은 D-15 로, 2.3 은 2.18 로 개정)
- [../docs/architecture.md](../docs/architecture.md) — AR-*, DP-*, 3.1 배치
- [../docs/domain.md](../docs/domain.md) — `Run`, `Task`, `State`, `Observation`
- [../docs/data-model.md](../docs/data-model.md) — 열 단위 정본(P1 이 갱신)
- [../evaluation/README.md](../evaluation/README.md) — `{{성능_기준}}`, REP-2·4·8
- [../harness/rules/evaluation-integrity.rule.md](../harness/rules/evaluation-integrity.rule.md) — EI-2
- [README.md](README.md) — spec 의 규칙
