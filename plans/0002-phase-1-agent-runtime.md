# Plan 0002 — Phase 1: Agent Runtime

| 키 | 값 |
| --- | --- |
| 번호 | 0002 |
| 근거 spec | [../specs/0002-phase-1-agent-runtime.md](../specs/0002-phase-1-agent-runtime.md) (승인됨 2026-09-12, D-1 ~ D-19. 개정 1·2 는 이 plan 의 리뷰에서) |
| 근거 intent | [../intents/0002-phase-1-agent-runtime.md](../intents/0002-phase-1-agent-runtime.md) |
| 작업 단위 | [../intents/mvp-backlog.md](../intents/mvp-backlog.md) P1-1 ~ P1-9 (P1-2 → 2a·2b, P1-5 → 5a·5b 로 분할) |
| 작성일 | 2026-09-12 |
| 상태 | 승인됨 |
| 승인 | showjihyun, 2026-09-12 (리뷰 F-1 ~ F-19 반영본. 순서 5 wave·11 단위, 사람 손 두 순간 네 접촉 + Q6 확인에 동의. spec 0002 개정 1 [실질] 도 이 승인으로 확정) |
| 개정 | — (실행 중 갱신: P1-2a 순서 2 의 conftest 배치를 실제대로 — 개정으로 세지 않음) |

spec 이 정한 요구사항(R-1 ~ R-16)·결정(D-1 ~ D-19)·계약은 반복하지 않습니다. 이 문서는 열한 단위를 어떤 순서로 하고, 단위마다 어느 파일을 누가 만들며, 무엇으로 판정하는지를 정합니다. 표기 — **A** 에이전트(`implementer`, Sonnet 5), **M** 주 세션(`docs/`·backlog·spec·plan — implementer 는 `docs/` 를 고칠 수 없습니다), **H** 사람(보호 파일, spec 0001 C-1), **W** 가드가 경고만 내는 파일.

이 plan 이 풀어야 하는 문제는 셋입니다.

1. **보호 파일 변경이 네 곳**(spec 0002 C-9) — `.importlinter`, `harness.config`, `harness.yml`, `evaluation/README.md`. 사람 손을 **두 순간**으로 묶습니다: P1-3 병합 직후(H-4)와 P1-9(H-6 · H-5 · H-7). 접촉 넷.
2. **`.importlinter` 는 한 번만 바꿉니다.** import-linter 는 `ignore_imports` 의 **각 줄**이 실제 import 와 매칭되어야 `unmatched_ignore_imports_alerting = error` 를 통과합니다. 벤더 SDK(`openai`·`anthropic`·`google`) 어댑터는 Phase 1 에 없으므로 그 세 ignore 줄은 삭제하고, `httpx` ignore 는 P1-3 의 어댑터가 생긴 뒤에 넣어야 매칭됩니다. 그래서 H-4 는 **P1-3 병합 뒤, P1-1 착수 전** 한 번입니다(부록 A). R-7 의 "실제 `.importlinter` 가 `httpx` 를 잡는다" 테스트는 그 뒤인 P1-1 에서.
3. **테스트 도구 설정은 실험으로 확인한 조합만 씁니다.** `--import-mode=importlib` 는 기존 `from fakes import …` 를 깨고, 기본 모드는 두 `fakes.py` 중 하나를 잘못 import 하며, `explicit_package_bases` 만 넣으면 src 레이아웃의 모듈 이름이 갈라집니다. 동작하는 조합 — pytest `pythonpath = ["."]`(기본 prepend), mypy `explicit_package_bases = true` + `mypy_path` 에 9개 `src`, 테스트는 네임스페이스 경로로 import(`from apps.api.tests.fakes import …`). spec 0002 개정 1 이 D-18 을 이렇게 고칩니다.

## 1. 순서

의존 그래프(backlog 의 `의존` 열)와 spec 2.1 의 배치에서 유도했습니다. **세션 하나에 단위 하나**이고, 병렬로 적은 곳도 실제로는 차례로 갑니다. 판정은 모델과 무관하게 4절의 명령입니다.

| Wave | 단위 | 왜 이 자리인가 | 사람 손 |
| --- | --- | --- | --- |
| 1 | **P1-2a** 테스트 도구 · 마이그레이션 0002 · 의존성 | 이후 모든 단위가 이 설정 아래에서 작성됩니다. `packages/runtime/tests` 가 처음 생기기 전에 mypy·pytest 설정이 있어야 하고, 마이그레이션 0002 는 spec 2.10 을 **한 번에** 담아 뒤 단위가 열을 기다리지 않게 합니다 | — |
| 1 | **P1-2b** Run 도메인 · lease · `RunStateStore` | 순수 도메인 + 저장소 계약. `AgentDefinition`·`BUILTIN_TOOL_NAMES` 도 여기 — P1-1 과 P1-4 둘 다의 선행입니다 | — |
| 1 | **P1-3** Model gateway | P1-2b 뒤 **순차**(같은 `pyproject`·`uv.lock`·`packages/runtime/tests` 를 만집니다). `httpx` 어댑터가 생기는 단위 | Q6 태그 확인은 PR 리뷰에서 |
| — | (경계) | `.importlinter` 한 번: `httpx` 금지 + `-> httpx` ignore, SDK ignore 셋 삭제, AR-7 확장, `error` | **H-4** |
| 2 | **P1-1** Agent Registry API | api 가 처음으로 `aether_runtime.domain` 을 import — H-4 의 AR-7 확장 아래에서. R-7 의 실제 `.importlinter` 테스트도 여기 | — |
| 2 | **P1-4** Planner/Executor 루프 | P1-2b(상태 기계·lease·정의)와 P1-3(gateway) 위에. `Tracer` 포트·인메모리 구현도 여기 | — |
| 3 | **P1-5a** worker 실행 경로 | P1-4 의 `ExecuteRun` 을 worker 가 부릅니다. runtime 의 Redis·DB 어댑터, heartbeat, compose worker 설정 | — |
| 3 | **P1-5b** Run API · 투영 · e2e | api 의 선언·조회·취소·투영 소비자. P1-5a 와 합쳐 R-2 의 e2e | — |
| 4 | **P1-6** Streaming | P1-5 의 이벤트 스트림을 읽는 쪽. sdk 의 SSE 파서 | — |
| 4 | **P1-7** Retry / Timeout / Error | 루프(P1-4)에 정책을 꽂는 일. P1-6 과 순서 무관 | — |
| 4 | **P1-8** Trace | `Tracer` 의 OTel 구현, `traceparent` 전파, collector 서비스 | — |
| 5 | **P1-9** smoke · 성능 기준 · 보호 파일 셋 | 전부가 있어야 e2e 가 성립. 사람 손 세 접촉 | **H-6 → H-5, H-7** |

P1-2a·2b 를 P1-1 보다 앞에 둔 것은 의도입니다(backlog 번호 순서와 다름). 도구 설정·마이그레이션·도메인 타입이 먼저 있어야 이후 단위가 그 아래에서 작성됩니다 — Phase 0 에서 P0-6 을 앞당긴 이유와 같습니다.

## 2. 단위별 계획

모든 단위는 **red(실패하는 테스트, 실행해 기록) → green → refactor(테스트 불변)** 순서이고, 보고의 `red 증거` 칸이 그것을 증명합니다 — 실패 원인이 기대한 원인인지도 적습니다(improvement-log 016). 테스트 docstring 은 `spec 0002 R-n`·`D-n`·`AR-n` 을 인용합니다. 단위마다 브랜치 하나(`p1-2a-tooling`), PR 하나, 커밋 trailer `Unit: P1-2a`. 유스케이스는 **평탄 배치** `application/usecases/<이름>.py` 와 `test_<이름>.py` 1:1 입니다 — `tests/arch/test_usecases_have_tests.py` 의 glob 이 비재귀이기 때문입니다(P0-9 와 같은 관례).

### P1-2a 테스트 도구, 마이그레이션 0002, 의존성

설정 단위라 일부는 테스트 우선이 성립하지 않습니다. red 가 성립하는 곳(3·4번)은 그대로 적용합니다.

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | 루트 `pyproject.toml` — `[tool.pytest.ini_options] pythonpath = ["."]`, `addopts = "--disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1"`(R-6. 단독 `--disable-socket` 은 `TestClient` 의 이벤트 루프가 `socketpair` 를 만들어 9건이 깨집니다 — 확인함); `[tool.mypy] explicit_package_bases = true`, `mypy_path = ["apps/api/src", "apps/worker/src", "packages/runtime/src", …(9개 src)]`(이것이 없으면 src 레이아웃 모듈이 `apps.api.src.aether_api.*` 로 갈라져 `import-untyped` 67건 — 확인함); dev 그룹에 `pytest-socket`. `packages/runtime/pyproject.toml` 에 `pydantic`, `psycopg[binary]`, `redis`. `uv sync --all-packages` → `uv.lock` | A (W) |
| 2 | 루트 `conftest.py` — `pytest_collection_modifyitems` 로 `integration` 마커 항목에 `enable_socket` 부여(컨테이너 테스트는 실제 소켓). `tests/__init__.py`, `tests/support/__init__.py`, `tests/support/pg.py`(현재 `apps/api/tests/conftest.py` 의 PostgreSQL 세션 fixture — 컨테이너·역할·`alembic upgrade`·세 접속 팩토리 — 를 **옮김**. 등록은 **루트 `conftest.py`** 의 `pytest_plugins = ["tests.support.pg"]` — pytest 9 는 top-level 이 아닌 conftest 의 `pytest_plugins` 를 거부해 `apps/api/tests/conftest.py` 는 **삭제**(실행 중 확인, spec 개정 3)), `tests/support/waiting.py`(`wait_until(predicate, timeout, interval)` — `Event.wait` 폴링). 기존 4개 테스트 파일의 `from fakes import …` 를 `from apps.api.tests.fakes import …` 로(네임스페이스 경로. `pythonpath = ["."]` 로 import 가능 — 확인함) | A (W) |
| 3 | **red** — `tests/arch/test_no_sleep_in_tests.py`(R-11. **`ast`** 로 `Call` 노드의 `time.sleep`/`asyncio.sleep`/`sleep` 바인딩 검사 — grep 은 docstring 의 `time.sleep` 에 오탐, `import … as` 에 누락). 지금 2곳이 걸려 red: `apps/api/tests/test_api_key_store_contract.py:123`, `apps/worker/tests/test_connect.py:53`. 실행해 실패 기록 | A |
| 4 | **green(3)** — `apps/api/tests/fakes.py` 의 `FakeApiKeyStore` 에 `clock` 주입(테스트 파일). PostgreSQL 쪽 "두 번째 revoke 가 `revoked_at` 유지" 는 **프로덕션 무변경**으로: 첫 revoke 뒤 관리자 연결로 `revoked_at = now() - interval '1 hour'` 를 심고 두 번째 revoke 뒤 그 값이 유지됨을 단언(`PostgresApiKeyStore.revoke` 는 SQL `COALESCE(revoked_at, now())` 라 시계 주입이 불가하고, 어댑터 시그니처 변경은 🔒 인증 코드에 닿습니다). `test_connect.py` 는 `Event.wait`. 판정에 "`apps/api/src/aether_api/` 무변경(`git diff --stat`)" | A |
| 5 | **red** — 기존 `test_migrations.py`(왕복)·`test_plane_roles.py` 에 케이스 추가: `aether_control` 이 `data.run_states` 에 접근하면 permission denied, `control.agents.current_version` 기본 1, `data.run_executions` 에 `lease_owner`·`lease_until` 열. 마이그레이션이 없어 red | A |
| 6 | **green(5)** — `apps/api/migrations/versions/0002_phase1_runs_lease_states.py`: spec 2.10 전부. `downgrade` 전부 되돌림 | A |
| 7 | `docs/data-model.md` — 새 열·테이블·lease 의미·cross-schema FK 하나 추가(4절). implementer 보고의 "사람에게 넘길 것" 에 열 표 초안을 싣고 주 세션이 옮깁니다 | **M** |
| 8 | **refactor**. 판정: `verify.sh` 16단계 pass(이제 `api-unit` 은 `addopts` 로 소켓 차단 상태에서 돕니다). `uv run mypy` 0. `red 증거` 에 3·5 의 실패 출력 | A |

### P1-2b Run 도메인, lease, `RunStateStore`

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | **red** — `packages/runtime/tests/`: `conftest.py`(`pytest_plugins = ["tests.support.pg"]`), `fakes.py`(`FakeRunStateStore`, `FakeClock` — import 는 `from packages.runtime.tests.fakes import …`), `test_run_state_machine.py`(전이표 전부: 허용 전이, 불허 → `IllegalTransition`, 종결에서 나가는 전이 0건), `test_run_state.py`(`RunState` 직렬화 왕복, `seq` 단조), `test_agent_definition.py`(spec 2.3 검증 규칙 전부 — `schema_version` 아닌 값, 빈 `system_prompt`, `BUILTIN_TOOL_NAMES` 밖 도구, 범위 밖 정책 값), `test_lease.py`(R-15: 유효 lease → `acquire_lease` 실패, 만료 → 성공, `renew`·`release`), `test_run_state_store_contract.py`(**포트 계약** — fake 와 PostgreSQL 에 같은 케이스: `save`/`load` 왕복, lease 조건부 UPDATE 원자성, 없는 run → `None`, **새 store 인스턴스가 같은 `RunState` 를 load**(재개의 저장소 절반 — 유스케이스 절반은 P1-4 `test_resume.py`). PostgreSQL 은 `integration`, `aether_data`). 실행해 실패 기록 | A |
| 2 | **green** — `aether_runtime/domain/{run,task,failure,agent,tools}.py`(`RunStatus`, `transition`, `RunState`, `IllegalTransition`, `LeaseHeld`, `Task`, `FailureReason`, `AgentDefinition`, `BUILTIN_TOOL_NAMES`·`ToolCall`·`ToolResult`), `application/ports/outbound/{run_state_store,clock}.py`(`Clock` 은 `now`·`monotonic`·`sleep`), `adapters/outbound/db/run_state_store.py`(lease 는 `UPDATE … WHERE lease_until IS NULL OR lease_until < now() RETURNING` 한 문장 — DB 시계 하나만) | A |
| 3 | **refactor**. 판정: `verify.sh` pass. `packages/runtime` 의 `domain`·`application` 이 `psycopg`·`redis` 를 import 하지 않음(`api-arch` AR-9). backlog P1-2 완료 판정의 "죽였다 살려도 같은 State 에서 재개" 는 **P1-4 의 `test_resume.py` 에서 완결**됨을 P1-2b 완료 보고와 backlog 상태 갱신에 적습니다 | A / M |

### P1-3 Model gateway 와 첫 어댑터

P1-2b 병합 뒤 분기합니다. H-4 는 이 단위 **뒤**이므로 이 단위의 판정에 실제 `.importlinter` 의 `httpx` 발화는 없습니다(P1-1 로).

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `packages/runtime/pyproject.toml` 에 `httpx`. `uv sync --all-packages` | A (W) |
| 2 | **red** — `packages/runtime/tests/test_model_gateway_contract.py`(fake 와 OpenAI-호환에 같은 케이스: 텍스트 응답, `tool_calls[].id` 보존, `tool` 메시지의 `tool_call_id` 전송, **tools + stream 동시** 청크 파싱, `reasoning_content` 분리, `think: false` 옵션 전송, 5xx·타임아웃 → `ModelError`, `embed` 왕복. OpenAI-호환은 `httpx.MockTransport`), `test_fake_model_gateway.py`(시나리오 주입). 실행해 실패 기록 | A |
| 3 | **green** — `application/ports/outbound/model_gateway.py`(`ModelRequest`·`ModelResponse`·`ModelDelta`·`ModelError`), `adapters/outbound/model_gateway/{fake,openai_compatible}.py`(`httpx` 는 이 디렉터리에만) | A |
| 4 | `infra/docker/compose.yaml` 에 `llm` 서비스(`profiles: ["llm"]`, Ollama 이미지 digest 고정, 모델 볼륨). `.env.example` 에 `AETHER_MODEL_ADAPTER=fake`, `AETHER_MODEL_BASE_URL`, `AETHER_MODEL_ID=qwen3.8:27b`, `AETHER_MODEL_API_KEY=<optional>`, `AETHER_MODEL_THINKING=false`. 루트 README 에 "실제 모델로 돌리기" 절(프로파일, `ollama pull qwen3.8:27b`, VRAM, 판정 대상이 아님) | A |
| 5 | **refactor**. 판정: `verify.sh` pass. 보고에 "`AETHER_MODEL_ID` 태그는 사람 확인 필요" | A |
| 6 | **PR 리뷰에서 사람이 확인**: Ollama 태그 `qwen3.8:27b` 실재(D-1). 없으면 대체 태그를 정해 `.env.example` 과 `improvement-log/` 에 | **H**(파일은 A) |

### H-4 (경계) — `.importlinter` 한 번

P1-3 병합 뒤, P1-1 착수 전. 부록 A. 에이전트는 현재 트리(어댑터 있음)에서 후보로 `PYTHONUTF8=1 uv run lint-imports` 가 `error` 설정으로 통과함을 확인해 기록을 넘깁니다.

### P1-1 Agent Registry API

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `apps/api/pyproject.toml` 에 `aether-runtime`(workspace), `redis`. `uv sync --all-packages` | A (W) |
| 2 | **계약 먼저**(DP-1, R-12) — 라우터 껍데기 `adapters/inbound/http/agents.py` 에 **최종 요청·응답 pydantic 모델과 `require_principal` 의존성을 포함**해 등록(본문은 `NotImplementedError`). `uv run aether-api openapi > packages/sdk/openapi.json`, `pnpm -F sdk run generate`, 커밋(같은 PR 의 첫 커밋). 껍데기는 red 이전에 쓰인 프로덕션 코드이므로 보고의 `red 증거` 에 그 사실을 적습니다 | A |
| 3 | **red** — `apps/api/tests/test_agents_api.py`(`integration`: 생성 201 → `GET /agents/{id}` → `PUT` → `current_version == 2` → `GET /agents/{id}/versions/1` 의 `definition` 동일(R-1); `409 agent_name_taken`; `404` 둘; 422 — `tools` 밖 이름, `schema_version: 2`), 유스케이스 단위 테스트 1:1 — `test_create_agent.py`, `test_list_agents.py`, `test_get_agent.py`, `test_get_agent_version.py`, `test_update_agent.py`(fake `AgentRepository`), `test_agent_version_concurrency.py`(`integration`: 스레드 둘이 동시 `PUT` → 하나는 200, 하나는 200 또는 409, 최종 `current_version == 3`, unique 위반 0건), `test_routes_require_auth.py`(R-8: `app.routes` 순회 401 — 예외 `/healthz`, `/openapi.json`, `/docs`, `/redoc`), `tests/arch/test_real_importlinter_fires.py`(R-7: `apps/*/src`·`packages/*/src` 만 임시 디렉터리에 복사하고 그 9개 경로를 **`PYTHONPATH` 앞**에 넣어(editable 설치의 `.pth` 보다 앞) `aether_api/_bad.py` 에 `import httpx` 와 `import aether_runtime.application` 을 주입 → `lint-imports --config <tmp>/.importlinter --no-cache` exit ≠ 0. 정상 트리 exit 0), `tests/arch/test_composition_only_in_main.py`(D-13 AR-10). 실행해 실패 기록 | A |
| 4 | **green** — `application/ports/inbound/agents.py`, `application/ports/outbound/agent_repository.py`, `application/usecases/{create_agent,list_agents,get_agent,get_agent_version,update_agent}.py`(`update_agent` 는 `lock_for_update(agent_id)` 안에서 `current_version + 1`), `adapters/outbound/db/agent_repository.py`(`SELECT … FOR UPDATE`, unique 위반 → `AgentVersionConflict`), `adapters/inbound/http/agents.py` 본문(**모듈 수준 라우터 + `build_agents_router(principal_dep)` 팩토리** — improvement-log 017 회피), `main.py` 조립 | A |
| 5 | `packages/sdk/src/client.ts` 에 `createAgent`·`listAgents`·`getAgent`·`getAgentVersion`·`updateAgent` + 테스트(fake fetch) | A |
| 6 | `docs/api.md` 시작(agents 5경로 표), `docs/README.md` 의 "아직 없는 문서" 행 제거. implementer 보고의 표 초안을 주 세션이 옮김 | **M** |
| 7 | **refactor**. 판정: `verify.sh` pass. `test_openapi_drift` 통과이고 **2번 커밋 대비 `packages/sdk/openapi.json` diff 0**. `web-typecheck` 생성물 드리프트 0 | A |

### P1-4 Planner/Executor 루프

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | **red** — `packages/runtime/tests/test_execute_run.py`(fake gateway·tools·store·`FakeClock`·인메모리 `Tracer`·fake `EventSink`·fake `StatusNotifier`: 도구를 부르는 시나리오 → `succeeded`, 부르지 않는 시나리오 → `succeeded`, `max_steps` 초과 → `failed(max_steps_exceeded)`, `unknown_tool`, cancel 관측 → `cancelled`, 전이 순서 == `run.status` 순서, `seq` 1 부터 연속), `test_observation_boundary.py`(R-14), `test_resume.py`(R-16·R-15: 종결 커밋 뒤 notifier 실패 → 두 번째 호출이 **같은 `seq` 로** 재발행 뒤 ack; `running` + lease 만료 → `RunState` 에서 이어감; lease 유효 → `LeaseHeld`), `test_tools.py`(`clock` 은 `Clock` 을 씀, `calculator` 는 `eval` 없이, 잘못된 식 → `is_error`), `test_tracer_tree.py`(R-5). **fake `EventSink` 는 Redis 의 "같은 ID 이하 재-XADD 거부" 를 모사하지 않고 계약대로 성공으로 취급**합니다 — 계약이 그렇게 정해졌기 때문(spec 개정 2, 2.7). 실행해 실패 기록 | A |
| 2 | **green** — `domain/observation.py`, `domain/events.py`(봉투·8종, `v: 1`), `application/ports/outbound/{tools,event_sink,status_notifier,tracer,run_declaration_reader}.py`(`EventSink.publish` 계약: 같은 `seq` 재발행은 성공), `application/ports/inbound/execute_run.py`, `application/usecases/execute_run.py`(spec 2.4 lease·재개·재발행 + 2.6 루프 — `complete` 만), `adapters/outbound/tools/{clock_tool,calculator,registry}.py`. 인메모리 `Tracer` 는 `packages/runtime/tests/fakes.py` | A |
| 3 | `tests/arch/test_usecases_have_tests.py` 가 `execute_run.py` 에 실제로 걸림. `BUILTIN_TOOL_NAMES == set(registry.names())` 단언 | A |
| 4 | **refactor**. 판정: `verify.sh` pass. AR-9(`domain`·`application` 에 `httpx`·`redis`·`psycopg`·`opentelemetry` 없음) | A |

### P1-5a worker 실행 경로

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `apps/worker/pyproject.toml` 에 `aether-runtime`, `psycopg[binary]`. `uv sync --all-packages` | A (W) |
| 2 | **red** — `apps/worker/tests/test_handle_run_requested.py`(fake `ExecuteRun`: 성공 → ack, `LeaseHeld` → ack 안 함, `traceparent` 복원), `test_requested_consumer.py`(`integration`: 자기 PEL 먼저(`XREADGROUP … 0`) → `XAUTOCLAIM` 순서, `count=1`, `min_idle_ms` 를 `Settings` 로 0 주입해 가로채기 경로 실행), `test_heartbeat.py`(`integration`, R-13: 키 TTL 갱신), `packages/runtime/tests/test_redis_adapters.py`(`integration`: `EventSink` 의 explicit ID `<seq>-0`·`MAXLEN`·TTL, **같은 ID 재-XADD 가 예외 없이 끝남**, `StatusNotifier` 의 필드(spec 2.18)), `test_run_declaration_reader.py`(`integration`: `aether_data` 로 `control.runs`·`agent_versions` 읽기). 실행해 실패 기록 | A |
| 3 | **green** — worker: `application/ports/inbound/handle_run_requested.py`, `application/usecases/handle_run_requested.py`, `adapters/inbound/stream/requested_consumer.py`(기존 `stream.py` 대체), `adapters/outbound/redis/heartbeat.py`, `settings.py`(`database_url`(`aether_data`), `worker_lease_seconds`, `worker_heartbeat_seconds`, `worker_consumer`, `worker_xautoclaim_min_idle_ms` 기본 3,900,000), `main.py` 조립(runtime `ExecuteRun` + PostgreSQL `RunStateStore`·`RunDeclarationReader` + Redis `EventSink`·`StatusNotifier` + no-op `Tracer`). runtime: `adapters/outbound/redis/{event_sink,status_notifier}.py`(`event_sink` 는 `ERR The ID specified in XADD is equal or smaller` 를 성공으로 흡수), `adapters/outbound/db/run_declaration_reader.py` | A |
| 4 | `infra/docker/compose.yaml` — worker 에 `AETHER_DATABASE_URL`(`aether_data`), healthcheck(`python -c` 하트비트 키), `depends_on`. `worker.Dockerfile` 주석 갱신. `.env.example` | A |
| 5 | **refactor**. 판정: `verify.sh` pass. compose `up` 뒤 `worker` healthy(손으로) | A |

### P1-5b Run API, 투영, e2e

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | **계약 먼저** — 껍데기(최종 모델·인증 포함)로 `openapi.json` 갱신(`POST /agents/{id}/run`, `GET /runs/{id}`, `POST /runs/{id}/cancel`), sdk 타입 생성, 커밋 | A |
| 2 | **red** — `apps/api/tests/test_runs_api.py`(`integration`: `POST run` 202 + `requested_by == 키 id` + `control.runs` 행 + `requested` 메시지에 `traceparent`; `GET` 은 `queued`; `cancel` 멱등; `404`), `test_request_run.py`·`test_get_run.py`·`test_cancel_run.py`·`test_apply_run_status.py`(fake 저장소. `ApplyRunStatus`: 낮은 `seq` 무시, 같은 `seq` 무시, 커밋 뒤 ack 순서), `test_run_end_to_end.py`(`integration`, R-2: api 앱 + worker `serve()` 스레드, fake gateway → `wait_until(succeeded)`; **cancel 시나리오의 fake 응답은 "tool_call 1회 뒤 최종"** — 취소는 반복 시작 시 관측되므로 다음 반복이 있어야 합니다. `Event` 로 도구 호출 사이에서 멈춰 세운 뒤 `cancel` → `cancelled`). 실행해 실패 기록 | A |
| 3 | **green** — `application/ports/inbound/{runs,apply_run_status}.py`, `application/ports/outbound/{run_declaration_store,run_notifier}.py`, `application/usecases/{request_run,get_run,cancel_run,apply_run_status}.py`(`request_run` — 커밋 뒤 XADD, XADD 실패 WARNING), `adapters/outbound/db/run_declaration_store.py`, `adapters/outbound/redis/run_notifier.py`, `adapters/inbound/http/runs.py`, `adapters/inbound/stream/status_consumer.py`(lifespan, group `aether-api`, 백오프, 붙지 못해도 HTTP 는 뜸), `settings.py` 에 `redis_url`, `main.py` | A |
| 4 | `infra/docker/compose.yaml` — api 에 `AETHER_REDIS_URL`. `packages/sdk` 에 `runAgent`·`getRun`·`cancelRun` + 테스트. 루트 README "Run 실행해 보기" | A |
| 5 | `docs/api.md` 에 runs 3경로와 스트림 계약 표(spec 2.18) | **M** |
| 6 | **refactor**. 판정: `verify.sh` pass. 껍데기 커밋 대비 `openapi.json` diff 0. compose 로 키 발급 → Run 하나 `succeeded`(손으로) | A |

### P1-6 Streaming

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `packages/sdk/package.json` 에 `json-schema-to-typescript`(bin `json2ts` — 확인함). `scripts.generate` 에 `json2ts -i events.schema.json -o src/generated/events.d.ts` 추가. `pnpm install` | A (W) |
| 2 | **계약 먼저** — `adapters/inbound/cli.py` 에 `events-schema`, `uv run aether-api events-schema > packages/sdk/events.schema.json`, 생성 타입 커밋. `GET /runs/{id}/events` 껍데기로 `openapi.json` 갱신 | A |
| 3 | **red** — `apps/api/tests/test_events_schema_drift.py`(R-12), `test_read_run_events.py`(fake 리더), `test_run_events_sse.py`(`integration`, R-3: 순서 == 전이, `id` 가 `seq`, `Last-Event-ID` 재개, 스트림 없음 + 종결 → 합성 `run.finished`, 소비자 단절 뒤 `wait_until(succeeded)`), `test_sse_route_is_async.py`(핸들러가 비동기 제너레이터). `packages/sdk/src/sse.test.ts`(청크 경계, 멀티라인 `data`, `id` 전달, `signal` 중단). 실행해 실패 기록 | A |
| 4 | **green** — `application/ports/inbound/read_run_events.py`, `application/ports/outbound/run_event_reader.py`, `application/usecases/read_run_events.py`, `adapters/outbound/redis/run_event_reader.py`(`redis.asyncio`, `XREAD BLOCK`), `adapters/inbound/http/events.py`. `packages/sdk/src/sse.ts`, `streamRunEvents` | A |
| 5 | `docs/api.md` 이벤트 절 | **M** |
| 6 | **refactor**. 판정: `verify.sh` pass. `web-typecheck` 드리프트 0(`events.d.ts` 포함) | A |

### P1-7 Retry / Timeout / Error Handling

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | **red** — `packages/runtime/tests/test_policy.py`(R-4: `FakeClock` 전진 → `timed_out`; 모델 재시도 소진 → `failed(model_error)`; 도구 → `tool_error`; 백오프가 `Clock.sleep` 인자로 관측(실제 대기 0); 잔여 시간이 모델 호출 타임아웃으로 전달; `definition_invalid`), `test_lease_renewal.py`(모델 호출 중 갱신 스레드, 갱신 실패 → 단계 뒤 `LeaseHeld` — spec C-13), `apps/api/tests/test_run_failure_projection.py`(`integration`: `failure_reason` 이 `GET /runs/{id}` 에). 실행해 실패 기록 | A |
| 2 | **green** — `application/usecases/execute_run.py` 에 정책·lease 갱신 적용(기존 테스트 불변), `domain/failure.py` 완성 | A |
| 3 | **refactor**. 판정: `verify.sh` pass. `test_no_sleep_in_tests.py` 0건 유지 | A |

### P1-8 Trace

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `packages/runtime/pyproject.toml` 에 `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`. `uv sync --all-packages` | A (W) |
| 2 | **red** — `packages/runtime/tests/test_otel_tracer.py`(`InMemorySpanExporter` 로 부모–자식·속성. 프롬프트·`reasoning` 속성 0건), `apps/api/tests/test_trace_propagation.py`(`integration`: `traceparent` 가 `requested` 메시지에, e2e 뒤 `GET /runs/{id}` 의 `trace_id` 가 그 trace 와 같음). 실행해 실패 기록 | A |
| 3 | **green** — `adapters/outbound/telemetry/otel_tracer.py`, worker `main.py` 가 no-op → OTel(`OTEL_EXPORTER_OTLP_ENDPOINT` 없으면 exporter 없음), api `request_run` 이 `traceparent` 실음, worker 복원, `trace_id` 를 `data.run_executions`·`StatusMessage` 에 | A |
| 4 | `infra/docker/compose.yaml` 에 `otel-collector`(contrib 이미지 digest 고정, `debug` + `file` exporter, host bind mount `${AETHER_OTEL_DIR:-./out/otel}` — **`.harness/` 아래가 아닙니다**: `.harness/*` 는 가드 보호 패턴이라 에이전트 명령이 막힐 수 있습니다), api·worker 에 `OTEL_EXPORTER_OTLP_ENDPOINT`. `infra/docker/otel-collector.yaml`. 루트 `.gitignore` 에 `infra/docker/out/`. README 에 collector 파일 위치 | A |
| 5 | **refactor**. 판정: `verify.sh` pass. 수동: Run 하나 → `infra/docker/out/otel/spans.jsonl` 에 `trace_id`(P1-9 가 자동화) | A |

### P1-9 smoke, 성능 기준, 보호 파일 셋

`red 증거` 는 착수 시점에 `scripts/smoke.sh` 가 없어 판정 명령이 실패함을 기록한 것으로 대신하고, 끝에 같은 명령의 성공을 기록합니다.

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `infra/docker/compose.ci.yaml` — `api`·`migrate` 에 **같은** `image: aether-api:ci`, `worker` 에 `image: aether-worker:ci`, `pull_policy: never`. bake 의 target 과 `up --no-build` 가 이 이름을 씁니다. 로컬 compose 에 영향 없음 | A (W) |
| 2 | `scripts/smoke.sh`(spec 2.11): `-p aether-smoke`, 임시 `.env`(랜덤, 실행 뒤 삭제), `AETHER_OTEL_DIR=./out/otel-smoke` 를 **`mkdir -p && chmod 0777`** 한 뒤(Linux CI 에서 Docker 가 root 소유로 만들면 uid 10001 collector 가 쓰지 못합니다) `up -d --wait postgres redis migrate otel-collector api worker`(web 제외). `SMOKE_NO_BUILD=1` 이면 `-f compose.ci.yaml` 을 더하고 `--no-build`, 아니면 `--build`. `keys create` → `POST /agents` → `POST run` → `succeeded` 폴링 60초 → `trace_id` 를 `out/otel-smoke/spans.jsonl` 에서 폴링 30초 → trap `down -v --remove-orphans`. `MSYS_NO_PATHCONV=1`, `exec -T`. `--bench` 는 spec 2.13(결과 `infra/docker/out/smoke-bench.json`). `git update-index --chmod=+x`. **C-12 확인**: `up --wait` 와 일회성 `migrate` 의 조합을 로컬(compose v2.29)에서 먼저 실행 — 실패하면 `migrate` 종료 코드와 healthcheck 를 직접 기다리는 경로 | A |
| 3 | 로컬 실측: `smoke.sh` 단독 시간, `--bench` 의 P50·P95·max. `harness.config` 후보(부록 B)를 **`bash -c` 로 실제 실행**해 exit 0(improvement-log 014). 기록을 사람에게 | A |
| 4 | `./harness/scripts/improvement-log.sh new` 1건: D-15(단계 상한 10 → 11)의 근거와 회귀 조건 — H-5 의 준비물 | A |
| 5a | **H-6 먼저**: `harness.yml`(부록 C — `docker/setup-buildx-action@v4`, `docker/bake-action@v6` 로 `api worker` 두 target 만 gha 캐시로, `SMOKE_NO_BUILD=1`). 별도 `harness-change` PR. 순서 근거는 Phase 0 와 **다릅니다** — H-5 를 먼저 병합해도 CI 는 `--build` 로 느리게 통과하지만, 캐시 없는 첫 실행이 8분 조건을 넘길 수 있어 캐시를 먼저 둡니다 | **H** |
| 5b | **H-5 다음**: `harness.config`(부록 B — `smoke` 행 한 줄, 17단계). 별도 `harness-change` PR | **H** |
| 5c | **H-7**: `evaluation/README.md` 의 `{{성능_기준}}` 값(부록 D). 별도 PR. 값은 에이전트가 제안하지 않습니다 | **H** |
| 6 | 판정: `verify.sh` pass, `verify.json` 17단계, `smoke` ≤ 240,000 ms, 합계 ≤ 600,000 ms(R-9). CI `verify` job ≤ 8분(D-15). 넘으면 사람에게 보고하고 spec 0002 2.11 의 (a) 로 회귀 — 그 판정도 사람 | A |

## 3. 사람 손

순간은 둘, 접촉은 넷입니다 — H-4(P1-3 병합 뒤), 그리고 P1-9 의 H-6 · H-5 · H-7. 여기에 P1-3 PR 리뷰의 태그 확인(Q6)과 **단위마다 PR 병합 한 번**이 더해집니다. 🔒 단위는 없지만, P1-2a 의 `sleep` 제거가 인증 어댑터에 닿지 않도록 프로덕션 무변경을 판정에 넣었습니다. 인증에 닿는 변경이 필요해지면 그 단위를 🔒 로 표시하고 spec 을 [실질] 개정합니다.

| 순간 | 언제 | 사람이 하는 일 | 에이전트가 넘기는 것 |
| --- | --- | --- | --- |
| **Q6 확인** | P1-3 의 PR 리뷰 | Ollama 태그 `qwen3.8:27b` 실재 확인. 없으면 대체 태그 결정 | `.env.example` 의 값과 확인 URL |
| **H-4** | **P1-3 병합 뒤, P1-1 착수 전** | `.importlinter` 한 번 — AR-5 에 `httpx` 금지 + `-> httpx` ignore, 벤더 SDK ignore 셋 삭제, `error`, AR-7 확장. `harness-change` PR | 부록 A(scratchpad 후보). 어댑터가 있는 트리에서 후보로 `lint-imports` 통과 기록 |
| **H-6** | P1-9 의 5a (**먼저**) | `harness.yml` 에 buildx + bake-action(gha 캐시, `api worker`) + `SMOKE_NO_BUILD`. `harness-change` PR | 부록 C(scratchpad 후보). 액션 태그 실재 확인 기록(refs/tags — 2026-09-12 확인: `setup-buildx-action@v4`, `bake-action@v6`) |
| **H-5** | P1-9 의 5b (**다음**) | `harness.config` 에 `smoke` 행. 17단계. `harness-change` PR | 부록 B(scratchpad 후보). `bash -c` 실행 확인, 로컬 실측, improvement-log id(4번) |
| **H-7** | P1-9 의 5c | `evaluation/README.md` 의 `{{성능_기준}}` 값 | `infra/docker/out/smoke-bench.json` 과 환경 정보. 값 제안 없음 |

H-4 를 P1-3 **뒤**에 두는 이유는 1절 문제 2 입니다. P1-3 이 끝나기 전에는 `httpx` ignore 가 매칭될 import 가 없어 `error` 가 실패하고, 벤더 SDK ignore 는 Phase 1 내내 매칭되지 않으므로 지금 삭제합니다. 그 사이(P1-2a ~ P1-3)에 `httpx` 를 잘못 import 할 수 있는 코드는 P1-3 의 어댑터뿐이고 그것이 허용 위치입니다.

## 4. 판정 절차

게이트가 켜져 있습니다. `TESTCONTAINERS_RYUK_DISABLED=true ./harness/scripts/verify.sh` 하나가 판정이고, 완료 보고에는 `.harness/verify.json` 경로와 실패 단계의 `log` 경로를 붙입니다. H-5 전까지 16단계, 뒤로는 17단계입니다. `api-unit` 의 소켓 차단은 P1-2a 부터 `pyproject.toml` `addopts` 로 걸리므로 `harness.config` 는 바뀌지 않습니다.

**단위별 추가 확인**(verify 가 아직 못 보는 것 — 보고에 "손으로 실행" 으로, 실행하지 않았으면 "미측정"):

| 단위 | 추가 확인 |
| --- | --- |
| P1-2a | `git diff --stat apps/api/src` 비어 있음(🔒 무변경). `uv run mypy` 가 `apps.api.src…` 류 모듈 이름 오류 0건 |
| P1-3 | 보고에 태그 확인 요청 |
| P1-5a | compose `up` 뒤 `worker` healthy |
| P1-5b | compose 로 키 발급 → Run 하나 `succeeded` |
| P1-8 | 그 Run 의 `trace_id` 가 `infra/docker/out/otel/spans.jsonl` 에 |
| P1-9 | `scripts/smoke.sh` 단독 exit 0 — H-5 전에 손으로, 뒤에는 verify 가 |

**보고에 반드시**: `red 증거`(실패 출력과 오류 종류 — 기대한 원인인지), 실행한 판정 명령 exit 표, 미측정, spec/plan 과의 불일치, `docs/` 에 옮길 표 초안(M 항목이 있는 단위).

## 5. 예산과 중단

[../AGENTS.md](../AGENTS.md) Loop 와 plan 0001 5절을 그대로 씁니다. 다른 것만 적습니다.

| 항목 | 값 |
| --- | --- |
| 단위당 반복 | 최대 8회. 같은 실패 3회 또는 개선 없는 2라운드면 중단 |
| 쪼개기 | P1-2 와 P1-5 는 **처음부터** 2a/2b, 5a/5b 로 쪼갰습니다(backlog 에 행 추가). 그래도 8회 안에 안 끝나면 더 쪼갭니다. 예산을 늘리지 않습니다 |
| 브랜치·PR | 단위 하나 = `p1-<번호>-<slug>` 브랜치 하나 = PR 하나. `Unit: P1-<번호>` trailer. 사람이 병합 |
| 보호 파일 | 후보는 scratchpad 에, 사람이 `cp` 하고 `harness-change` 라벨. 한 PR 에 보호 파일 하나 |
| 새 `.sh` | `git update-index --chmod=+x`(`scripts/smoke.sh`) |
| 범위 밖 파일 | 다른 단위의 파일을 고치고 싶어지면 멈추고 보고. `docs/` 는 M — implementer 는 표 초안만 보고에 |
| Docker | P1-5 이후 통합 테스트가 PG + Redis 컨테이너 둘을 띄웁니다. 세션당 하나씩(`tests/support/pg.py`, Redis 는 같은 자리에 더함) |
| 시간 예산 | verify 합계 10분(D-12). P1-9 에서 넘으면 (a) 회귀 — 사람 결정 |

## 6. Phase 완료

spec 0002 의 R 전부가 어느 단위에서 판정되는지입니다.

| R | 판정 단위 | 판정 시점 |
| --- | --- | --- |
| R-1 | P1-1 | `api-integration`, `test_openapi_drift` |
| R-2 | P1-5b (+P1-2b, P1-4, P1-5a) | `api-integration` e2e, `smoke` |
| R-3 | P1-6 | `api-integration` SSE 순서·단절 |
| R-4 | P1-7 | `api-unit` `FakeClock` |
| R-5 | P1-4, P1-8 | `api-unit` `Tracer` 트리, `smoke` collector 파일 |
| R-6 | P1-2a, P1-3 | `addopts` 소켓 차단(loopback 만 허용), `MockTransport` |
| R-7 | P1-1 (+H-4) | `tests/arch/test_real_importlinter_fires.py` |
| R-8 | P1-1, P1-5b, P1-6 | `test_routes_require_auth.py` |
| R-9 | P1-9 | `verify.json` 17단계, 시간 |
| R-10 | P1-9 (H-7) | evaluation/README 의 값 |
| R-11 | P1-2a | `test_no_sleep_in_tests.py`(`ast`) |
| R-12 | P1-1, P1-5b, P1-6 | 드리프트 테스트 둘 + 껍데기 커밋 대비 diff 0 |
| R-13 | P1-5a | worker healthy, TTL 테스트 |
| R-14 | P1-4 | `test_observation_boundary.py` |
| R-15 | P1-2b, P1-4 | `test_lease.py`, `test_resume.py` |
| R-16 | P1-4, P1-5a | `test_resume.py` 재발행, Redis 재-XADD 흡수 |

**끝났을 때 갱신할 문서**

- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — P1-1 ~ P1-9(2a·2b·5a·5b 포함) `완료`. Phase 2 의 intent 0003 을 발급하고 `Intent:` 를 링크로
- [../intents/intent.md](../intents/intent.md) — 활성 intent 를 0003 으로. 사슬의 `지금` 열
- [../intents/0002-phase-1-agent-runtime.md](../intents/0002-phase-1-agent-runtime.md) — 상태 `완료`
- [../docs/roadmap.md](../docs/roadmap.md) — 현재 위치를 Phase 1 완료로. 성숙도 L2(REP 기준선이 생겼으면)
- [../docs/architecture.md](../docs/architecture.md) 6절 — `packages/runtime` 이 채워졌음. AR-5·AR-7 실효
- `docs/api.md`(P1-1·P1-5b·P1-6 에서 M 이 만듦 — 지금은 없어 링크하지 않습니다) — 경로·스트림·이벤트 계약. [../docs/README.md](../docs/README.md) 의 "아직 없는 문서" 행 제거
- [../docs/data-model.md](../docs/data-model.md) — P1-2a 에서 M 이 갱신
- [../evaluation/README.md](../evaluation/README.md)(보호) — REP-2 · REP-4 · REP-8 실행 가능, `{{성능_기준}}` 값(H-7). 사람
- [../CLAUDE.md](../CLAUDE.md) "아직 없는 것" — Phase 2 의 것으로 교체(대체할 항목과 함께)
- [../AGENTS.md](../AGENTS.md) 첫 문단 — Phase 1 완료
- [../PROVENANCE.md](../PROVENANCE.md) 8절 — 이력 한 줄
- [../DESIGN.md](../DESIGN.md) — 변경 없음(web 화면 없음). 확인만

---

## 부록 — 보호 파일 제안

에이전트가 만들 수 없는 파일의 **바꿀 부분**입니다. 제안이며, 도구가 첫 실행에서 거부하면 사람이 고쳐 커밋합니다. 그 수정은 이 plan 의 개정이 아닙니다. 버전에 따라 달라지는 부분은 `# 확인` 으로 표시했습니다. 각 후보는 에이전트가 scratchpad 에 파일로 뽑아 두고, 사람은 `cp` 뒤 `harness-change` PR 을 엽니다.

### A. `.importlinter` — 바꿀 부분 (H-4, 한 번)

AR-5 계약의 `forbidden_modules`·`ignore_imports`·alerting, AR-7 계약의 `forbidden_modules`.

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
    aether_runtime.adapters.outbound.model_gateway.** -> httpx
unmatched_ignore_imports_alerting = error
# 벤더 SDK(openai·anthropic·google)의 ignore 는 두지 않습니다 — Phase 1 에 그 어댑터가 없어
# 매칭되지 않고, error 는 매칭되지 않는 ignore 를 실패로 봅니다(import-linter contract_utils).
# SDK 어댑터가 생기는 Phase 에 그 줄을 다시 넣습니다. forbidden 은 그대로 걸립니다.

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

### B. `harness.config` — 바꿀 부분 (H-5)

`HARNESS_STEPS` 의 마지막 원소 뒤에 한 행. `api-unit` 은 바꾸지 않습니다(소켓 차단은 `pyproject.toml` `addopts`).

```bash
  "api-integration|correctness|true|uv run pytest -q -m integration"
  "smoke|behavior|true|scripts/smoke.sh"
```

주석 블록의 "제품 단계 10개" 문구를 "11개(spec 0001 개정 12)" 로. `HARNESS_THRESHOLD`·가중치는 그대로.

### C. `.github/workflows/harness.yml` — 바꿀 부분 (H-6)

`verify` job 의 `pnpm install` 뒤, `하네스 검증` 앞에. 태그는 2026-09-12 refs/tags 로 실재 확인 — 병합 전 다시 확인.

```yaml
      # spec 0002 2.11: smoke 가 쓰는 api·worker 이미지를 bake 로 먼저 만들어 GitHub Actions
      # 캐시를 씁니다(리뷰 F-11·F-13). web·migrate 는 target 에서 제외 — smoke 가 web 을 띄우지
      # 않고 migrate 는 api 와 같은 이미지(compose.ci.yaml 이 같은 image: 를 줌). smoke.sh 는
      # SMOKE_NO_BUILD=1 로 이 이미지를 그대로 씁니다.
      - uses: docker/setup-buildx-action@v4   # 확인: 2026-09-12 존재
      - uses: docker/bake-action@v6            # 확인: 2026-09-12 존재. ACTIONS_RUNTIME_TOKEN 노출을 대신합니다
        with:
          files: |
            infra/docker/compose.yaml
            infra/docker/compose.ci.yaml
          targets: api,worker
          load: true
          set: |
            *.cache-from=type=gha
            *.cache-to=type=gha,mode=max
      - name: 하네스 검증
        env:
          SMOKE_NO_BUILD: "1"
        run: ./harness/scripts/verify.sh
```

### D. `evaluation/README.md` — 바꿀 부분 (H-7)

자리표시자 표의 한 행. 값은 사람이 `infra/docker/out/smoke-bench.json` 을 보고 적습니다 — 아래는 **형식**만입니다.

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
