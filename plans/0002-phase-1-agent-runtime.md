# Plan 0002 — Phase 1: Agent Runtime

| 키 | 값 |
| --- | --- |
| 번호 | 0002 |
| 근거 spec | [../specs/0002-phase-1-agent-runtime.md](../specs/0002-phase-1-agent-runtime.md) (승인됨 2026-09-12, D-1 ~ D-19) |
| 근거 intent | [../intents/0002-phase-1-agent-runtime.md](../intents/0002-phase-1-agent-runtime.md) |
| 작업 단위 | [../intents/mvp-backlog.md](../intents/mvp-backlog.md) P1-1 ~ P1-9 |
| 작성일 | 2026-09-12 |
| 상태 | 초안 |
| 승인 | (비어 있음 — 순서와 사람 손의 횟수에 동의하는 것이 승인입니다) |
| 개정 | — |

spec 이 정한 요구사항(R-1 ~ R-16)·결정(D-1 ~ D-19)·계약은 반복하지 않습니다. 이 문서는 아홉 단위를 어떤 순서로 하고, 단위마다 어느 파일을 누가 만들며, 무엇으로 판정하는지를 정합니다. Phase 0 의 plan 과 같은 절 구성이고, 표기도 같습니다 — **A** 에이전트(`implementer`, Sonnet 5), **H** 사람(보호 파일, spec 0001 C-1), **W** 가드가 경고만 내는 파일.

이 plan 이 풀어야 하는 문제는 둘입니다.

1. **보호 파일 변경이 네 곳**(spec 0002 C-9) — `.importlinter`, `harness.config`, `harness.yml`, `evaluation/README.md`. 사람 손을 **두 순간**으로 묶습니다: wave 1 착수 전(H-4)과 P1-9(H-4b · H-5 · H-6 · H-7).
2. **`.importlinter` 의 AR-5 는 어댑터가 있어야 `error` 로 켤 수 있습니다.** `unmatched_ignore_imports_alerting = error` 는 ignore 가 매칭되지 않으면 실패하므로, `httpx` 어댑터가 생기기 전에는 `warn` 이어야 합니다. 그래서 D-13 을 두 단계로 나눕니다 — H-4(착수 전: `httpx` 금지 + ignore + AR-7 확장, `warn` 유지) 와 H-4b(P1-9: `warn` → `error`). 결정은 그대로이고 시점만 plan 이 정합니다.

## 1. 순서

의존 그래프(backlog 의 `의존` 열)와 spec 2.1 의 배치에서 유도했습니다. 한 wave 안의 단위는 서로 독립이라 순서를 바꿔도 되지만, **세션 하나에 단위 하나**이므로 실제로는 차례로 갑니다. 판정은 모델과 무관하게 4절의 명령입니다.

| Wave | 단위 | 왜 이 자리인가 | 사람 손 |
| --- | --- | --- | --- |
| — | (선행) | `.importlinter` 에 AR-5 `httpx` 금지·AR-7 확장이 **코드보다 먼저** 있어야 위반이 첫 커밋부터 걸립니다 | **H-4** |
| 1 | **P1-2** Run 상태 기계 + 마이그레이션 0002 + 테스트 도구 | 순수 도메인이라 가장 쌉니다. 마이그레이션 0002 는 spec 2.10 의 변경을 **한 번에** 담아 P1-1·P1-5 가 열을 기다리지 않게 합니다. `packages/runtime/tests` 가 처음 생기므로 mypy·pytest 설정 변경(D-18)과 `sleep` 금지(D-14)도 여기서 | — |
| 1 | **P1-3** Model gateway | P0-1 만 필요. P1-2 와 병렬 가능(같은 `packages/runtime` 이지만 다른 모듈). `httpx` 어댑터가 생기는 단위 — H-4 뒤여야 합니다 | Q6 태그 확인은 PR 리뷰에서(파일은 A) |
| 2 | **P1-1** Agent Registry API | P0-8·P0-9 와 P1-2 의 마이그레이션(`current_version`)이 필요. `AgentDefinition` 은 여기서 `aether_runtime.domain` 에 생깁니다 — api 가 처음으로 runtime 을 import | — |
| 2 | **P1-4** Planner/Executor 루프 | P1-2(상태 기계·lease)와 P1-3(gateway) 위에. `Tracer` 포트와 인메모리 구현도 여기서(span 트리는 루프의 구조) | — |
| 3 | **P1-5** Run API + worker 실행 + 투영 + heartbeat | 전부가 만나는 자리. P1-1(Agent), P1-4(루프), P0-4(worker 뼈대). Redis `EventSink`·`StatusNotifier` 어댑터도 여기(worker 가 발행하므로) | — |
| 4 | **P1-6** Streaming | P1-5 의 이벤트 스트림을 읽는 쪽. sdk 의 SSE 파서 | — |
| 4 | **P1-7** Retry / Timeout / Error | P1-5 뒤. 루프(P1-4)에 정책을 꽂는 일이라 P1-6 과 병렬 가능 | — |
| 4 | **P1-8** Trace | P1-5 뒤. `Tracer` 의 OTel 구현, `traceparent` 전파, collector 서비스 | — |
| 5 | **P1-9** smoke + 성능 기준 + 보호 파일 넷 | 전부가 있어야 e2e 가 성립. 사람 손 네 접촉이 여기 모입니다 | **H-6 → H-5 → H-4b, H-7** |

P1-2 를 P1-1 보다 앞에 둔 것은 의도입니다(backlog 번호 순서와 다름). 마이그레이션·테스트 도구·`sleep` 금지가 먼저 있어야 이후 모든 단위가 그 아래에서 작성됩니다 — Phase 0 에서 P0-6 을 앞당긴 이유와 같습니다.

## 2. 단위별 계획

모든 단위는 **red(실패하는 테스트, 실행해 기록) → green → refactor(테스트 불변)** 순서이고, 보고의 `red 증거` 칸이 그것을 증명합니다. 테스트 docstring 은 `spec 0002 R-n`·`D-n`·`AR-n` 을 인용합니다. 단위마다 브랜치 하나(`p1-2-runtime-state`), PR 하나, 커밋 trailer `Unit: P1-n`.

### P1-2 Run 상태 기계, 마이그레이션 0002, 테스트 도구

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | **도구 설정**(D-18) — 루트 `pyproject.toml`: `[tool.mypy] explicit_package_bases = true`, `[tool.pytest.ini_options] addopts = "--import-mode=importlib"`, dev 그룹에 `pytest-socket`. `packages/runtime/pyproject.toml` 에 `pydantic`, `psycopg[binary]`, `redis`(2.16). `uv sync --all-packages` → `uv.lock`. 이 순서가 먼저인 이유: 2번의 `packages/runtime/tests/conftest.py` 가 생기는 순간 mypy 가 `apps/api/tests/conftest.py` 와 충돌합니다(spec 2.16) | A (W) |
| 2 | **red** — `packages/runtime/tests/`: `test_run_state_machine.py`(전이표 전부 — 허용 전이 성공, 불허 전이 `IllegalTransition`, 종결 상태에서 나가는 전이 0건), `test_run_state.py`(`RunState` 직렬화 왕복, `seq` 단조), `test_lease.py`(R-15: fake 저장소에 유효 lease → `acquire_lease` 실패, 만료 → 성공, `renew`·`release`), `test_run_state_store_contract.py`(**포트 계약 테스트** — fake 와 PostgreSQL 구현에 같은 케이스: `save`/`load` 왕복, lease 조건부 UPDATE 의 원자성, 없는 run 의 `load` → `None`. PostgreSQL 쪽은 `integration`, `aether_data` 역할). `tests/arch/test_no_sleep_in_tests.py`(R-11 — 지금 2곳이 걸려 **red**), `apps/api/tests/waiting.py` 의 `wait_until` 과 그 단위 테스트. 전부 실행해 실패 기록 | A |
| 3 | **green** — `aether_runtime/domain/run.py`(`RunStatus`, `transition`, `RunState`, `IllegalTransition`, `LeaseHeld`), `domain/task.py`, `domain/failure.py`, `application/ports/outbound/run_state_store.py`, `application/ports/outbound/clock.py`(`now`·`monotonic`·`sleep`), `adapters/outbound/db/run_state_store.py`(PostgreSQL. lease 는 `UPDATE … WHERE lease_until IS NULL OR lease_until < now() RETURNING` 한 문장). `packages/runtime/tests/fakes.py`(`FakeRunStateStore`, `FakeClock`). `apps/api/tests/test_api_key_store_contract.py` 와 `apps/worker/tests/test_connect.py` 의 `sleep` 제거 — 전자는 `FakeApiKeyStore(clock=)` 주입, 후자는 `Event.wait` 로 | A |
| 4 | **마이그레이션 0002** — `apps/api/migrations/versions/0002_phase1_runs_lease_states.py`: spec 2.10 전부(`control.agents.current_version`, `control.runs` 의 `input`·`status`·`status_seq`·`started_at`·`finished_at`·`failure_reason`·`trace_id`·`cancel_requested_at`, `data.run_executions.lease_owner`·`lease_until`, `data.run_states`, GRANT). `downgrade` 전부 되돌림. 기존 `test_migrations.py`(왕복)와 `test_plane_roles.py` 가 그대로 통과해야 하고, `aether_control` 이 `data.run_states` 에 접근하면 permission denied 인 케이스 1건 추가 | A |
| 5 | `docs/data-model.md` — 새 열·테이블·lease 의미·cross-schema FK 하나 추가(4절) | A |
| 6 | **refactor**. 판정: `verify.sh` 16단계 pass. `uv run pytest -q -m 'not integration' --disable-socket` 도 통과(다음 단위부터 `api-unit` 명령에 넣을 준비 — `harness.config` 는 P1-9 의 H-5 에서 바뀌므로 그때까지는 손으로 확인) | A |

8회 안에 끝나지 않으면 P1-2a(1·4·5: 도구·마이그레이션·문서)와 P1-2b(2·3: 상태 기계·lease)로 쪼갭니다.

### P1-3 Model gateway 와 첫 어댑터

H-4 가 끝난 뒤 시작합니다(`.importlinter` 에 `httpx` 금지가 있어야 이 단위의 R-7 테스트가 성립).

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `packages/runtime/pyproject.toml` 에 `httpx`. `uv sync --all-packages` | A (W) |
| 2 | **red** — `packages/runtime/tests/test_model_gateway_contract.py`(fake 와 OpenAI-호환에 같은 케이스: 텍스트 응답, `tool_calls[].id` 보존, `tool` 메시지의 `tool_call_id` 전송, **tools + stream 동시** 청크 파싱, `reasoning_content` 분리, `think: false` 옵션 전송, 5xx·타임아웃 → `ModelError`, `embed` 왕복. OpenAI-호환은 `httpx.MockTransport`), `test_fake_model_gateway.py`(시나리오 주입). `tests/arch/test_real_importlinter_fires.py`(R-7 — 실제 `.importlinter` 복사 + `aether_api/_bad.py` 에 `import httpx` 주입 → exit ≠ 0. **H-4 뒤라 `httpx` 금지가 실재**. `aether_runtime.application` 주입 케이스도 함께). 실행해 실패 기록 | A |
| 3 | **green** — `application/ports/outbound/model_gateway.py`(`ModelRequest`·`ModelResponse`·`ModelDelta`·`ModelError`), `adapters/outbound/model_gateway/fake.py`, `adapters/outbound/model_gateway/openai_compatible.py`(`httpx` 는 이 디렉터리에만) | A |
| 4 | `infra/docker/compose.yaml` 에 `llm` 서비스(`profiles: ["llm"]`, Ollama 이미지 digest 고정, 모델 볼륨). `.env.example` 에 `AETHER_MODEL_ADAPTER=fake`, `AETHER_MODEL_BASE_URL`, `AETHER_MODEL_ID=qwen3.8:27b`, `AETHER_MODEL_API_KEY=<optional>`, `AETHER_MODEL_THINKING=false`. 루트 README 에 "실제 모델로 돌리기" 절(프로파일 켜기, `ollama pull qwen3.8:27b`, VRAM 안내, 판정 대상이 아님을 명시) | A |
| 5 | **refactor**. 판정: `verify.sh` pass. `api-arch` 가 11 kept 이상(`.importlinter` 의 계약 수는 H-4 뒤 기준). 보고에 "`AETHER_MODEL_ID` 태그는 사람 확인 필요" 를 남김 | A |
| 6 | **PR 리뷰에서 사람이 확인**: Ollama 태그 `qwen3.8:27b` 가 여전히 실재하는지(D-1). 실재하지 않으면 사람이 대체 태그를 정해 `.env.example` 과 `improvement-log/` 에 적음 | **H**(파일은 A) |

### P1-1 Agent Registry API

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `apps/api/pyproject.toml` 에 `aether-runtime`(workspace), `redis`. `uv sync --all-packages` | A (W) |
| 2 | **계약 먼저**(DP-1, R-12) — `aether_runtime/domain/agent.py`(`AgentDefinition`, spec 2.3), `domain/tools.py`(`BUILTIN_TOOL_NAMES`, `ToolCall`, `ToolResult`). 라우터 껍데기(`adapters/inbound/http/agents.py` — 경로·모델만, 본문은 `NotImplementedError`)로 `uv run aether-api openapi > packages/sdk/openapi.json` 갱신, `pnpm -F sdk run generate` 로 타입 생성, 둘 다 커밋. `docs/api.md` 시작(agents 5경로 표 — `docs/README.md` 의 자리) | A |
| 3 | **red** — `apps/api/tests/test_agents_api.py`(`integration`: 생성 201 → `GET /agents/{id}` → `PUT` → `current_version == 2` → `GET /agents/{id}/versions/1` 의 `definition` 동일(R-1); `409 agent_name_taken`; `404` 둘; 422 — `tools` 에 `BUILTIN_TOOL_NAMES` 밖 이름, `schema_version: 2`), `test_agents_api_unit.py`(fake `AgentRepository` 로 유스케이스), `test_agent_version_concurrency.py`(`integration`: 스레드 둘이 동시 `PUT` → 하나는 200, 하나는 200 또는 409, 최종 `current_version == 3`, unique 위반 0건), `test_routes_require_auth.py`(R-8: `app.routes` 순회 401 — 예외 목록 `/healthz`, `/openapi.json`, `/docs`, `/redoc`). 실행해 실패 기록 | A |
| 4 | **green** — `application/ports/inbound/agents.py`, `application/ports/outbound/agent_repository.py`, `application/usecases/agents/*.py`(`CreateAgent`, `ListAgents`, `GetAgent`, `GetAgentVersion`, `UpdateAgent` — `UpdateAgent` 는 저장소의 `lock_for_update(agent_id)` 안에서 `current_version + 1`), `adapters/outbound/db/agent_repository.py`(`SELECT … FOR UPDATE`, unique 위반 → `AgentVersionConflict`), `adapters/inbound/http/agents.py`(본문. `require_principal(app.state.authenticate)` 를 라우터 의존성으로. **모듈 수준 라우터 + `build_agents_router(principal_dep)` 팩토리** — improvement-log 017 의 함정을 피하는 형태), `main.py` 조립 | A |
| 5 | `packages/sdk/src/client.ts` 에 `createAgent`·`listAgents`·`getAgent`·`getAgentVersion`·`updateAgent` + 테스트(fake fetch). `tests/arch/test_composition_only_in_main.py`(D-13 AR-10 — 지금 트리에서 통과해야 함) | A |
| 6 | **refactor**. 판정: `verify.sh` pass. `test_openapi_drift` 가 2번의 커밋과 일치. `web-typecheck` 의 생성물 드리프트 0 | A |

### P1-4 Planner/Executor 루프

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | **red** — `packages/runtime/tests/test_execute_run.py`(fake gateway·fake tools·fake store·`FakeClock`·인메모리 `Tracer`·fake `EventSink`·fake `StatusNotifier`: 도구를 부르는 시나리오 → `succeeded`, 부르지 않는 시나리오 → `succeeded`, `max_steps` 초과 → `failed(max_steps_exceeded)`, `unknown_tool`, cancel 관측 → `cancelled`, 전이 순서 == 발행된 `run.status` 순서, `seq` 가 1 부터 연속), `test_observation_boundary.py`(R-14: fake gateway 가 받은 요청에서 `role: tool` + 표지, system 에 없음, `tool_call_id` 일치, 잘림 표시), `test_resume.py`(R-16: 종결 커밋 뒤 notifier 실패 → 두 번째 호출이 재발행 뒤 ack; `running` + lease 만료 → `RunState` 에서 이어감; lease 유효 → `LeaseHeld`), `test_tools.py`(`clock` 은 `Clock` 을 씀, `calculator` 는 `eval` 없이 사칙연산·괄호, 잘못된 식 → `is_error`), `test_tracer_tree.py`(R-5: `run` → `task` → `model.complete`/`tool.run` 부모–자식). 실행해 실패 기록 | A |
| 2 | **green** — `domain/observation.py`, `domain/events.py`(봉투·8종, `v: 1`), `application/ports/outbound/{tools,event_sink,status_notifier,tracer,run_declaration_reader}.py`, `application/ports/inbound/execute_run.py`, `application/usecases/execute_run.py`(spec 2.4 의 lease·재개·재발행 + 2.6 의 루프 — `complete` 만), `adapters/outbound/tools/{clock_tool,calculator,registry}.py`, `adapters/outbound/telemetry/in_memory_tracer.py` 는 테스트 지원이므로 `tests/fakes.py` 에 | A |
| 3 | `tests/arch/test_usecases_have_tests.py` 가 새 유스케이스에 대해 실제로 걸림(`test_execute_run.py` 존재). `BUILTIN_TOOL_NAMES == set(registry.names())` 단언 테스트 | A |
| 4 | **refactor**. 판정: `verify.sh` pass. `packages/runtime` 의 `domain`·`application` 이 `httpx`·`redis`·`psycopg`·`opentelemetry` 를 import 하지 않음(`api-arch` AR-9) | A |

### P1-5 Run API, worker 실행, 투영, heartbeat

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `apps/worker/pyproject.toml` 에 `aether-runtime`, `psycopg[binary]`. `uv sync --all-packages` | A (W) |
| 2 | **계약 먼저** — 라우터 껍데기로 `openapi.json` 갱신(`POST /agents/{id}/run`, `GET /runs/{id}`, `POST /runs/{id}/cancel`), sdk 타입 생성, 커밋. `docs/api.md` 에 runs 3경로와 스트림 계약 표(spec 2.18) | A |
| 3 | **red** — `apps/api/tests/test_runs_api.py`(`integration`: PG + Redis testcontainers. `POST run` 202 + `requested_by == 키 id` + `control.runs` 행 + `requested` 스트림 메시지(`traceparent` 필드 존재); `GET` 은 `queued`; `cancel` 멱등; `404`), `test_apply_run_status.py`(fake 저장소: `seq` 단조 — 낮은 `seq` 무시, 같은 `seq` 무시, 역행 무시, 커밋 뒤 ack 순서), `test_run_end_to_end.py`(`integration`, R-2: api 앱 + worker `serve()` 를 스레드로, fake gateway → `wait_until(status == "succeeded")`; cancel 시나리오는 fake gateway 를 `Event` 로 멈춰 세운 뒤 `cancel` → `cancelled`), `apps/worker/tests/test_handle_run_requested.py`(fake `ExecuteRun`: 성공 → ack, `LeaseHeld` → ack 안 함, `traceparent` 복원), `test_heartbeat.py`(`integration`, R-13: 키 TTL 갱신), `test_requested_consumer.py`(PEL 먼저 → `XAUTOCLAIM` 순서, `count=1`). 실행해 실패 기록 | A |
| 4 | **green(api)** — `application/ports/inbound/runs.py`·`apply_run_status.py`, `application/ports/outbound/{run_declaration_store,run_notifier}.py`, `application/usecases/runs/*.py`(`RequestRun` — 커밋 뒤 XADD, XADD 실패 WARNING; `GetRun`; `CancelRun`; `ApplyRunStatus`), `adapters/outbound/db/run_declaration_store.py`, `adapters/outbound/redis/run_notifier.py`, `adapters/inbound/http/runs.py`, `adapters/inbound/stream/status_consumer.py`(lifespan 백그라운드, consumer group `aether-api`, 백오프 재시도, 붙지 못해도 HTTP 는 뜸), `settings.py` 에 `redis_url`, `main.py` 조립(lifespan) | A |
| 5 | **green(worker)** — `application/ports/inbound/handle_run_requested.py`, `application/usecases/handle_run_requested.py`, `adapters/inbound/stream/requested_consumer.py`(기존 `stream.py` 대체), `adapters/outbound/redis/heartbeat.py`, `settings.py` 에 `database_url`(`aether_data`)·`worker_lease_seconds`·`worker_heartbeat_seconds`·`worker_consumer`, `main.py` 조립(runtime 의 `ExecuteRun` + PostgreSQL `RunStateStore`·`RunDeclarationReader` + Redis `EventSink`·`StatusNotifier` + 아직은 no-op `Tracer`). runtime 쪽 `adapters/outbound/redis/{event_sink,status_notifier}.py`, `adapters/outbound/db/run_declaration_reader.py` | A |
| 6 | `infra/docker/compose.yaml` — worker 에 `AETHER_DATABASE_URL`(`aether_data`), api 에 `AETHER_REDIS_URL`, worker healthcheck(`python -c` 하트비트 키), `depends_on` 갱신. `infra/docker/worker.Dockerfile` 의 HEALTHCHECK 주석 갱신. `.env.example` 갱신. 루트 README 에 "Run 실행해 보기" 절 | A |
| 7 | `packages/sdk` 에 `runAgent`·`getRun`·`cancelRun` + 테스트 | A |
| 8 | **refactor**. 판정: `verify.sh` pass. `docker compose … up` 뒤 `worker` 가 healthy(수동 확인, P1-9 의 smoke 가 자동화). `api-arch`: `aether_api` 가 `aether_runtime.application`·`adapters` 를 import 하지 않음(AR-7 확장, H-4 뒤 실효) | A |

### P1-6 Streaming

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `packages/sdk/package.json` 에 `json-schema-to-typescript`(devDependency). `scripts.generate` 를 `openapi-typescript … && json2ts -i events.schema.json -o src/generated/events.d.ts` 로. `pnpm install` | A (W) |
| 2 | **계약 먼저** — `adapters/inbound/cli.py` 에 `events-schema` 서브커맨드(`aether_runtime.domain.events` 의 JSON Schema 출력), `uv run aether-api events-schema > packages/sdk/events.schema.json`, 생성 타입 커밋. `GET /runs/{id}/events` 껍데기로 `openapi.json` 갱신. `docs/api.md` 에 이벤트 절 | A |
| 3 | **red** — `apps/api/tests/test_events_schema_drift.py`(R-12), `test_run_events_sse.py`(`integration`, R-3: 이벤트 순서 == 전이 순서, `id` 가 `seq`, `Last-Event-ID` 로 재개, 스트림이 없고 종결이면 합성 `run.finished`, 소비자를 끊은 뒤 `wait_until(succeeded)`), `test_sse_route_is_async.py`(핸들러가 코루틴/비동기 제너레이터임을 단언 — 스레드풀 점유 금지의 최소 검사). `packages/sdk/src/sse.test.ts`(파서: 청크 경계, 멀티라인 `data`, `id` 전달, `signal` 중단). 실행해 실패 기록 | A |
| 4 | **green** — `application/ports/inbound/read_run_events.py`, `application/ports/outbound/run_event_reader.py`, `application/usecases/read_run_events.py`, `adapters/outbound/redis/run_event_reader.py`(`redis.asyncio`, `XREAD BLOCK`), `adapters/inbound/http/events.py`(SSE, `run.finished` 뒤 닫기, 단절 시 취소). worker 쪽 `EventSink` 가 explicit ID `<seq>-0`·`MAXLEN`·TTL 을 쓰는지 P1-5 의 구현을 확인해 필요하면 여기서 맞춤. `packages/sdk/src/sse.ts`, `streamRunEvents` | A |
| 5 | **refactor**. 판정: `verify.sh` pass. `web-typecheck` 드리프트 0(`events.d.ts` 포함) | A |

### P1-7 Retry / Timeout / Error Handling

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | **red** — `packages/runtime/tests/test_policy.py`(R-4: `FakeClock` 전진으로 `timed_out`; 모델 재시도 소진 → `failed(model_error)`; 도구 재시도 소진 → `failed(tool_error)`; 백오프 지연이 `Clock.sleep` 호출 인자로 관측됨 — 실제 대기 0; 잔여 시간이 모델 호출 타임아웃으로 전달됨; `definition_invalid`), `apps/api/tests/test_run_failure_projection.py`(`integration`: `failure_reason` 이 `GET /runs/{id}` 에 나타남). 실행해 실패 기록 | A |
| 2 | **green** — `application/usecases/execute_run.py` 에 정책 적용(P1-4 의 루프에 꽂음 — 유스케이스 파일 하나, 테스트는 늘고 기존 테스트는 불변), `domain/failure.py` 완성, lease 갱신 스레드(spec C-13 — 모델 호출 중 갱신, 실패 시 단계 뒤 `LeaseHeld`) | A |
| 3 | **refactor**. 판정: `verify.sh` pass. `tests/arch/test_no_sleep_in_tests.py` 여전히 0건 | A |

### P1-8 Trace

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `packages/runtime/pyproject.toml` 에 `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`(어댑터). `uv sync --all-packages` | A (W) |
| 2 | **red** — `packages/runtime/tests/test_otel_tracer.py`(OTel `Tracer` 구현이 `InMemorySpanExporter` 로 부모–자식·속성을 남김. 프롬프트·`reasoning` 속성 0건), `apps/api/tests/test_trace_propagation.py`(`integration`: `POST run` 의 `traceparent` 가 `requested` 메시지에 있고, e2e 뒤 `GET /runs/{id}` 의 `trace_id` 가 그 trace 와 같음). 실행해 실패 기록 | A |
| 3 | **green** — `adapters/outbound/telemetry/otel_tracer.py`, worker `main.py` 가 no-op `Tracer` 를 OTel 로 교체(`OTEL_EXPORTER_OTLP_ENDPOINT` 없으면 exporter 없음 — 기존 `init_telemetry` 규칙), api 의 `RequestRun` 이 `traceparent` 를 메시지에 실음, worker 가 부모로 복원, `trace_id` 를 `data.run_executions` 와 `StatusMessage` 에 | A |
| 4 | `infra/docker/compose.yaml` 에 `otel-collector`(contrib 이미지 digest 고정, `debug` + `file` exporter, host bind mount `../../.harness/otel/`), api·worker 에 `OTEL_EXPORTER_OTLP_ENDPOINT`. `infra/docker/otel-collector.yaml` 설정 파일. 루트 `.gitignore` 에 `.harness/otel/` 추가 — `.harness/` 는 통째로 무시되지 않고 파일별로 적혀 있습니다(확인함) | A |
| 5 | **refactor**. 판정: `verify.sh` pass. 수동: compose 로 Run 하나 → `.harness/otel/spans.jsonl` 에 `trace_id`(P1-9 가 자동화) | A |

### P1-9 smoke, 성능 기준, 보호 파일 넷

코드보다 설정이 많은 단위입니다. `red 증거` 는 착수 시점에 `scripts/smoke.sh` 가 없어 판정 명령이 실패함을 기록한 것으로 대신하고, 끝에 같은 명령의 성공을 기록합니다.

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `scripts/smoke.sh`(spec 2.11 그대로: `-p aether-smoke`, 임시 `.env`, `up --build -d --wait` 대상 6서비스, `keys create`, agent → run → `succeeded` 폴링 60초, `trace_id` 폴링 30초, trap `down -v`, `MSYS_NO_PATHCONV=1`, `exec -T`, `SMOKE_NO_BUILD=1` 지원, `--bench`). `git update-index --chmod=+x`. **C-12 확인**: `up --wait` 가 일회성 `migrate` 와 함께 동작하는지 로컬(compose v2.29)에서 먼저 실행 — 실패하면 스크립트가 `migrate` 종료 코드와 healthcheck 를 직접 기다리는 경로로 | A |
| 2 | `infra/docker/compose.ci.yaml` — CI 전용 오버라이드(빌드 캐시 `cache_from`/`cache_to` 는 bake 가 `--set` 으로 넣으므로 여기는 태그·`pull_policy` 정도). 로컬 compose 에 영향 없음 | A (W) |
| 3 | 로컬 실측: `scripts/smoke.sh` 단독 시간, `--bench` 의 P50·P95·max → `.harness/smoke-bench.json`(루트 `.gitignore` 에 추가). 그리고 `harness.config` 후보(부록 B)를 **`bash -c` 로 실제 실행**해 exit 0 확인(improvement-log 014). 기록을 사람에게 넘김 | A |
| 4 | `./harness/scripts/improvement-log.sh new` 로 1건: D-15(단계 상한 10 → 11)의 근거와 회귀 조건 — EI-2 상 사람 결정의 기록. H-5 의 준비물 | A |
| 5a | **H-6 먼저**: `.github/workflows/harness.yml`(부록 C — `docker/setup-buildx-action`, `buildx bake … type=gha`, `SMOKE_NO_BUILD=1`). 별도 `harness-change` PR. 옛 `harness.config`(16단계) 아래에서 빌드만 추가되므로 CI 가 녹색이어야 함 — 빌드 시간을 여기서 처음 측정 | **H** |
| 5b | **H-5 다음**: `harness.config`(부록 B — `smoke` 행 추가, 17단계). 별도 `harness-change` PR. 순서가 이래야 하는 이유는 Phase 0 의 H-2b → H-2a 와 같습니다 — PR 의 CI 는 PR 의 config 를 PR 의 workflow 로 돌립니다 | **H** |
| 5c | **H-4b**: `.importlinter` 의 `unmatched_ignore_imports_alerting` `warn` → `error`(부록 A 의 둘째 diff). 별도 PR. P1-3 의 어댑터가 있어 ignore 가 매칭됩니다 | **H** |
| 5d | **H-7**: `evaluation/README.md` 의 `{{성능_기준}}` 행에 3번의 실측을 보고 **사람이 값을 적음**(환경 이름 포함, 부록 D). 별도 PR. 값은 에이전트가 제안하지 않습니다 | **H** |
| 6 | 판정: `./harness/scripts/verify.sh` pass, `verify.json` 에 17단계, `smoke` ≤ 240,000 ms, 합계 ≤ 600,000 ms(R-9). CI `verify` job ≤ 8분(D-15 회귀 조건). 넘으면 **사람에게 보고하고 spec 0002 2.11 의 (a) 로 회귀** — 그 판정도 사람 | A |

## 3. 사람 손

순간은 둘, 접촉은 다섯입니다 — H-4(착수 전), 그리고 P1-9 의 H-6 · H-5 · H-4b · H-7. 여기에 P1-3 PR 리뷰의 태그 확인(Q6)과 **단위마다 PR 병합 한 번**이 더해집니다. 🔒 단위는 없습니다 — 인증에 닿는 변경은 이 Phase 에 없고, 생기면 그 단위를 🔒 로 표시하고 spec 을 [실질] 개정합니다.

| 순간 | 언제 | 사람이 하는 일 | 에이전트가 넘기는 것 |
| --- | --- | --- | --- |
| **H-4** | **wave 1 착수 전** | `.importlinter` — AR-5 에 `httpx` 금지 + model_gateway ignore, AR-7 확장(`aether_api → aether_runtime.application/adapters` 금지). `warn` 은 유지. `harness-change` PR | 부록 A 의 첫째 diff(scratchpad 후보). 현재 트리에서 `PYTHONUTF8=1 uv run lint-imports` 가 후보로 통과함을 확인한 기록 |
| **Q6 확인** | P1-3 의 PR 리뷰 | Ollama 태그 `qwen3.8:27b` 실재 확인. 없으면 대체 태그 결정 | `.env.example` 의 값과 확인 URL |
| **H-6** | P1-9 의 5a (**먼저**) | `harness.yml` 에 buildx + bake 캐시 + `SMOKE_NO_BUILD`. `harness-change` PR | 부록 C(scratchpad 후보). 액션 버전 실재 확인(refs/tags 조회 — improvement-log 015) |
| **H-5** | P1-9 의 5b (**다음**) | `harness.config` 에 `smoke` 행. 17단계. `harness-change` PR | 부록 B(scratchpad 후보). `bash -c` 실행 확인, 로컬 실측(`smoke` 단독·합계), improvement-log id(4번) |
| **H-4b** | P1-9 의 5c | `.importlinter` `warn` → `error` | 부록 A 의 둘째 diff. 어댑터가 있는 트리에서 후보로 `lint-imports` 통과 기록 |
| **H-7** | P1-9 의 5d | `evaluation/README.md` 의 `{{성능_기준}}` 값 | `.harness/smoke-bench.json` 과 환경 정보. 값 제안 없음 |

H-4 를 선행 조건으로 두는 이유는 Phase 0 의 H-1 과 같습니다 — 단위 안에 두면 세션이 사람을 기다리며 멈춥니다. `.importlinter` 는 이번에 두 번 바뀌지만 둘 다 한 줄짜리이고, 한 번에 합치려면 `error` 가 어댑터 없는 트리에서 실패하므로 나눌 수밖에 없습니다.

## 4. 판정 절차

**전 단위 공통.** 게이트가 켜져 있습니다. `TESTCONTAINERS_RYUK_DISABLED=true ./harness/scripts/verify.sh` 하나가 판정이고, 완료 보고에는 `.harness/verify.json` 경로와 실패 단계의 `log` 경로를 붙입니다. H-5 전까지는 16단계, 뒤로는 17단계입니다.

**단위별 추가 확인**(verify 가 아직 못 보는 것 — 보고에 "손으로 실행" 으로 적고, 실행하지 않았으면 "미측정"):

| 단위 | 추가 확인 |
| --- | --- |
| P1-2 | `uv run pytest -q -m 'not integration' --disable-socket` 통과(H-5 전까지 `api-unit` 명령에 없음) |
| P1-3 | `PYTHONUTF8=1 uv run lint-imports` 의 kept 수가 H-4 뒤 기준과 같음 |
| P1-5 | compose `up` 뒤 `worker` healthy. `docker compose exec api aether-api keys create` 로 키를 얻어 Run 하나를 손으로 `succeeded` 까지 |
| P1-8 | 위 Run 의 `trace_id` 가 `.harness/otel/spans.jsonl` 에 있음 |
| P1-9 | `scripts/smoke.sh` 단독 exit 0 — H-5 전에 손으로, 뒤에는 verify 가 |

**보고에 반드시**: `red 증거`(실패 출력과 오류 종류 — 기대한 원인인지, improvement-log 016), 실행한 판정 명령 exit 표, 미측정, spec/plan 과의 불일치.

## 5. 예산과 중단

[../AGENTS.md](../AGENTS.md) Loop 와 plan 0001 5절을 그대로 씁니다. 다른 것만 적습니다.

| 항목 | 값 |
| --- | --- |
| 단위당 반복 | 최대 8회. 같은 실패 3회 또는 개선 없는 2라운드면 중단 |
| 쪼개기 | 8회 안에 안 끝나면 쪼갭니다 — P1-2 는 2a/2b(2절), P1-5 는 5a(api)/5b(worker). 예산을 늘리지 않습니다 |
| 브랜치·PR | 단위 하나 = `p1-n-<slug>` 브랜치 하나 = PR 하나. `Unit: P1-n` trailer. 사람이 병합 |
| 보호 파일 | 후보는 scratchpad 에, 사람이 `cp` 하고 `harness-change` 라벨. 한 PR 에 보호 파일 하나 |
| 새 `.sh` | `git update-index --chmod=+x`(`scripts/smoke.sh`) |
| 범위 밖 파일 | 한 단위가 다른 단위의 파일을 고치고 싶어지면 멈추고 보고. 예외: P1-6 이 P1-5 의 `EventSink` 세부(explicit ID·MAXLEN)를 맞추는 것은 2절에 적힌 대로 허용 |
| Docker | P1-5 이후 통합 테스트가 PG + Redis 컨테이너 둘을 띄웁니다. 세션당 하나씩(`scope="session"`) |
| 시간 예산 | verify 합계 10분(D-12). P1-9 에서 넘으면 (a) 회귀 — 사람 결정 |

## 6. Phase 완료

spec 0002 의 R 전부가 어느 단위에서 판정되는지입니다(spec 5절과 같음 — 여기는 판정 시점만 더합니다).

| R | 판정 단위 | 판정 시점 |
| --- | --- | --- |
| R-1 | P1-1 | `api-integration`, `test_openapi_drift` |
| R-2 | P1-5 (+P1-2, P1-4) | `api-integration` e2e, `smoke` |
| R-3 | P1-6 | `api-integration` SSE 순서·단절 |
| R-4 | P1-7 | `api-unit` `FakeClock` |
| R-5 | P1-4, P1-8 | `api-unit` `Tracer` 트리, `smoke` collector 파일 |
| R-6 | P1-3 | `api-unit --disable-socket`, `MockTransport` |
| R-7 | P1-3 (+H-4) | `tests/arch/test_real_importlinter_fires.py` |
| R-8 | P1-1, P1-5, P1-6 | `test_routes_require_auth.py` |
| R-9 | P1-9 | `verify.json` 17단계, 시간 |
| R-10 | P1-9 (H-7) | evaluation/README 의 값 |
| R-11 | P1-2 | `test_no_sleep_in_tests.py` |
| R-12 | P1-1, P1-6 | 두 드리프트 테스트 |
| R-13 | P1-5 | worker healthy, TTL 테스트 |
| R-14 | P1-4 | `test_observation_boundary.py` |
| R-15 | P1-2, P1-4 | `test_lease.py`, `test_resume.py` |
| R-16 | P1-4, P1-5 | `test_resume.py` 재발행 |

**끝났을 때 갱신할 문서**

- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — P1-1 ~ P1-9 `완료`. Phase 2 의 intent 0003 을 발급하고 `Intent:` 를 링크로
- [../intents/intent.md](../intents/intent.md) — 활성 intent 를 0003 으로. 사슬의 `지금` 열
- [../intents/0002-phase-1-agent-runtime.md](../intents/0002-phase-1-agent-runtime.md) — 상태 `완료`
- [../docs/roadmap.md](../docs/roadmap.md) — 현재 위치를 Phase 1 완료로. 성숙도 L2(REP 기준선이 생겼으면)
- [../docs/architecture.md](../docs/architecture.md) 6절 — `packages/runtime` 이 채워졌음. AR-5·AR-7 이 실효
- `docs/api.md`(P1-1·P1-5·P1-6 이 만듦 — 지금은 없어 링크하지 않습니다) — Phase 1 의 경로·스트림·이벤트 계약. [../docs/README.md](../docs/README.md) 의 "아직 없는 문서" 행 제거
- [../docs/data-model.md](../docs/data-model.md) — P1-2 가 갱신(마이그레이션 0002)
- [../evaluation/README.md](../evaluation/README.md)(보호) — REP-2 · REP-4 · REP-8 실행 가능, `{{성능_기준}}` 값(H-7 에서 이미). 사람
- [../CLAUDE.md](../CLAUDE.md) "아직 없는 것" — Phase 2 의 것으로 교체(대체할 항목과 함께)
- [../AGENTS.md](../AGENTS.md) 첫 문단 — Phase 1 완료
- [../PROVENANCE.md](../PROVENANCE.md) 8절 — 이력 한 줄
- [../DESIGN.md](../DESIGN.md) — 변경 없음(web 화면 없음). 확인만

---

## 부록 — 보호 파일 제안

에이전트가 만들 수 없는 파일의 **바꿀 부분**입니다. 제안이며, 도구가 첫 실행에서 거부하면 사람이 고쳐 커밋합니다. 그 수정은 이 plan 의 개정이 아닙니다. 버전에 따라 달라지는 부분은 `# 확인` 으로 표시했습니다. 각 후보는 에이전트가 scratchpad 에 파일로 뽑아 두고, 사람은 `cp` 뒤 `harness-change` PR 을 엽니다.

### A. `.importlinter` — 바꿀 부분 (H-4, H-4b)

**H-4 (착수 전).** AR-5 계약의 세 곳과 AR-7 계약 한 곳.

```ini
[importlinter:contract:ar5-llm-sdk-only-in-model-gateway]
name = AR-5 LLM SDKs and LLM HTTP only inside aether_runtime.adapters.outbound.model_gateway
type = forbidden
source_modules =
    (그대로)
forbidden_modules =
    openai
    anthropic
    google
    httpx
ignore_imports =
    aether_runtime.adapters.outbound.model_gateway.** -> openai
    aether_runtime.adapters.outbound.model_gateway.** -> anthropic
    aether_runtime.adapters.outbound.model_gateway.** -> google
    aether_runtime.adapters.outbound.model_gateway.** -> httpx
unmatched_ignore_imports_alerting = warn
# H-4b(P1-9)에서 error 로. 그 전에는 어댑터가 없어 ignore 가 매칭되지 않습니다.

[importlinter:contract:ar7-control-does-not-call-data]
name = AR-7 api must not import worker, nor runtime execution layers
type = forbidden
source_modules =
    aether_api
forbidden_modules =
    aether_worker
    aether_runtime.application
    aether_runtime.adapters
# aether_runtime.domain 은 허용(spec 0002 2.1 — AgentDefinition, RunStatus, 이벤트 타입).
```

**H-4b (P1-9).** 한 줄.

```ini
unmatched_ignore_imports_alerting = error
```

### B. `harness.config` — 바꿀 부분 (H-5)

`HARNESS_STEPS` 의 마지막 원소 뒤에 한 행. 배열 원소는 큰따옴표 문자열이므로 명령 안에 큰따옴표를 쓰지 않습니다.

```bash
  "api-integration|correctness|true|uv run pytest -q -m integration"
  "smoke|behavior|true|scripts/smoke.sh"
```

`api-unit` 행은 `--disable-socket` 을 더합니다(D-18, R-6):

```bash
  "api-unit|correctness|true|uv run pytest -q -m 'not integration' --disable-socket"
```

주석 블록의 "제품 단계 10개" 문구를 "11개(spec 0001 개정 12)" 로. `HARNESS_THRESHOLD`·가중치는 그대로.

### C. `.github/workflows/harness.yml` — 바꿀 부분 (H-6)

`verify` job 의 `pnpm install` 뒤, `하네스 검증` 앞에.

```yaml
      # spec 0002 2.11: smoke 가 쓰는 이미지를 bake 로 먼저 만들어 GitHub Actions 캐시를 씁니다.
      # compose 의 cache_from 한 줄로는 되지 않습니다(리뷰 F-11). smoke.sh 는 SMOKE_NO_BUILD=1 로
      # 이 이미지를 그대로 씁니다. 버전은 2026-09-12 기준 — 확인: 병합 전 refs/tags 조회.
      - uses: docker/setup-buildx-action@v3   # 확인
      - name: 이미지 빌드 (bake, gha 캐시)
        run: >
          docker buildx bake
          -f infra/docker/compose.yaml -f infra/docker/compose.ci.yaml
          --set '*.cache-from=type=gha' --set '*.cache-to=type=gha,mode=max'
          --load
      - name: 하네스 검증
        env:
          SMOKE_NO_BUILD: "1"
        run: ./harness/scripts/verify.sh
```

`bake` 가 compose 파일의 `build` 블록을 읽으려면 서비스에 `image:` 이름이 있어야 합니다 — `compose.ci.yaml`(A)이 그것을 줍니다. `ACTIONS_RUNTIME_TOKEN` 노출이 필요한 버전이면 `crazy-max/ghaction-github-runtime`(확인)을 앞에 둡니다.

### D. `evaluation/README.md` — 바꿀 부분 (H-7)

자리표시자 표의 한 행. 값은 사람이 `.harness/smoke-bench.json` 을 보고 적습니다 — 아래는 **형식**만입니다.

```markdown
| `{{성능_기준}}` | Run 생성 응답 P95 ≤ <값> ms — 환경 <머신/OS/Docker>, fake 어댑터, 순차 200회(워밍업 20 제외), 2026-<월>-<일> 실측(spec 0002 2.13, D-8). 넘으면 REP-8 실패 |
```

그리고 "지금 이 세트의 상태" 표의 `Phase 1 완료` 행을 도달 사실로.

## 관련 문서

- [../specs/0002-phase-1-agent-runtime.md](../specs/0002-phase-1-agent-runtime.md) — 근거 spec
- [../intents/0002-phase-1-agent-runtime.md](../intents/0002-phase-1-agent-runtime.md) — 근거 intent
- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — P1-1 ~ P1-9 와 상태
- [0001-phase-0-foundation.md](0001-phase-0-foundation.md) — 같은 절 구성, 5절 예산의 원문
- [../AGENTS.md](../AGENTS.md) — Loop, 위임, PR 게이트
- [../.claude/agents/implementer.md](../.claude/agents/implementer.md) — 구현 세션의 역할과 보고 형식
- [README.md](README.md) — plan 의 규칙
