# Plan 0001 — Phase 0: Architecture & Foundation

| 키 | 값 |
| --- | --- |
| 번호 | 0001 |
| 근거 spec | [../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) (승인됨 2026-09-09) |
| 근거 intent | [../intents/0001-phase-0-foundation.md](../intents/0001-phase-0-foundation.md) |
| 작업 단위 | [../intents/mvp-backlog.md](../intents/mvp-backlog.md) P0-1 ~ P0-9 |
| 작성일 | 2026-09-09 |
| 상태 | 검토 대기 |
| 승인 | (비어 있음 — 채워지기 전에는 P0-1 을 시작하지 않습니다) |
| 개정 | — |

spec 이 정한 요구사항(R)·결정(D)·계약은 반복하지 않습니다. 이 문서는 아홉 단위를 어떤 순서로 하고, 단위마다 어느 파일을 누가 만들며, 게이트가 켜지기 전에는 무엇으로 판정하는지를 정합니다.

이 plan 이 풀어야 하는 문제는 하나입니다. spec C-1 — **보호 패턴에 걸리는 파일은 에이전트가 만들 수 없습니다.** `tsconfig.json`, `eslint.config.*`, `.importlinter`, `.dependency-cruiser.*`, `harness.config`, `harness.yml` 이 그것입니다. 이 파일들이 아홉 단위 곳곳에 흩어져 있으면 사람이 매 단위마다 불려 나옵니다. 그래서 사람 손이 필요한 순간을 **세 번**으로 묶었습니다(3절).

## 1. 순서

의존 그래프(backlog 의 `의존` 열)에서 유도했습니다. 한 wave 안의 단위는 서로 독립이라 순서를 바꿔도 됩니다. 에이전트 세션 하나에 단위 하나입니다.

| Wave | 단위 | 왜 이 자리인가 | 사람 손 |
| --- | --- | --- | --- |
| 1 | **P0-1** 모노레포 뼈대 | 모든 것의 의존. 보호 파일 다섯 개가 여기서 필요합니다 | **H-1** (단위 안에서) |
| 2 | **P0-6** AR-* 기계 판정 | H-1 로 규칙 파일이 생긴 직후, 코드가 비어 있을 때 부정 테스트를 붙이는 것이 가장 쌉니다. 이후 모든 단위가 이 규칙 아래에서 작성됩니다 | — |
| 2 | **P0-2** api 최소 기동 | P0-1 만 필요 | — |
| 2 | **P0-4** worker 최소 기동 | P0-1 만 필요. P0-2 와 병렬 가능 | — |
| 3 | **P0-3** sdk + web | P0-2 의 OpenAPI 가 필요 | — |
| 3 | **P0-8** 데이터 모델 v1 | P0-2 의 앱 뼈대가 필요. P0-3 과 병렬 가능 | — |
| 4 | **P0-5** compose + README | api·web·worker 가 전부 있어야 |  — |
| 5 | **P0-7** 게이트 활성화 + CI | compose(P0-5)와 규칙(P0-6)이 있어야 제품 단계가 전부 통과 가능 | **H-2** |
| 6 | **P0-9** 🔒 인증 | P0-7 뒤에 두는 이유: 보안 코드가 **켜진 게이트** 아래에서 작성되게. 의존(P0-8)은 wave 3 에 끝나 있습니다 | **H-3** |

P0-6 을 backlog 의 번호 순서보다 앞당긴 것은 의도입니다. 규칙이 나중에 붙으면 그 사이에 쓴 코드가 규칙을 어기고 있을 수 있고, 그때 고치는 비용은 지금 붙이는 비용보다 항상 큽니다.

## 2. 단위별 계획

표기: **A** = 에이전트가 만듦, **H** = 사람이 만듦(C-1), **W** = 가드가 경고만 내는 파일(만들 수 있음. 경고는 정상입니다).

### P0-1 모노레포 뼈대와 빈 패키지 경계

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | 루트 `pyproject.toml`(uv workspace, `[tool.uv] package = false`, ruff·mypy·pytest 설정, dev 의존 그룹), `.python-version` | A (W) |
| 2 | `apps/api`, `apps/worker`, `packages/{runtime,workflow,context,memory,mcp,policy,evaluation}` — 각각 `pyproject.toml` + `src/aether_<이름>/__init__.py` + `README.md`(책임 한 문장 = architecture.md 2절) | A (W) |
| 3 | `uv sync` → `uv.lock` | A (W) |
| 4 | 루트 `package.json`(`engines`, devDependencies: typescript, eslint, typescript-eslint, dependency-cruiser, vitest), `pnpm-workspace.yaml`, `.nvmrc` | A (W) |
| 5 | `apps/web/package.json`(`@aether/web`), `packages/sdk/package.json`(`@aether/sdk`) — 스크립트 이름은 spec 2.2 의 규칙대로 전부 등록, 내용은 아직 비어도 됨 | A (W) |
| 6 | `pnpm install` → `pnpm-lock.yaml` | A (W) |
| 7 | **H-1**: `apps/web/tsconfig.json`, `packages/sdk/tsconfig.json`, `eslint.config.js`(루트), `.importlinter`, `.dependency-cruiser.cjs` — 부록 A~E 의 내용으로 | **H** |
| 8 | `infra/docker/README.md`, `infra/kubernetes/README.md` 한 줄씩 | A |
| 9 | 판정: `uv sync` 와 `pnpm install` 이 깨끗한 checkout 에서 성공. `uv run lint-imports` exit 0(코드가 없어 공허하게). 트리가 spec 2.1 표와 일치 | A |

`packages/sdk` 는 `src/index.ts` 빈 export 하나만 둡니다. 내용은 P0-3.

### P0-6 AR-* 를 기계 판정으로

H-1 이 규칙 파일을 만들었으므로 이 단위는 **규칙이 동작함을 증명**하는 일입니다.

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `tests/arch/fixtures/ar_violation/` — `bad_runtime/__init__.py`(`import bad_api`), `bad_api/__init__.py`, `importlinter.ini`(bad_runtime → bad_api 금지). **파일 이름이 `.importlinter` 가 아니어야** 에이전트가 만들 수 있습니다 | A |
| 2 | `tests/arch/fixtures/ar1_violation/apps/web/page.ts`(`packages/runtime` 를 import), `depcruise.fixture.cjs` | A |
| 3 | `tests/arch/test_import_linter.py` — (a) fixture 로 `lint-imports --config importlinter.ini` 가 exit ≠ 0, (b) 실제 `.importlinter` 를 파싱해 AR-2·3·4·5·6·7 계약 이름이 전부 있음, (c) 실제 `uv run lint-imports` 가 exit 0 | A |
| 4 | `tests/arch/test_depcruise.py` — fixture 로 exit ≠ 0, 실제 `pnpm -F web run depcruise` 가 exit 0 | A |
| 5 | `apps/web/package.json` 의 `depcruise` 스크립트: `depcruise . --config ../../.dependency-cruiser.cjs` | A (W) |
| 6 | 판정: 3·4 의 테스트 전부 통과. AR-7 의 planner/executor 부분은 모듈이 없어 등록하지 않음 — spec 2.10 대로 Phase 1 | A |

첫 실행에서 부록 D·E 의 설정이 도구에 거부되면 **에이전트는 고칠 수 없습니다**(보호 파일). 거부 메시지와 고친 내용을 사람에게 넘기고, 사람이 반영합니다. 이것이 H-1 의 후속입니다.

### P0-2 `apps/api` 최소 기동

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `apps/api/src/aether_api/settings.py`(`AETHER_` 접두사, 기본값으로 뜸), `telemetry.py`(OTel 초기화, exporter 는 env 있을 때만), `main.py`(FastAPI 앱, `GET /healthz`), `cli.py`(`aether-api openapi` — OpenAPI JSON 을 stdout 으로. P0-3 이 씁니다) | A |
| 2 | `apps/api/pyproject.toml` 에 `[project.scripts] aether-api = "aether_api.cli:main"` | A (W) |
| 3 | `apps/api/tests/test_healthz.py` — 200, 스키마 `{status, service, version}`, `version` 기본값 `dev` | A |
| 4 | 판정: `uv run pytest apps/api -q` 통과. `uv run uvicorn aether_api.main:app` 기동 후 `curl /healthz` 200. 기동 로그에 외부 호출 없음 | A |

### P0-4 `apps/worker` 최소 기동

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `apps/worker/src/aether_worker/settings.py`, `queue.py`(Redis Streams `aether:runs:requested` 에 consumer group 생성·블록 읽기. 처리 없음), `main.py`(재시도 백오프, SIGTERM 핸들러) | A |
| 2 | `apps/worker/tests/test_backoff.py`(단위. 시계 주입), `apps/worker/tests/test_connect.py`(`integration` 마커. testcontainers Redis 로 ready 로그와 5초 내 종료) | A |
| 3 | 판정: 단위 테스트 통과. `uv run pytest apps/worker -q -m integration` 통과 | A |

### P0-3 `packages/sdk` 와 `apps/web` 최소 기동

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `uv run aether-api openapi > packages/sdk/openapi.json` | A |
| 2 | `packages/sdk` — `scripts.generate = "openapi-typescript openapi.json -o src/generated/openapi.d.ts"`, 실행해 생성물 커밋. `src/client.ts`(`createClient({ baseUrl, apiKey })`, `healthz()`), `src/index.ts`, `src/client.test.ts`(Vitest, fetch 를 주입해 경로·헤더 확인), `vitest.config.ts` | A (W) |
| 3 | `apps/web` — `app/layout.tsx`, `app/page.tsx`(서버 컴포넌트에서 sdk 의 `healthz()` 호출, 결과 표시), `next.config.ts`, `vitest.config.ts`, 컴포넌트 테스트 1건 | A (W) |
| 4 | `apps/api/tests/test_openapi_drift.py` — `aether-api openapi` 출력 == 커밋된 `packages/sdk/openapi.json` | A |
| 5 | 판정: `pnpm -F sdk run generate && git diff --exit-code -- packages/sdk/src/generated`. `pnpm -F web -F sdk run typecheck`, `run lint`, `run test:unit`. `pnpm -F web run build`. `pnpm -F web run depcruise` exit 0 | A |

### P0-8 데이터 모델 v1

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `apps/api/migrations/`(`alembic.ini`, `env.py`, `script.py.mako`), `versions/0001_schemas_and_roles_grants.py` — `CREATE SCHEMA control, data`, 다섯 테이블(spec 2.8 표), `agent_versions` 불변 트리거, `run_executions.status` enum, GRANT 두 역할. `downgrade` 는 전부 되돌림 | A |
| 2 | `infra/docker/postgres/init/01-roles.sql` — `aether_control`, `aether_data` 역할만. 비밀번호는 env 참조. P0-5 의 compose 가 마운트 | A |
| 3 | `apps/api/tests/conftest.py`(`integration`: testcontainers PostgreSQL 기동 → 01-roles.sql 실행 → `alembic upgrade head`), `tests/test_migrations.py`(up → down → up 왕복), `tests/test_agent_version_immutable.py`(**관리자 역할로** UPDATE·DELETE → 트리거 예외), `tests/test_plane_roles.py`(`aether_control` 로 `SELECT FROM data.run_executions` → permission denied. `aether_data` 로 `control.agent_versions` SELECT 성공, INSERT 실패) | A (W) |
| 4 | `docs/data-model.md` — 열의 정본. cross-schema FK 의 수명(spec C-8)을 적음. `docs/README.md` 의 "아직 없는 문서" 에서 행 제거 | A |
| 5 | 판정: `uv run pytest apps/api -q -m integration` 통과 | A |

### P0-5 Docker Compose 와 루트 README

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `infra/docker/api.Dockerfile`, `worker.Dockerfile`, `web.Dockerfile` — 베이스 이미지 digest 고정, 빌드 인자 `AETHER_VERSION`. `infra/docker/.dockerignore`(`.env*`, `.git`, `node_modules`, `.venv`) | A |
| 2 | `infra/docker/compose.yaml` — postgres(init 마운트, healthcheck), redis(AOF, healthcheck), migrate(일회성, 관리자 역할), api(`service_completed_successfully` on migrate), worker, web. `.env.example` 전체 키, 비밀값 자리는 `<generate>` | A (W) |
| 3 | `infra/docker/compose.offline.yaml` — 네트워크 `internal: true`, `probe` 서비스(curl 이미지, `api:8000/healthz` 와 `web:3000/` 200 확인 후 exit 0) | A (W) |
| 4 | 루트 `README.md` — 기동 명령(`docker compose -f infra/docker/compose.yaml up`), verify 명령, 문서 지도 링크. 두 홉 규칙(spec R-1) | A |
| 5 | 판정: 온라인에서 README 의 명령 → healthz 200, web 200 (R-1). 이미지 빌드 후 `docker compose -f … -f compose.offline.yaml run probe` exit 0 (R-4). `docker history` 로 이미지에 `.env` 없음 (R-6) | A |

### P0-7 `harness.config` 제품 단계 활성화와 CI

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | 로컬에서 spec 2.11 의 열 명령을 **손으로 순서대로** 실행해 전부 exit 0 임을 먼저 확인. 하나라도 실패하면 이 단위를 시작하지 않고 해당 단위로 돌아감 | A |
| 2 | 열 명령의 실행 시간을 합산해 기록. 10분(D-12)을 넘기면 H-2 전에 사람에게 보고 | A |
| 3 | `./harness/scripts/improvement-log.sh new` 로 임계값 90 → 80 의 근거 항목 1건 (intent Constraints 의 예외 조항) | A |
| 4 | **H-2**: `harness.config`(부록 F — 주석 블록을 단계 표로 교체, `HARNESS_THRESHOLD=80`, `HARNESS_SELF_CHECK_LINK_DIRS` 에 `specs plans`), `.github/workflows/harness.yml`(부록 G — uv·pnpm 설치, gitleaks job). PR 에 `harness-change` 라벨 | **H** |
| 5 | 판정: `./harness/scripts/verify.sh` pass, `verify.json` 에 16단계. CI 녹색. `duration_ms` 합계 기록 (R-11) | A |

### P0-9 🔒 인증 기준선

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `apps/api/src/aether_api/auth.py` 의 **인터페이스만**(함수 시그니처, docstring 에 spec 2.9 의 결정), `tests/test_auth.py` 의 **실패하는 테스트**: 보호 경로 401, `/healthz` 200, 폐기된 키 401, 잘못된 형식 401 | A |
| 2 | **H-3 (설계 검토)**: 사람이 인터페이스와 테스트 목록을 검토. 통과 전에 구현하지 않음 | **H** |
| 3 | 구현: 키 생성(`aeth_` + 256-bit), SHA-256 저장, constant-time 비교, `Depends` 로 라우터 전체에 적용(`/healthz` 제외), `cli.py` 에 `keys create --label` | A |
| 4 | **H-3 (구현 검토)**: PR 리뷰. 비밀값이 로그·테스트 fixture 에 원문으로 없는지 | **H** |
| 5 | 판정: `verify.sh` pass(P0-7 뒤이므로 게이트가 켜져 있음). R-9 의 테스트 통과 | A |

## 3. 사람 손

세 번입니다. 각 순간에 에이전트가 무엇을 준비해 넘기는지를 적습니다. 사람이 빈손으로 시작하지 않게 하는 것이 이 절의 목적입니다.

| 순간 | 언제 | 사람이 하는 일 | 에이전트가 넘기는 것 |
| --- | --- | --- | --- |
| **H-1** | P0-1 의 7번 | 보호 파일 다섯 개를 만들어 커밋: `apps/web/tsconfig.json`, `packages/sdk/tsconfig.json`, `eslint.config.js`, `.importlinter`, `.dependency-cruiser.cjs` | 부록 A~E 의 내용. P0-6 에서 도구가 거부한 항목이 있으면 그 diff |
| **H-2** | P0-7 의 4번 | `harness.config` 와 `harness.yml` 을 고쳐 `harness-change` 라벨 PR 로 병합. 임계값 90 → 80 은 EI-2 상 사람의 결정 | 부록 F·G 의 내용. 열 명령이 로컬에서 전부 통과한 기록. 실행 시간 합계. improvement-log 항목 id |
| **H-3** | P0-9 의 2번과 4번 | 인증의 설계 검토(구현 전)와 PR 리뷰(구현 후) | 인터페이스 파일, 실패하는 테스트 목록, spec 2.9 대비 차이가 있으면 그 목록 |

H-1 을 P0-1 안에 두는 대신 P0-1 을 시작하기 전에 미리 해 둘 수도 있습니다. 부록의 내용은 P0-1 의 나머지와 독립이기 때문입니다. 그 경우 사람 손은 여전히 세 번이고 P0-1 은 중단 없이 끝납니다.

## 4. 판정 절차

**P0-7 전.** `harness.config` 에는 self-check 6단계만 있어 `verify.sh` 는 제품 코드를 보지 않습니다. 그래서 P0-1 ~ P0-5 와 P0-8 은 spec 2.11 의 명령을 **손으로** 실행해 판정합니다. 단위를 끝낼 때 다음을 순서대로 실행하고 전부 exit 0 이어야 합니다.

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run pytest -q -m 'not integration'
pnpm -F sdk run generate && git diff --exit-code -- packages/sdk/src/generated && pnpm -F web -F sdk run typecheck
pnpm -F web -F sdk run lint
pnpm -F web run depcruise
pnpm -F web -F sdk run test:unit
pnpm -F web run build
uv run pytest -q -m integration
./harness/scripts/verify.sh          # self-check 는 여전히 통과해야 합니다
```

아직 존재하지 않는 대상(예: P0-2 시점의 web)은 해당 줄을 건너뜁니다. 건너뛴 줄은 완료 보고에 "미측정" 으로 적습니다. 통과로 적지 않습니다(EI-7).

**P0-7 후.** `./harness/scripts/verify.sh` 하나가 전부입니다. 완료 보고에는 `.harness/verify.json` 의 경로와 실패 단계의 `log` 경로를 붙입니다.

## 5. 예산과 중단

[../AGENTS.md](../AGENTS.md) Loop 를 그대로 씁니다.

| 항목 | 값 |
| --- | --- |
| 단위당 반복 | 최대 8회 |
| 같은 실패 | 3회 반복이면 중단 |
| 개선 없음 | 2라운드 연속이면 중단 |
| 중단 시 남기는 것 | 마지막 상태(어느 순서 번호까지 됐는가), 실패 근거 경로(`.harness/logs/` 또는 테스트 출력), 다음 시도 후보. backlog 의 `상태` 를 `보류` 로 |
| 되돌리기 | 단위 하나가 PR 하나입니다. 되돌리기는 그 PR 의 revert. H-1·H-2 의 보호 파일은 사람이 되돌립니다 |
| 8회 안에 안 끝나면 | 단위를 쪼갭니다(`P0-3a`, `P0-3b`). 예산을 늘리지 않습니다 |

한 단위가 다른 단위의 파일을 고치고 싶어지면 그것은 범위가 번지는 신호입니다. 고치지 않고 그 단위의 `범위 밖` 에 있는지 확인한 뒤, 정말 필요하면 backlog 에 후보 단위를 적고 멈춥니다.

## 6. Phase 완료

spec 의 R 전부가 어느 단위에서 판정되는지입니다. 하나라도 판정되지 않은 채 Phase 를 끝내지 않습니다.

| R | 판정 단위 | 판정 시점 |
| --- | --- | --- |
| R-1 | P0-5 | 온라인. README 의 명령 |
| R-2 | P0-7 | `verify.json` 에 `api-*`, `web-*` |
| R-3 | P0-6 | 부정 테스트 + 실제 규칙 통과 |
| R-4 | P0-5 | `probe` exit 0 |
| R-5 | P0-7 | CI 녹색 |
| R-6 | P0-5, P0-7, P0-9 | `.dockerignore`, gitleaks job, 원문 키 부재 |
| R-7 | P0-6, P0-8 | AR-7 계약, 역할 권한 테스트 |
| R-8 | P0-8 | 마이그레이션 왕복, 불변 트리거 |
| R-9 | P0-9 | 401 / 200 |
| R-10 | P0-7 | 단계 표 == `harness.config`, improvement-log 1건 |
| R-11 | P0-7 | `duration_ms` 합계 ≤ 10분 |

**끝났을 때 갱신할 문서**

- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — P0-1 ~ P0-9 `완료`. Phase 1 의 intent 0002 를 발급하고 `Intent:` 를 링크로
- [../intents/intent.md](../intents/intent.md) — 활성 intent 를 0002 로. 사슬의 `지금` 열
- [../docs/roadmap.md](../docs/roadmap.md) — 현재 위치를 Phase 0 완료 / AD-2 로
- [../docs/architecture.md](../docs/architecture.md) 6절 "지금 없는 것" — 이제 있으므로 절을 고침
- [../evaluation/README.md](../evaluation/README.md) — REP-1 · REP-3 · REP-5 가 실행 가능해진 사실
- [../PROVENANCE.md](../PROVENANCE.md) 7절 — 이력 한 줄

---

## 부록 — 보호 파일 제안

에이전트가 만들 수 없는 파일의 내용입니다. **제안**이며, 도구가 첫 실행에서 거부하면 사람이 고쳐 커밋합니다. 그 수정은 이 plan 의 개정이 아닙니다. 버전에 따라 달라지는 부분은 `# 확인` 으로 표시했습니다.

### A. `packages/sdk/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["ES2022", "DOM"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "declaration": true,
    "declarationMap": true,
    "outDir": "dist",
    "rootDir": "src",
    "skipLibCheck": true,
    "isolatedModules": true
  },
  "include": ["src"]
}
```

### B. `apps/web/tsconfig.json`

Next.js 가 생성하는 기본형에 `strict` 와 `noUncheckedIndexedAccess` 를 더한 것입니다. Next 가 첫 빌드에서 이 파일을 고치려 하면 그 diff 를 사람이 반영합니다.

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

### C. `eslint.config.js` (루트)

```js
// @ts-check
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import next from "@next/eslint-plugin-next"; // 확인: 설치된 버전의 flat config export 이름

export default tseslint.config(
  { ignores: ["**/dist/**", "**/.next/**", "**/node_modules/**", "packages/sdk/src/generated/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  {
    files: ["apps/web/**/*.{ts,tsx}"],
    plugins: { "@next/next": next },
    rules: { ...next.configs["core-web-vitals"].rules },
  },
);
```

### D. `.importlinter` (루트)

계약 이름의 접두사 `ar<번호>-` 는 P0-6 의 테스트가 파싱합니다. 바꾸면 테스트도 바꿔야 합니다.

```ini
[importlinter]
root_packages =
    aether_api
    aether_worker
    aether_runtime
    aether_workflow
    aether_context
    aether_memory
    aether_mcp
    aether_policy
    aether_evaluation
include_external_packages = True

[importlinter:contract:ar2-packages-do-not-know-apps]
name = AR-2 packages/* must not import apps/*
type = forbidden
source_modules =
    aether_runtime
    aether_workflow
    aether_context
    aether_memory
    aether_mcp
    aether_policy
    aether_evaluation
forbidden_modules =
    aether_api
    aether_worker

[importlinter:contract:ar3-runtime-direction]
name = AR-3 mcp and context must not import runtime
type = forbidden
source_modules =
    aether_mcp
    aether_context
forbidden_modules =
    aether_runtime

[importlinter:contract:ar4-policy-judges-only]
name = AR-4 policy must not import runtime, mcp, context
type = forbidden
source_modules =
    aether_policy
forbidden_modules =
    aether_runtime
    aether_mcp
    aether_context

[importlinter:contract:ar5-llm-sdk-only-in-model-gateway]
name = AR-5 LLM SDKs only inside aether_runtime.model_gateway
type = forbidden
source_modules =
    aether_api
    aether_worker
    aether_runtime
    aether_workflow
    aether_context
    aether_memory
    aether_mcp
    aether_policy
    aether_evaluation
forbidden_modules =
    openai
    anthropic
    google.genai
ignore_imports =
    aether_runtime.model_gateway.** -> openai
    aether_runtime.model_gateway.** -> anthropic
    aether_runtime.model_gateway.** -> google.genai
# 확인: ** 와일드카드는 import-linter 2.x. 미지원이면 어댑터 모듈을 개별 나열합니다.

[importlinter:contract:ar6-mcp-client-only-in-mcp]
name = AR-6 MCP client library only inside aether_mcp
type = forbidden
source_modules =
    aether_api
    aether_worker
    aether_runtime
    aether_workflow
    aether_context
    aether_memory
    aether_policy
    aether_evaluation
forbidden_modules =
    mcp

[importlinter:contract:ar7-control-does-not-call-data]
name = AR-7 api must not import worker
type = forbidden
source_modules =
    aether_api
forbidden_modules =
    aether_worker
# AR-7 의 나머지(api -> runtime 의 planner/executor 금지)는 그 모듈이 생기는 Phase 1 에 더합니다.
```

### E. `.dependency-cruiser.cjs` (루트)

```js
/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: "ar1-web-imports-only-sdk",
      comment: "AR-1: apps/web knows only the HTTP contract via packages/sdk (docs/architecture.md)",
      severity: "error",
      from: { path: "^apps/web/" },
      to: { path: "^packages/(?!sdk/)" },
    },
    {
      name: "ar1-web-does-not-import-api",
      severity: "error",
      from: { path: "^apps/web/" },
      to: { path: "^apps/api/" },
    },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsPreCompilationDeps: true,
    tsConfig: { fileName: "apps/web/tsconfig.json" },
    // 확인: pnpm 의 workspace 심링크가 실경로(packages/sdk/…)로 해석되는지 첫 실행에서 봅니다.
    // node_modules/@aether/… 로 보이면 to.path 에 "node_modules/@aether/(?!sdk)" 를 더합니다.
    enhancedResolveOptions: {
      exportsFields: ["exports"],
      conditionNames: ["import", "require", "node", "default"],
    },
  },
};
```

### F. `harness.config` — 바꿀 부분

"Phase 0 이후" 주석 블록을 아래로 교체합니다. 나머지 키는 그대로입니다.

```bash
  # --- Phase 0 제품 단계 (spec 0001 2.11, D-7). 싼 것부터. -----------------------
  "api-lint|quality|true|uv run ruff check . && uv run ruff format --check ."
  "api-typecheck|quality|true|uv run mypy"
  "api-arch|architecture|true|uv run lint-imports"
  "api-unit|correctness|true|uv run pytest -q -m 'not integration'"
  "web-typecheck|quality|true|pnpm -F sdk run generate && git diff --exit-code -- packages/sdk/src/generated && pnpm -F web -F sdk run typecheck"
  "web-lint|quality|true|pnpm -F web -F sdk run lint"
  "web-arch|architecture|true|pnpm -F web run depcruise"
  "web-unit|correctness|true|pnpm -F web -F sdk run test:unit"
  "web-build|correctness|true|pnpm -F web run build"
  "api-integration|correctness|true|uv run pytest -q -m integration"
```

```bash
HARNESS_THRESHOLD=80   # AD-2 시작값. 근거: improvement-log/<P0-7 에서 발급된 id>
HARNESS_SELF_CHECK_LINK_DIRS="AGENTS.md CLAUDE.md PROVENANCE.md docs intents specs plans evaluation improvement-log"
```

### G. `.github/workflows/harness.yml` — 바꿀 부분

`verify` job 의 checkout 과 "하네스 검증" 사이에 도구 설치를 넣고, job 하나를 더합니다.

```yaml
      - uses: astral-sh/setup-uv@v5          # 확인: 최신 메이저
        with: { enable-cache: true }
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with: { node-version-file: .nvmrc, cache: pnpm }
      - run: uv sync --frozen
      - run: pnpm install --frozen-lockfile
```

```yaml
  secrets:
    name: 비밀값 스캔
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2      # 확인: 라이선스 조건. 조직 저장소는 키가 필요할 수 있습니다
```

## 관련 문서

- [../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) — R, D, C 의 정본
- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — 단위의 범위와 완료 판정
- [../harness/rules/harness-change-control.rule.md](../harness/rules/harness-change-control.rule.md) — H-2 의 절차
- [../harness/rules/evaluation-integrity.rule.md](../harness/rules/evaluation-integrity.rule.md) — EI-2(임계값), EI-7(미측정 표기)
- [../AGENTS.md](../AGENTS.md) — 예산과 중단
- [README.md](README.md) — plan 의 규칙
