# Spec 0001 — Phase 0: Architecture & Foundation

| 키 | 값 |
| --- | --- |
| 번호 | 0001 |
| 근거 intent | [../intents/0001-phase-0-foundation.md](../intents/0001-phase-0-foundation.md) (승인됨 2026-09-08) |
| 작성일 | 2026-09-08 |
| 상태 | 검토 대기 |
| 승인 | (비어 있음 — 채워지기 전에는 plan 으로 넘어가지 않습니다) |
| 후속 plan | (생기면 `plans/0001-phase-0-foundation.md`) |
| 개정 | — |

intent 가 정한 문제·범위·제약은 여기서 반복하지 않습니다. 이 문서는 그 `Proposed Outcome` 다섯 개를 판정 가능한 요구사항으로 옮기고, 그것을 만족시키는 경계와 계약을 정하고, 사람이 내려야 할 결정을 한곳에 모읍니다. 작업 단위는 [../intents/mvp-backlog.md](../intents/mvp-backlog.md) 의 P0-1 ~ P0-9 이며, 이 spec 은 그 단위들이 공유하는 결정을 소유합니다.

## 1. 요구사항

판정 방법이 없는 요구사항은 요구사항이 아니므로, 모든 행에 판정을 붙였습니다.

| ID | 요구사항 | 유도 근거 | 판정 |
| --- | --- | --- | --- |
| R-1 | 깨끗한 checkout 에서 저장소 문서만 보고 찾은 **명령 하나**로 Web 과 API 가 뜹니다 | Outcome 1 | 루트 README 의 명령을 그대로 실행 → `GET /healthz` 200, web 첫 페이지 200. 명령까지의 발견 경로는 README 에서 두 홉 이내 |
| R-2 | `verify.sh` 한 번의 실행이 self-check 단계와 제품 단계를 함께 집계합니다 | Outcome 2 | `.harness/verify.json` 의 `steps[]` 에 `api-*` 와 `web-*` id 가 있고 전부 `pass` |
| R-3 | AR-1 ~ AR-5 가 기계 판정입니다. 위반을 넣으면 `architecture` 계층이 실패합니다 | Outcome 3 | 위반 fixture 로 `lint-imports` / `depcruise` 가 exit ≠ 0. 정상 코드에서 exit 0. 둘 다 테스트로 고정 |
| R-4 | 이미지를 빌드해 둔 뒤에는 인터넷 없이 `docker compose up` 이 성립합니다 | Outcome 4, DP-4 | egress 없는 네트워크에서 up → healthz 200, web 200. 부팅 경로의 외부 호출 0건 |
| R-5 | CI 가 깨끗한 checkout 에서 R-2 를 통과합니다 | Outcome 5 | `.github/workflows/harness.yml` 녹색 |
| R-6 | 비밀값이 코드·이미지·로그·커밋에 없습니다 | Constraints, Trust | `.env.example` 만 커밋. 이미지 layer 에 `.env` 없음. 가드의 security 패턴 적중 0건 |
| R-7 | Control Plane 은 Data Plane 을 호출하지 않고 선언만 합니다 | AR-7 | `aether_api` 의 import 그래프에 `aether_worker` 없음. api → worker 로 가는 HTTP/RPC 경로 없음. 저장소 권한이 2.8 의 역할 분리와 일치 |
| R-8 | `Agent` / `Agent Version` / `Run` 의 저장 모델이 [../docs/domain.md](../docs/domain.md) 1절과 같고, `Agent Version` 은 DB 수준에서 불변입니다 | backlog P0-8 | 마이그레이션 up/down 왕복. `agent_versions` UPDATE/DELETE 가 DB 에서 거부되는 테스트 |
| R-9 | 보호 경로는 인증 없이 401, `/healthz` 는 인증 없이 200 입니다 | Q4, DP-6 | 테스트 2건 |
| R-10 | 검증 게이트를 약화하지 않습니다 | Constraints, EI-1·EI-6 | 2.7 의 단계 표와 `harness.config` 가 같음. `required` 하향 0건. 임계값 변경은 `improvement-log/` 1건과 짝 |

## 2. 설계

### 2.1 저장소 구조

로드맵 Phase 0 의 트리를 그대로 씁니다. 각 항목에 언어·소유 계층·Phase 0 에서의 상태를 붙입니다. 계층 이름은 [../docs/architecture.md](../docs/architecture.md) 2절의 것입니다.

| 경로 | 언어 | 계층 | Phase 0 에서 |
| --- | --- | --- | --- |
| `apps/api` | Python | Control Plane | FastAPI. `/healthz`, 인증 기준선, 마이그레이션 소유. Agent Registry API 는 Phase 1 |
| `apps/worker` | Python | Data Plane (Agent Runtime 의 실행자) | Redis 큐에 붙어 대기. 처리 없음 |
| `apps/web` | TypeScript | Experience | Next.js. healthz 페이지 하나 |
| `packages/runtime` | Python | Agent Runtime + Model | 경계와 공개 인터페이스 자리만 |
| `packages/workflow` | Python | Agent Runtime | 경계만. Phase 4 |
| `packages/context` | Python | Context Engine | 경계만. Phase 3 |
| `packages/memory` | Python | Context Engine | 경계만. Phase 3 |
| `packages/mcp` | Python | MCP | 경계만. Phase 2 |
| `packages/policy` | Python | Trust | 경계만. Phase 2 에 판정 함수 |
| `packages/evaluation` | Python | Control Plane (제품 Evaluation) | 경계만. Phase 7. 하네스의 `evaluation/` 과 다른 것([../docs/domain.md](../docs/domain.md) 5절) |
| `packages/sdk` | TypeScript | Experience ↔ Control Plane 의 HTTP 계약 | `healthz()` 하나. 타입은 OpenAPI 에서 생성 |
| `infra/docker` | — | 배포 | `compose.yaml`, `compose.offline.yaml`, Dockerfile, `.env.example` |
| `infra/kubernetes` | — | 배포 | README 한 줄. Month 6 |

Python 패키지 이름은 전부 `aether_<이름>` 이고 배치는 `packages/<이름>/src/aether_<이름>/` 입니다. `src` 레이아웃을 쓰는 이유는 하나입니다 — 테스트가 **설치된** 패키지를 import 하게 강제해, 경계 위반이 로컬의 상대 경로 덕에 통과하는 일이 없게 합니다. `apps/api`, `apps/worker` 도 같은 규칙(`aether_api`, `aether_worker`)입니다.

루트 파일:

```text
pyproject.toml         uv workspace. members = apps/api, apps/worker, packages/<Python 전부>
uv.lock  .python-version
package.json           pnpm workspace 루트. 스크립트는 -r 로 위임만 합니다
pnpm-workspace.yaml    packages: apps/web, packages/sdk
pnpm-lock.yaml  .nvmrc
.importlinter          AR-2 ~ AR-7 (Python)        ← 보호 파일
.dependency-cruiser.cjs AR-1 (TypeScript)          ← 보호 파일
```

### 2.2 도구 체인

Q1·Q2 의 답을 반영합니다. 버전은 숫자를 문서에 박지 않고 **고정하는 파일**을 정합니다. 문서의 숫자는 코드보다 먼저 낡습니다.

| 대상 | 도구 | 고정 위치 |
| --- | --- | --- |
| Python 의존성·실행 | **uv** workspace | `pyproject.toml` `[tool.uv.workspace]`, `uv.lock` |
| Python 버전 | 3.12 이상 | `.python-version`, 각 `pyproject.toml` 의 `requires-python` |
| Node 의존성·실행 | **pnpm workspace 단독**. turborepo 없음 — 패키지 두 개(web, sdk)에 태스크 그래프는 과합니다. 다섯을 넘으면 그때 다시 판정 | `pnpm-workspace.yaml`, `pnpm-lock.yaml` |
| Node 버전 | 현재 LTS | `.nvmrc`, 루트 `package.json` `engines` |
| Python lint·포맷 | ruff | `pyproject.toml` `[tool.ruff]` (별도 `ruff.toml` 을 만들지 않습니다 — 보호 파일 수를 늘리지 않기 위해) |
| Python 타입 | mypy, strict | `pyproject.toml` `[tool.mypy]` |
| Python 테스트 | pytest. `integration` 마커. 통합 테스트는 testcontainers 로 실제 PostgreSQL·Redis | `pyproject.toml` `[tool.pytest.ini_options]` |
| Python 아키텍처 | import-linter | `.importlinter` |
| TS lint | ESLint (flat config) | `eslint.config.*` (보호 파일) |
| TS 타입 | `tsc --noEmit` | 각 패키지 `tsconfig.json` (보호 파일) |
| TS 테스트 | Vitest | `vitest.config.*` |
| TS 아키텍처 | dependency-cruiser | `.dependency-cruiser.cjs` |
| 마이그레이션 | Alembic | `apps/api/migrations/` |
| 트레이스 | OpenTelemetry SDK | 각 앱 시작점 |

### 2.3 계약

DP-1 API-first 이므로 계약을 먼저 적습니다. 구현이 아니라 이것이 리뷰 대상입니다.

**`GET /healthz`** — 인증 없음. 프로세스 liveness 만 답합니다. DB·Redis 를 보지 않습니다(그것은 readiness 이고 Phase 0 범위 밖입니다).

```json
{ "status": "ok", "service": "api", "version": "<git sha 또는 semver>" }
```

**큐** — Redis 하나. 메시지 이름과 필드는 spec 이 고정하고, 전송 방식(Streams / List)은 plan 이 정합니다.

| 이름 | 방향 | 필드 | Phase 0 |
| --- | --- | --- | --- |
| `aether:runs:requested` | Control → Data | `run_id`, `agent_version_id` | worker 가 이 이름으로 consumer group 을 만들고 대기만 합니다 |
| `aether:runs:status` | Data → Control | `run_id`, `status`, `at` | 이름만 예약. Phase 1 P1-5 |

이 두 이름이 AR-7 의 코드상 실체입니다. Control Plane 은 `requested` 에 쓰기만 하고, Data Plane 은 `status` 에 쓰기만 합니다. 서로의 코드를 import 하지 않습니다.

**설정** — 환경변수만. 접두사 `AETHER_`. `.env.example` 이 전체 키를 개발용 기본값과 함께 나열합니다. 비밀값 자리에는 동작하는 값이 아니라 `<generate>` 를 둡니다.

**OpenTelemetry** — 세 앱 모두 시작 시 SDK 를 초기화하고 `service.name` 을 `api` / `worker` / `web` 으로 둡니다. exporter 는 `OTEL_EXPORTER_OTLP_ENDPOINT` 가 있을 때만 붙습니다. 없으면 no-op 이고, 있어도 부팅을 막지 않습니다(DP-4).

### 2.4 `packages/sdk` (Q5)

| 항목 | 결정 |
| --- | --- |
| 타입 | **생성.** `apps/api` 가 내보낸 `openapi.json` 에서 `openapi-typescript` 로 `packages/sdk/src/generated/` 를 만들고 **커밋**합니다 |
| 호출 함수 | **수기.** `createClient({ baseUrl, apiKey })` 와 `healthz()`. 생성기가 만든 fetch 래퍼는 쓰지 않습니다 — 인증 헤더·재시도·스트리밍(Phase 1)을 우리가 소유해야 합니다 |
| 드리프트 | `api-unit` 안의 테스트 하나가 "api 가 지금 내보내는 OpenAPI == 커밋된 `packages/sdk/openapi.json`" 을 확인합니다. 어긋나면 correctness 실패. 새 단계를 만들지 않습니다 |

생성물을 커밋하는 이유: web 의 typecheck 가 Python 환경 없이 돌아야 합니다. 생성 단계를 verify 에 넣으면 Q3 의 분할 문제가 다시 생깁니다.

### 2.5 `apps/web`

Next.js App Router. 페이지 하나(`/`)가 sdk 의 `healthz()` 를 호출해 결과를 표시합니다. `apps/web` 은 `packages/sdk` 외의 `packages/*` 와 `apps/api` 를 import 하지 않습니다(AR-1). 이것을 말이 아니라 `.dependency-cruiser.cjs` 가 판정합니다.

### 2.6 `apps/worker`

Data Plane 의 프로세스입니다. Redis 에 붙어 `aether:runs:requested` 의 consumer group 으로 블록합니다. Phase 0 에서는 메시지를 처리하지 않습니다. Redis 가 없으면 지수 백오프로 재시도한 뒤 명확한 메시지와 함께 0 이 아닌 코드로 종료합니다. SIGTERM 에 5초 안에 내려갑니다. `aether_api` 를 import 하지 않습니다.

### 2.7 Docker Compose

| 서비스 | 역할 | 비고 |
| --- | --- | --- |
| `postgres` | 저장소 | 초기화 스크립트가 2.8 의 스키마 두 개와 역할 두 개를 만듭니다 |
| `redis` | 큐 | |
| `migrate` | 일회성. `alembic upgrade head` | 관리자 역할로 실행. 끝나면 종료 |
| `api` | Control Plane | `migrate` 완료 후 기동 |
| `worker` | Data Plane | `redis` healthy 후 기동 |
| `web` | Experience | `api` healthy 후 기동 |

모든 서비스에 healthcheck 를 두고 `depends_on` 에 `condition: service_healthy` 를 씁니다. 베이스 이미지는 digest 로 고정합니다.

오프라인은 오버라이드 파일로 표현합니다.

```text
docker compose up                                              # 개발. 첫 실행은 이미지 pull 이 필요
docker compose -f compose.yaml -f compose.offline.yaml up     # R-4. internal: true 네트워크. egress 없음
```

R-1 과 R-4 는 같은 명령이 아닙니다. 3절 C-3 에 이유가 있습니다.

### 2.8 데이터 모델 v1

한 PostgreSQL 안에서 Control Plane 과 Data Plane 의 저장소를 **스키마와 역할로** 가릅니다. 지금 가르지 않으면 `apps/api` 가 `runs` 를 직접 읽는 지름길이 Phase 0 에서 생기고, intent 가 말한 대로 Phase 14 까지 남습니다.

| 스키마 | 소유 | 테이블 (Phase 0) | 접근 역할 |
| --- | --- | --- | --- |
| `control` | Control Plane (`apps/api`) | `agents`, `agent_versions`, `api_keys` | `aether_control`: 전부 |
| `data` | Data Plane (`apps/worker`, `packages/runtime`) | `runs` | `aether_data`: 전부 + `control.agent_versions` SELECT |

`aether_control` 은 `data` 스키마에 아무 권한이 없습니다. `aether_data` 가 `control.agent_versions` 를 읽는 것은 허용입니다 — Control Plane 은 선언하고 Data Plane 은 그 선언을 읽어 실행합니다(AR-7 의 뜻이 정확히 이것입니다). Phase 1 의 `GET /runs/{id}` 는 `data.runs` 를 직접 읽지 않고, `aether:runs:status` 이벤트로 채워지는 `control` 쪽 투영을 읽습니다. 그 투영은 P1-5 의 몫이고 여기서는 자리만 남깁니다.

| 테이블 | 열 (뜻은 domain.md 1절) | 제약 |
| --- | --- | --- |
| `control.agents` | `id` uuid, `name` text, `created_at`, `updated_at` | `name` unique |
| `control.agent_versions` | `id` uuid, `agent_id` → agents, `version` int, `definition` jsonb, `created_at` | (`agent_id`, `version`) unique. **BEFORE UPDATE OR DELETE 트리거가 거부** — 불변은 앱의 예의가 아니라 DB 의 제약입니다 |
| `control.api_keys` | `id` uuid, `label` text, `key_hash` text, `created_at`, `revoked_at` nullable | 원문은 저장하지 않습니다 |
| `data.runs` | `id` uuid, `agent_version_id` → control.agent_versions, `status` enum, `created_at`, `started_at`, `finished_at`, `failure_reason` nullable, `trace_id` nullable | `status` ∈ queued · running · waiting · succeeded · failed · cancelled · timed_out. 전이 규칙은 P1-2 가 코드로 소유하고 DB 는 값만 저장 |

`definition` 의 내부 형태는 Phase 1 이 정합니다. Phase 0 에서는 `schema_version` 키 하나만 요구합니다. 열의 정본은 P0-8 이 만드는 `docs/data-model.md` 이며, 이 표는 경계와 제약만 고정합니다.

마이그레이션은 `apps/api/migrations/` 에 둡니다. 배포·구성은 Control Plane 의 책임이므로([../docs/architecture.md](../docs/architecture.md) 4절) 두 스키마의 마이그레이션을 api 가 소유하는 것이 계층과 맞습니다. 실행 역할(관리자)과 api 의 런타임 역할(`aether_control`)은 다릅니다.

### 2.9 인증 기준선 (Q4) 🔒

| 항목 | 결정 |
| --- | --- |
| 방식 | API 키. `Authorization: Bearer <key>` |
| 저장 | `control.api_keys` 에 해시만. 원문은 발급 시 한 번 출력 |
| 발급 | `uv run aether-api keys create --label <이름>`. 환경변수로 키를 주입하는 부트스트랩은 두지 않습니다 — `.env` 에 동작하는 비밀값이 놓이는 경로가 됩니다 |
| 범위 | `/healthz` 를 제외한 모든 경로. 단일 테넌트. 사용자·조직·역할 없음 |
| 뺀 것 | 세션, OIDC/SSO, Permission. Identity 는 Control Plane 의 항목이지만 Trust Layer(Phase 8) 전에는 키 하나로 충분합니다 |

이 절은 DP-6 과 AGENTS.md Trust 에 걸립니다. 에이전트는 P0-9 에서 인터페이스와 테스트 목록까지만 만들고 구현은 사람 검토를 거칩니다.

### 2.10 아키텍처 규칙의 기계 판정

| 규칙 | 도구 | 계약 | Phase 0 |
| --- | --- | --- | --- |
| AR-1 | dependency-cruiser | `apps/web` → `packages/*` 금지, 단 `packages/sdk` 허용. `apps/web` → `apps/api` 금지 | 활성 |
| AR-2 | import-linter forbidden | `aether_runtime, workflow, context, memory, mcp, policy, evaluation` → `aether_api`, `aether_worker` 금지 | 활성 |
| AR-3 | forbidden | `aether_mcp`, `aether_context` → `aether_runtime` 금지 | 활성. 코드가 없어 공허하게 통과하지만 위반 fixture 가 발화를 증명 |
| AR-4 | forbidden | `aether_policy` → `aether_runtime`, `aether_mcp`, `aether_context` 금지 | 활성 |
| AR-5 | forbidden, `include_external_packages` | LLM SDK 모듈(`openai`, `anthropic`, … 목록은 `.importlinter` 가 소유) → `aether_runtime.model_gateway` 밖 어디서든 금지 | 활성. 공급자를 더하면 목록에 이름을 더합니다 — 보호 파일이므로 사람 |
| AR-6 | forbidden | MCP 클라이언트 라이브러리 → `aether_mcp` 밖 금지 | 등록. Phase 2 에 실제로 걸림 |
| AR-7 | forbidden | `aether_api` → `aether_worker` 금지. `aether_api` → `aether_runtime` 의 실행 모듈(planner, executor) 금지, 공개 타입 모듈만 허용 | 등록. 모듈 이름은 Phase 1 에서 확정 |

부정 테스트: `tests/arch/` 에 위반 import 를 담은 임시 패키지 fixture 를 두고, 그 fixture 용 설정으로 `lint-imports` 와 `depcruise` 를 실행해 exit ≠ 0 을 단언합니다. 이 테스트가 없으면 "규칙이 등록되어 있다" 와 "규칙이 동작한다" 를 구분할 수 없습니다.

### 2.11 검증 단계 (Q3)

**근거.** `harness/scripts/lib/detect-stack.sh` 의 계약: 감지 결과(`detect_stack`, `detect_kind`)는 `HARNESS_STEPS` 가 비어 있을 때의 기본 단계 생성과 진단 표시에만 쓰입니다. 보호 패턴은 감지와 무관하게 로드된 전 팩의 합집합입니다. `harness.config` 가 `HARNESS_STEPS` 를 명시하는 이 저장소에서 `HARNESS_KIND=fullstack` 은 동작에 영향이 없습니다. 그러므로 **verify 를 kind 별로 나눌 이유가 없습니다.** Python 과 TypeScript 단계를 한 배열에 나열하고, 계층 점수를 가르는 것은 id 접두사와 `layer` 열입니다.

**단계.** self-check 6개는 그대로 두고 제품 단계 10개를 더합니다. intent 의 제약 "열 개 넘게 늘리지 않습니다" 의 상한입니다. 싼 것을 앞에 둡니다 — verify 는 필수 단계가 실패하면 뒤를 건너뛰므로, 앞 단계가 빨라야 실패가 빨리 드러납니다.

| id | layer | required | command |
| --- | --- | --- | --- |
| `api-lint` | quality | true | `uv run ruff check .` |
| `api-typecheck` | quality | true | `uv run mypy` |
| `api-arch` | architecture | true | `uv run lint-imports` |
| `api-unit` | correctness | true | `uv run pytest -q -m "not integration"` |
| `web-typecheck` | quality | true | `pnpm -r run typecheck` |
| `web-lint` | quality | true | `pnpm -r run lint` |
| `web-arch` | architecture | true | `pnpm -F web run depcruise` |
| `web-unit` | correctness | true | `pnpm -r run test:unit` |
| `web-build` | correctness | true | `pnpm -F web run build` |
| `api-integration` | correctness | true | `uv run pytest -q -m integration` (testcontainers → 실행 호스트에 Docker 필요) |

뺀 것: `format-check`(ruff check 에 포맷 규칙을 포함시켜 대신합니다), `smoke`·`e2e`·`load`(Phase 1 이후, [../intents/mvp-backlog.md](../intents/mvp-backlog.md) P1-9·MVP-4). Phase 1 에서 단계를 더할 때는 실행 시간을 먼저 봅니다.

`HARNESS_THRESHOLD` 는 P0-7 에서 90 → 80 으로 내립니다([../harness/references/harness-adoption.md](../harness/references/harness-adoption.md) AD-2). EI-2 에 따라 이 값은 사람이 바꾸고, 근거를 `improvement-log/` 에 1건 남깁니다. `HARNESS_SELF_CHECK_LINK_DIRS` 에 `specs` 를 더합니다(이 디렉터리의 링크가 지금은 검사되지 않습니다).

### 2.12 CI

`.github/workflows/harness.yml` 의 `verify` job 은 `./harness/scripts/verify.sh` 하나만 실행합니다. 그 앞에 도구 설치가 필요합니다: uv, Node LTS + pnpm(캐시 포함). `api-integration` 은 ubuntu-latest 의 Docker 를 씁니다. 이 파일은 보호 파일이므로 변경은 `harness-change` 라벨과 사람 검토를 거칩니다.

### 2.13 개발 환경 (Windows)

줄바꿈은 `.gitattributes` 가 LF 로 고정했습니다. 하네스 스크립트는 Git Bash 로 실행합니다. Docker Desktop 이 필요합니다(compose, testcontainers). uv 와 pnpm 은 네이티브로 동작합니다.

## 3. 우려 지점

플레이북이 요구하는 "areas of concern" 입니다. 서로 부딪히는 정책과 사람이 열어야 하는 문을 적습니다.

| ID | 우려 | 어떻게 다루는가 |
| --- | --- | --- |
| C-1 | **보호 파일의 생성이 hook 에 막힙니다.** `guard-lib.sh` 의 `matches_any` 는 `/` 없는 패턴을 **basename 으로 어느 깊이에서든** 맞춥니다. 그래서 `.importlinter`, `.dependency-cruiser.cjs` 뿐 아니라 `apps/web/tsconfig.json`, `eslint.config.*` 도 에이전트가 Write 로 만들 수 없습니다. P0-1, P0-3, P0-6 이 걸립니다 | 에이전트는 파일 내용을 PR 본문이나 인접 문서에 제안하고, 사람이 만들어 `harness-change` 라벨로 커밋합니다. `HARNESS_ALLOW_GUARDED_EDIT` 우회는 쓰지 않습니다 — `bypass` 이벤트가 남고 REP-3 의 합격 기준에 걸립니다 |
| C-2 | **Phase 0 에서 보호 파일 변경이 세 건 있습니다.** `harness.config`(단계·임계값·링크 디렉터리), `harness.yml`(도구 설치), 그리고 C-1 의 신규 파일들 | 각각 별도 PR, 한 번에 하나([../harness/rules/harness-change-control.rule.md](../harness/rules/harness-change-control.rule.md)). 임계값은 EI-2 로 사람 소유 |
| C-3 | **R-1 과 R-4 는 같은 명령으로 동시에 만족되지 않습니다.** "명령 하나로 뜬다" 는 첫 실행에서 이미지 pull 을 전제하고, "인터넷 없이" 는 pull 이 이미 끝났음을 전제합니다 | R-1 은 온라인 첫 실행으로, R-4 는 빌드 후 `compose.offline.yaml` 로 각각 판정합니다. 두 판정을 하나로 합치려고 이미지를 저장소에 넣지 않습니다. 진짜 오프라인 배포는 Phase 11 의 Offline Release Bundle 입니다 |
| C-4 | **인증(2.9)은 보안에 닿습니다** | 🔒 P0-9. 에이전트는 설계와 테스트 목록까지. 구현은 사람 검토 |
| C-5 | **`api-integration` 이 Docker 에 의존합니다.** testcontainers 가 이미지를 pull 하므로 verify 자체는 오프라인이 아닙니다 | DP-4 는 "Runtime 이 오프라인" 이지 "verify 가 오프라인" 이 아닙니다. Phase 11 에서 verify 의 오프라인도 확인합니다([../docs/roadmap.md](../docs/roadmap.md) Phase 11 행) |
| C-6 | **AR-7 은 지금 부분적으로만 표현됩니다.** 코드 경계(import)와 저장소 경계(역할)는 잡히지만, "HTTP 로 Data Plane 을 부르지 않는다" 는 정적 도구가 잡지 못합니다 | Phase 1 에서 api 의 outbound HTTP 를 sdk 경유 하나로 모으고 그 모듈을 AR-7 계약에 넣습니다. 지금은 리뷰 항목 |
| C-7 | **`packages/evaluation` 과 루트 `evaluation/` 의 이름 충돌** | Python 패키지 이름을 `aether_evaluation` 으로 두고, 루트 `evaluation/` 은 하네스 것임을 [../docs/domain.md](../docs/domain.md) 5절이 소유합니다. 새로 적지 않습니다 |
| C-8 | **cross-schema FK(`data.runs` → `control.agent_versions`)는 한 DB 일 때만 성립합니다.** On-Prem 에서 두 Plane 이 다른 DB 에 놓이면 깨집니다 | Modular Monolith(DP-5) 인 지금은 FK 로 두고, Plane 분리 배포가 실제로 오는 Phase 에서 soft reference 로 바꿉니다. 그 전환이 필요하다는 사실을 `docs/data-model.md` 에 적어 둡니다 |

## 4. 결정 요청

이 spec 을 승인하면 아래가 채택됩니다. 하나라도 다르게 하려면 그 항목을 먼저 고친 뒤 승인합니다.

| ID | 결정 | 닫히는 질문 | 근거 |
| --- | --- | --- | --- |
| D-1 | verify 는 **한 번에** 돕니다. Python·TS 단계를 한 `HARNESS_STEPS` 에 나열하고 id 접두사(`api-`, `web-`)로 가릅니다. kind 별 분할 없음 | **Q3** | 2.11. `detect-stack.sh` 계약상 감지 결과는 명시된 `HARNESS_STEPS` 에 영향이 없습니다 |
| D-2 | sdk 는 **타입은 생성, 호출은 수기**. 생성물을 커밋하고 드리프트는 `api-unit` 의 테스트가 잡습니다 | **Q5** | 2.4 |
| D-3 | 🔒 인증은 **API 키**(Bearer, 해시 저장, CLI 발급). 사용자·조직·세션 없음 | **Q4** | 2.9. 사람 검토 필요 |
| D-4 | 저장소를 **`control` / `data` 스키마와 두 역할로** 가릅니다. `aether_data` 만 `control.agent_versions` 를 읽습니다 | — | 2.8. AR-7 을 Phase 0 에서 저장소 수준으로 고정 |
| D-5 | 마이그레이션은 **`apps/api` 소유, Alembic**, compose 의 일회성 `migrate` 서비스로 실행 | — | 2.8. 배포·구성은 Control Plane 의 책임 |
| D-6 | 버전은 **파일로 고정**(`.python-version`, `.nvmrc`, `engines`). Python 3.12+, Node 현재 LTS | — | 2.2 |
| D-7 | 제품 검증 단계는 **정확히 10개**(2.11 표). `format-check` 는 넣지 않고 `smoke`·`e2e`·`load` 는 Phase 1 이후 | — | intent 제약 "열 개 넘게 늘리지 않습니다" |
| D-8 | 오프라인은 **`compose.offline.yaml` 오버라이드**로 판정하고, R-1 과 R-4 를 다른 명령으로 둡니다 | — | C-3 |
| D-9 | Python 패키지는 **`aether_<이름>`, `src` 레이아웃** | — | 2.1 |

승인과 함께 [../intents/0001-phase-0-foundation.md](../intents/0001-phase-0-foundation.md) 의 Open Questions 3·4·5 를 닫고, [../intents/intent.md](../intents/intent.md) 의 머리 표를 갱신합니다. D-3 은 승인해도 P0-9 의 구현 검토가 따로 남습니다.

## 5. 검증 매핑

요구사항마다 어느 단위가 만족시키고 무엇으로 판정하는지입니다. 빠진 R 이 있으면 설계가 덜 된 것입니다.

| R | 단위 | 판정 명령 또는 절차 |
| --- | --- | --- |
| R-1 | P0-1 ~ P0-5 | README 의 명령 실행 → `curl /healthz`, web 200 |
| R-2 | P0-7 | `./harness/scripts/verify.sh` → `.harness/verify.json` 의 `api-*`, `web-*` |
| R-3 | P0-6 | `api-arch`, `web-arch` + `tests/arch/` 부정 테스트 |
| R-4 | P0-5 | `docker compose -f compose.yaml -f compose.offline.yaml up` → healthz, web |
| R-5 | P0-7 | GitHub Actions `harness` 워크플로 |
| R-6 | P0-5, P0-9 | `.env` 미커밋 확인, 이미지 layer 검사, 가드 security 패턴 |
| R-7 | P0-4, P0-8 | `api-arch`(AR-7 계약), DB 역할 권한 테스트 |
| R-8 | P0-8 | `api-integration`: 마이그레이션 왕복, 불변 트리거 테스트 |
| R-9 | P0-9 | `api-unit`: 401 / 200 테스트 |
| R-10 | P0-7 | 2.11 표와 `harness.config` diff, `improvement-log/` 항목 존재 |

## 6. Non-goals

intent 의 것을 반복하고, 설계하면서 새로 뺀 것을 더합니다.

| 항목 | 언제 |
| --- | --- |
| Agent Registry API, Run API, 스트리밍 | Phase 1 (P1-1, P1-5, P1-6) |
| `control` 쪽 Run 상태 투영 | Phase 1 (P1-5) |
| readiness 엔드포인트 | Phase 1. liveness 만으로 Phase 0 의 compose 가 성립합니다 |
| 사용자·조직·역할·SSO | Phase 8 Trust Layer |
| Kubernetes 매니페스트 | Month 6 |
| Offline Release Bundle, verify 의 오프라인 | Phase 11 |
| Plane 분리 배포와 soft reference 전환 | Plane 이 실제로 갈라지는 Phase |
| turborepo | 패키지가 다섯을 넘을 때 재판정 |

## 관련 문서

- [../intents/0001-phase-0-foundation.md](../intents/0001-phase-0-foundation.md) — 근거 intent
- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — P0-1 ~ P0-9
- [../docs/architecture.md](../docs/architecture.md) — AR-*, DP-*, Plane
- [../docs/domain.md](../docs/domain.md) — 용어
- [../harness/rules/evaluation-integrity.rule.md](../harness/rules/evaluation-integrity.rule.md) — EI-*
- [../harness/rules/harness-change-control.rule.md](../harness/rules/harness-change-control.rule.md) — 보호 파일 절차
- [README.md](README.md) — spec 의 규칙
