# Plan 0001 — Phase 0: Architecture & Foundation

| 키 | 값 |
| --- | --- |
| 번호 | 0001 |
| 근거 spec | [../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) (승인됨 2026-09-09) |
| 근거 intent | [../intents/0001-phase-0-foundation.md](../intents/0001-phase-0-foundation.md) |
| 작업 단위 | [../intents/mvp-backlog.md](../intents/mvp-backlog.md) P0-1 ~ P0-9 |
| 작성일 | 2026-09-09 |
| 상태 | 승인됨 |
| 승인 | showjihyun, 2026-09-09 (리뷰 F-1 ~ F-6, P-1 ~ P-7 반영본) |
| 개정 | — |

spec 이 정한 요구사항(R)·결정(D)·계약은 반복하지 않습니다. 이 문서는 아홉 단위를 어떤 순서로 하고, 단위마다 어느 파일을 누가 만들며, 게이트가 켜지기 전에는 무엇으로 판정하는지를 정합니다.

이 plan 이 풀어야 하는 문제는 하나입니다. spec C-1 — **보호 패턴에 걸리는 파일은 에이전트가 만들 수 없습니다.** `tsconfig.json`, `eslint.config.*`, `.importlinter`, `.dependency-cruiser.*`, `harness.config`, `harness.yml` 이 그것입니다. 이 파일들이 아홉 단위 곳곳에 흩어져 있으면 사람이 매 단위마다 불려 나옵니다. 그래서 사람 손이 필요한 순간을 **세 순간**으로 묶었습니다 — 접촉은 다섯 번입니다(3절).

## 1. 순서

의존 그래프(backlog 의 `의존` 열)에서 유도했습니다. 한 wave 안의 단위는 서로 독립이라 순서를 바꿔도 됩니다. 에이전트 세션 하나에 단위 하나입니다. 그 세션은 **`.claude/agents/implementer.md`(Sonnet 5)** 가 맡습니다 — 코드 작성과 테스트 실행은 비용이 낮은 모델로, plan 갱신·H-* 준비물·리뷰·커밋은 주 세션이([../AGENTS.md](../AGENTS.md) Loop). 판정은 모델과 무관하게 4절의 명령입니다.

| Wave | 단위 | 왜 이 자리인가 | 사람 손 |
| --- | --- | --- | --- |
| 1 | **P0-1** 모노레포 뼈대 | 모든 것의 의존. 보호 파일 다섯 개가 여기서 필요합니다 | **H-1** (착수 전 선행) |
| 2 | **P0-6** AR-* 기계 판정 | H-1 로 규칙 파일이 생긴 직후, 코드가 비어 있을 때 부정 테스트를 붙이는 것이 가장 쌉니다. 이후 모든 단위가 이 규칙 아래에서 작성됩니다 | — |
| 2 | **P0-2** api 최소 기동 | P0-1 만 필요 | — |
| 2 | **P0-4** worker 최소 기동 | P0-1 만 필요. P0-2 와 병렬 가능 | — |
| 3 | **P0-3** sdk + web | P0-2 의 OpenAPI 가 필요 | — |
| 3 | **P0-3b** UI 기반(Tailwind + shadcn/ui + 앱 셸) | P0-3 직후. 같은 `apps/web` 을 만지므로 병렬 불가. `DESIGN.md` 를 코드로 옮기는 단위(spec 개정 6) | — |
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
| 2 | `apps/api`, `apps/worker`, `packages/{runtime,workflow,context,memory,mcp,policy,evaluation}` — 각각 `pyproject.toml` + `README.md`(책임 한 문장 = architecture.md 2절) + `src/aether_<이름>/` 아래 빈 껍데기: `domain/`, `application/ports/inbound/`, `application/ports/outbound/`, `application/usecases/`, `adapters/inbound/`, `adapters/outbound/` — 각각 `__init__.py` (중간 패키지 `application/`, `application/ports/`, `adapters/` 포함). `apps/*` 에는 `main.py` 자리(AR-8 ~ AR-12, spec D-13) | A (W) |
| 3 | `uv sync --all-packages` → `uv.lock`. 루트가 `package = false` 가상 워크스페이스라 옵션 없는 `uv sync` 는 멤버를 설치하지 않고 **제거**합니다(P0-1 실행에서 확인) | A (W) |
| 4 | 루트 `package.json`(`engines`, devDependencies 는 spec 2.2 의 도구 전부 — typescript, eslint, @eslint/js, typescript-eslint, @next/eslint-plugin-next, dependency-cruiser, vitest, openapi-typescript …), `pnpm-workspace.yaml`, `.nvmrc` | A (W) |
| 5 | `apps/web/package.json`(`@aether/web`), `packages/sdk/package.json`(`@aether/sdk`) — 스크립트 이름은 spec 2.2 의 규칙대로 전부 등록, 내용은 아직 비어도 됨 | A (W) |
| 6 | `pnpm install` → `pnpm-lock.yaml` | A (W) |
| 7 | H-1 의 다섯 파일(`apps/web/tsconfig.json`, `packages/sdk/tsconfig.json`, `eslint.config.js`, `.importlinter`, `.dependency-cruiser.cjs`)이 **이미 있는지 확인**. H-1 은 이 단위 착수 전에 끝나 있습니다(3절). 없으면 시작하지 않고 보고 | A |
| 8 | `infra/docker/README.md`, `infra/kubernetes/README.md` 한 줄씩 | A |
| 9 | 판정: `uv sync --all-packages` 와 `pnpm install` 이 깨끗한 checkout 에서 성공. `PYTHONUTF8=1 uv run lint-imports` exit 0 — 코드가 없어 공허하게 통과하며, 빈 코드에서도 성립하는 것은 부록 D 의 `unmatched_ignore_imports_alerting = warn` 덕입니다. `PYTHONUTF8` 은 Windows 의 locale(cp949)이 `.importlinter` 의 UTF-8 주석을 못 읽기 때문입니다. 트리가 spec 2.1 표와 일치 | A |

`packages/sdk` 는 `src/index.ts` 빈 export 하나만 둡니다. 내용은 P0-3.

### P0-6 AR-* 를 기계 판정으로

H-1 이 규칙 파일을 만들었으므로 이 단위는 **규칙이 동작함을 증명**하는 일입니다.

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `tests/arch/fixtures/ar_violation/` — `bad_runtime/__init__.py`(`import bad_api`), `bad_api/__init__.py`, `importlinter.ini`(bad_runtime → bad_api 금지). **파일 이름이 `.importlinter` 가 아니어야** 에이전트가 만들 수 있습니다 | A |
| 2 | `tests/arch/fixtures/ar1_violation/` — `apps/web/page.ts` 가 `../../packages/runtime/index.ts` 를 import 하고 **그 파일이 fixture 안에 실재**합니다(해석되지 않는 import 는 경로 매칭이 달라져 규칙이 발화하지 않을 수 있습니다). `depcruise.fixture.cjs` | A |
| 2b | `tests/arch/fixtures/inward_violation/` — `pkg/domain/__init__.py` 가 `pkg.adapters` 를 import(AR-8 위반), `pkg/application/usecases/uc.py` 가 `fastapi` 를 import(AR-9 위반), `pkg/adapters/inbound/__init__.py` 가 `pkg.adapters.outbound` 를 import(AR-11 위반), `pkg/adapters/inbound/http.py` 가 `pkg.application.usecases` 를 import(AR-12 위반). `importlinter.ini` 에 네 계약 | A |
| 3 | `tests/arch/test_import_linter.py` — (a) 두 fixture 로 `lint-imports --config importlinter.ini` 가(fixture 디렉터리를 `PYTHONPATH` 에 넣고 실행) exit ≠ 0 이고 출력에 위반한 계약 이름이 각각 보임, (b) 실제 `.importlinter` 를 파싱해 `ar2`·`ar3`·`ar4`·`ar5`·`ar6`·`ar7`·`ar8`·`ar9`·`ar11`·`ar12` 접두사 계약이 전부 있음, (c) 실제 `uv run lint-imports` 가 exit 0 | A |
| 4 | `tests/arch/test_depcruise.py` — fixture 로 exit ≠ 0. 실제 규칙의 exit 0 확인은 web 에 TS 파일이 생기는 **P0-3 의 판정**으로 옮깁니다(지금 web 은 비어 있습니다) | A |
| 5 | `web-arch` 는 **루트에서** 실행합니다: `pnpm exec depcruise apps/web --config .dependency-cruiser.cjs`. `apps/web` 안에서 돌리면 부록 E 의 `^apps/web/` 이 cwd 기준으로 매칭되지 않아 규칙이 영영 발화하지 않습니다(리뷰 F-2). web 에 `depcruise` 스크립트를 두지 않습니다 | A |
| 6 | 판정: 3·4 의 테스트 전부 통과. AR-7 의 planner/executor 부분은 모듈이 없어 등록하지 않음 — spec 2.10 대로 Phase 1 | A |

첫 실행에서 부록 D·E 의 설정이 도구에 거부되면 **에이전트는 고칠 수 없습니다**(보호 파일). 거부 메시지와 고친 내용을 사람에게 넘기고, 사람이 반영합니다. 이것이 H-1 의 후속입니다.

### P0-2 `apps/api` 최소 기동

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `apps/api/src/aether_api/` — `settings.py`(`AETHER_` 접두사, 기본값으로 뜸), `adapters/outbound/telemetry.py`(OTel 초기화, exporter 는 env 있을 때만), `adapters/inbound/http/healthz.py`(라우터. 상수를 답하는 유스케이스 없는 순수 inbound 어댑터 — `application` 을 import 하지 않습니다), `adapters/inbound/cli.py`(`openapi` 서브커맨드의 **함수만** — 조립된 앱을 인자로 받아 OpenAPI JSON 을 stdout 으로. P0-3 이 씁니다), `main.py`(조립: FastAPI 앱 생성, 라우터 등록, telemetry 초기화, 그리고 **CLI 진입점 `cli()`** — 조립한 것을 `adapters/inbound/cli.py` 의 함수에 건넵니다. 어댑터가 `main` 을 import 하면 AR-10 이 뒤집히고 순환이 생깁니다 — AR-10) | A |
| 2 | `apps/api/pyproject.toml` 에 `[project.scripts] aether-api = "aether_api.main:cli"` — 진입점은 조립 지점입니다(리뷰 F-6) | A (W) |
| 3 | `apps/api/tests/test_healthz.py` — 200, 스키마 `{status, service, version}`, `version` 기본값 `dev` | A |
| 4 | 판정: `uv run pytest apps/api -q` 통과. `uv run uvicorn aether_api.main:app` 기동 후 `curl /healthz` 200. 기동 로그에 외부 호출 없음 | A |

### P0-4 `apps/worker` 최소 기동

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `apps/worker/src/aether_worker/` — `settings.py`, `adapters/inbound/stream.py`(Redis Streams `aether:runs:requested` 에 consumer group 생성·블록 읽기. 처리 없음 — 스트림 소비자는 시스템을 움직이는 쪽이므로 inbound), `domain/backoff.py`(재시도 정책 — 순수 규칙. 시계는 주입), `main.py`(조립, SIGTERM 핸들러) | A |
| 2 | `apps/worker/tests/test_backoff.py`(단위. 시계 주입), `apps/worker/tests/test_connect.py`(`integration` 마커. testcontainers Redis 로 ready 로그와 5초 내 종료) | A |
| 3 | 판정: 단위 테스트 통과. `uv run pytest apps/worker -q -m integration` 통과 | A |

### P0-3 `packages/sdk` 와 `apps/web` 최소 기동

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `uv run aether-api openapi > packages/sdk/openapi.json` | A |
| 2 | `packages/sdk` — `scripts.generate = "openapi-typescript openapi.json -o src/generated/openapi.d.ts"`, 실행해 생성물 커밋. `src/client.ts`(`createClient({ baseUrl, apiKey })`, `healthz()`), `src/index.ts`, `src/client.test.ts`(Vitest, fetch 를 주입해 경로·헤더 확인). sdk 는 `vitest.config.ts` 를 두지 않습니다 — Vitest 기본(node 환경)으로 충분하고, 패키지 루트의 설정 파일은 보호 파일 `tsconfig.json`(`include: ["src"]`)과 `eslint.config.js`(`projectService`) 조합에서 파서 오류를 냅니다(P0-3 에서 확인) | A (W) |
| 3 | `apps/web` — `app/layout.tsx`, `app/page.tsx`(서버 컴포넌트에서 sdk 의 `healthz()` 호출, 결과 표시. **동적 렌더링으로 고정** — `fetch(..., { cache: "no-store" })` 또는 `export const dynamic = "force-dynamic"`. 정적 프리렌더가 빌드 시 API 를 부르면 `web-build` 가 API 없이 실패합니다(리뷰 F-4)), `next.config.ts`(`transpilePackages: ["@aether/sdk"]`), `vitest.config.ts`(jsdom), 컴포넌트 테스트 1건. **`next build` 는 `apps/web/tsconfig.json`(보호)을 다시 씁니다** — `jsx: react-jsx`, `include` 에 `.next/dev/types/**/*.ts`, 그리고 CRLF. 되돌려도 다음 빌드에 또 바뀌므로 그 내용을 받아들이고 사람이 커밋합니다(H-1 후속. `.gitattributes` 가 LF 로 정규화) | A (W) |
| 4 | `apps/api/tests/test_openapi_drift.py` — `aether-api openapi` 출력을 **파싱해** 커밋된 `packages/sdk/openapi.json` 과 비교(텍스트 비교는 키 순서·공백에 깨집니다) | A |
| 5 | 판정: `pnpm -F sdk run generate && git diff --exit-code HEAD -- packages/sdk/src/generated && test -z "$(git status --porcelain packages/sdk/src/generated)" && pnpm -F web -F sdk run typecheck`(`HEAD` 와 미추적 확인이 없으면 첫 생성 때 공허하게 통과합니다). `pnpm -F web -F sdk run lint`, `run test:unit`. `pnpm -F web run build`. **`pnpm exec depcruise apps/web --config .dependency-cruiser.cjs` exit 0** — P0-6 에서 옮겨 온 실통과 검사 | A |

### P0-3b UI 기반: Tailwind + shadcn/ui + 앱 셸

[../DESIGN.md](../DESIGN.md) 가 결정을 소유합니다. 이 단위는 그것을 설치하고 셸을 세우는 일이며, 새 시각적 결정을 하지 않습니다.

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | Tailwind CSS v4: `pnpm -F web add -D tailwindcss @tailwindcss/postcss postcss`, `apps/web/postcss.config.mjs`, `app/globals.css` 에 `@import "tailwindcss"` | A (W) |
| 2 | `pnpm -F web dlx shadcn@latest init` — style `new-york`, base color `neutral`, CSS variables. 생성되는 `components.json`, `lib/utils.ts`(`cn`), `globals.css` 토큰을 그대로 둠. **`tsconfig.json` 의 `paths`(`@/*`)는 부록 B 에 이미 있음 — init 이 tsconfig 를 고치려 하면 diff 를 보고(H-1 후속)** | A |
| 3 | DESIGN.md 4절의 초기 세트 `pnpm -F web dlx shadcn@latest add button input textarea label card badge alert skeleton separator scroll-area table tabs dialog sheet dropdown-menu tooltip sonner`. `components/ui/*` 커밋 | A |
| 4 | `next-themes`(`ThemeProvider`, 헤더 토글), Geist(`next/font`), `lucide-react` | A (W) |
| 5 | `components/AppShell.tsx` — DESIGN.md 5절의 셸. 사이드바 항목 5개(Agents·Runs·Knowledge·Workflows·Settings — 링크 자리만, 대상 페이지는 MVP-2), `lg` 미만은 `sheet`. `app/layout.tsx` 가 이것으로 감쌈 | A |
| 6 | `components/RunStatusBadge.tsx` — 6절 표를 코드로(7개 상태 × variant × 아이콘). `RunStatusBadge.test.tsx` 가 7개를 전부 렌더해 텍스트·아이콘 존재 확인 | A |
| 7 | `app/page.tsx` 를 다시 표현: `card` 안에 status·service·version, 오류 시 `alert destructive`(DESIGN.md 7절). 서버 컴포넌트·동적 렌더링은 P0-3 그대로 | A |
| 8 | 판정: `pnpm -F web run typecheck`·`lint`·`test:unit`·`build` 0(API 없이). `pnpm exec depcruise apps/web --config .dependency-cruiser.cjs` 0. grep — `app/`·`components/`(ui 제외)에 `@radix-ui` import 0건, `bg-[`·`text-[#`·`-slate-`·`-gray-`·`-zinc-` 0건. `git diff --stat apps/web/tsconfig.json eslint.config.js` 비어 있음. 실동작: api + `next start` 로 `/` 가 카드로 렌더 | A |

`eslint.config.js`(보호)가 Tailwind·shadcn 코드에서 새 규칙 위반을 내면(예: `react/no-unknown-property`), 코드를 규칙에 맞추는 것이 먼저이고 규칙을 바꾸는 것은 사람의 일입니다.

### P0-8 데이터 모델 v1

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | **red** — `apps/api/tests/conftest.py`(`integration`: testcontainers PostgreSQL 기동 → 역할 두 개 생성 → `alembic upgrade head`), `tests/test_migrations.py`(up → down → up 왕복), `tests/test_agent_version_immutable.py`(**관리자 역할로** UPDATE·DELETE → 트리거 예외), `tests/test_plane_roles.py`(`aether_control` 로 `SELECT FROM data.run_executions` → permission denied. `aether_data` 로 `control.agent_versions` SELECT 성공, INSERT 실패). `uv run pytest apps/api -q -m integration` 을 **실행해 실패를 기록** — 마이그레이션이 없어 `alembic upgrade` 부터 실패합니다 | A (W) |
| 2 | `infra/docker/postgres/init/01-roles.sh` — `aether_control`, `aether_data` 역할만. plain SQL 은 env 를 읽지 못하므로 셸에서 `psql -v` 로 비밀번호를 넘깁니다. 실행 비트 필요(5절). P0-5 의 compose 가 마운트. conftest 의 역할 생성은 이 파일과 같은 SQL 을 씁니다 | A |
| 3 | **green** — `apps/api/migrations/`(`alembic.ini`, `env.py`, `script.py.mako`), `versions/0001_schemas_and_roles_grants.py` — `CREATE SCHEMA control, data`, 다섯 테이블(spec 2.8 표), `agent_versions` 불변 트리거, `run_executions.status` enum, GRANT 두 역할. `downgrade` 는 전부 되돌림. 1번의 테스트가 전부 통과할 때까지 — 그 이상을 만들지 않습니다 | A |
| 4 | **refactor** — 마이그레이션 정리. 테스트는 바꾸지 않습니다 | A |
| 5 | `docs/data-model.md` — 열의 정본. cross-schema FK 의 수명(spec C-8)을 적음. `docs/README.md` 의 "아직 없는 문서" 에서 행 제거 | A |
| 6 | 판정: `uv run pytest apps/api -q -m integration` 통과. 보고의 `red 증거` 에 1번의 실패 실행과 3번의 통과 실행 | A |

### P0-5 Docker Compose 와 루트 README

설정 단위라 테스트 우선이 성립하지 않습니다. `red 증거` 는 착수 시점에 판정 명령(`docker compose … run probe`)이 실패함을 기록한 것으로 대신하고, 끝에 같은 명령의 성공을 기록합니다.

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | `infra/docker/api.Dockerfile`, `worker.Dockerfile`, `web.Dockerfile` — 베이스 이미지 digest 고정, 빌드 인자 `AETHER_VERSION`, 빌드 컨텍스트는 저장소 루트(uv workspace 전체가 필요). **루트 `.dockerignore`**(`.env*`, `.git`, `node_modules`, `.venv`, `.next`, `dist`) — Docker 는 빌드 컨텍스트 루트의 것만 읽습니다. `infra/docker/` 에 두면 무시되고 `.env` 가 이미지에 들어갑니다(리뷰 F-1) | A |
| 2 | `infra/docker/compose.yaml` — postgres(init 마운트, healthcheck), redis(AOF, healthcheck), migrate(일회성, 관리자 역할), api(`service_completed_successfully` on migrate), worker, web. `infra/docker/.env.example` 전체 키, 비밀값 자리는 `<generate>`. 실제 `.env` 도 compose 파일 옆 `infra/docker/.env` — compose 는 자기 디렉터리의 `.env` 를 읽습니다(`.gitignore` 의 `.env` 패턴은 깊이 무관) | A (W) |
| 3 | `infra/docker/compose.offline.yaml` — 네트워크 `internal: true`, `probe` 서비스(curl 이미지, `api:8000/healthz` 와 `web:3000/` 200 확인 후 exit 0) | A (W) |
| 4 | 루트 `README.md` — 기동 명령(`docker compose -f infra/docker/compose.yaml up`), 개발 설치 명령(`uv sync --all-packages`, `pnpm install`), verify 명령, 문서 지도 링크. 두 홉 규칙(spec R-1) | A |
| 5 | 판정: 온라인에서 README 의 명령 → healthz 200, web 200 (R-1). 이미지 빌드 후 `docker compose -f … -f compose.offline.yaml run probe` exit 0 (R-4). `docker history` 로 이미지에 `.env` 없음 (R-6) | A |

### P0-7 `harness.config` 제품 단계 활성화와 CI

코드가 없는 단위입니다. `red 증거` 는 "해당 없음 — 게이트 설정" 으로 적습니다.

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | 로컬에서 spec 2.11 의 열 명령을 **손으로 순서대로** 실행해 전부 exit 0 임을 먼저 확인. 하나라도 실패하면 이 단위를 시작하지 않고 해당 단위로 돌아감 | A |
| 2 | 열 명령의 실행 시간을 합산해 기록. 10분(D-12)을 넘기면 H-2 전에 사람에게 보고 | A |
| 3 | `./harness/scripts/improvement-log.sh new` 로 임계값 90 → 80 의 근거 항목 1건 (intent Constraints 의 예외 조항) | A |
| 4a | **H-2a**: `harness.config`(부록 F — 주석 블록을 단계 표로 교체, `HARNESS_THRESHOLD=80`, `HARNESS_SELF_CHECK_LINK_DIRS` 에 `specs plans`). PR 에 `harness-change` 라벨. 병합 후 로컬 verify 통과 확인 | **H** |
| 4b | **H-2b**: `.github/workflows/harness.yml`(부록 G — uv·pnpm 설치, gitleaks job). **별도 PR**, `harness-change` 라벨. 보호 파일은 한 번에 하나(spec C-2) | **H** |
| 5 | 판정: `./harness/scripts/verify.sh` pass, `verify.json` 에 16단계. CI 녹색. `duration_ms` 합계 기록 (R-11) | A |

### P0-9 🔒 인증 기준선

| 순서 | 무엇 | 누가 |
| --- | --- | --- |
| 1 | **포트와 테스트만**: inbound 포트 `application/ports/inbound/authenticate.py`(`Authenticate` Protocol), `application/ports/inbound/issue_api_key.py`(`IssueApiKey` Protocol); outbound 포트 `application/ports/outbound/api_keys.py`(`ApiKeyStore` Protocol — `find_by_hash`, `create`, `revoke`). docstring 에 spec 2.9 의 결정. **실패하는 테스트**: `tests/test_authenticate.py`(fake `ApiKeyStore` 로 컨테이너 없이 — 유효 키 통과, 폐기된 키 거부, 잘못된 형식 거부, constant-time 비교 사용), `tests/test_api_key_store_contract.py`(**포트 계약 테스트** — 같은 케이스를 fake 와 PostgreSQL 구현에. 후자는 `integration` 마커), `tests/test_auth_http.py`(보호 경로 401, `/healthz` 200 — `Authenticate` 포트에 fake 를 꽂아). 전부 **실행해 실패를 기록**합니다 — red | A |
| 2 | **H-3 (설계 검토)**: 사람이 인터페이스와 테스트 목록을 검토. 통과 전에 구현하지 않음 | **H** |
| 3 | 구현: `application/usecases/authenticate.py`·`issue_api_key.py`(키 생성 `aeth_` + 256-bit, SHA-256, constant-time 비교 — 전부 표준 라이브러리. outbound 포트 `ApiKeyStore` 만 봄), `adapters/outbound/db/api_keys.py`(`ApiKeyStore` 의 PostgreSQL 구현), `adapters/inbound/http/auth.py`(`Depends` — `Authenticate` **포트 타입**을 받아 라우터 전체에 적용, `/healthz` 제외), `adapters/inbound/cli.py` 에 `keys create --label`(`IssueApiKey` 포트를 부름). `main.py` 에서 조립: 유스케이스에 PostgreSQL 어댑터를 꽂고, 라우터와 CLI 에 유스케이스를 포트 타입으로 건넴. CLI 진입점은 P0-2 의 `main:cli` 그대로(AR-10·AR-12). 1번의 테스트가 전부 통과 — green. 그 뒤 정리(refactor)에서 테스트는 바꾸지 않습니다 | A |
| 4 | **H-3 (구현 검토)**: PR 리뷰. 비밀값이 로그·테스트 fixture 에 원문으로 없는지 | **H** |
| 5 | 판정: `verify.sh` pass(P0-7 뒤이므로 게이트가 켜져 있음). R-9 의 테스트 통과 | A |

## 3. 사람 손

순간은 셋, 접촉은 다섯입니다 — H-1, H-2a, H-2b, H-3 설계 검토, H-3 PR 리뷰. 부록의 설정이 도구에 거부되면 H-1 의 후속이 하나 더 생깁니다. 각 순간에 에이전트가 무엇을 준비해 넘기는지를 적습니다. 사람이 빈손으로 시작하지 않게 하는 것이 이 절의 목적입니다.

| 순간 | 언제 | 사람이 하는 일 | 에이전트가 넘기는 것 |
| --- | --- | --- | --- |
| **H-1** | **P0-1 착수 전** | 보호 파일 다섯 개를 만들어 커밋: `apps/web/tsconfig.json`, `packages/sdk/tsconfig.json`, `eslint.config.js`, `.importlinter`, `.dependency-cruiser.cjs` | 부록 A~E 의 내용. `.importlinter` 는 AR-2 ~ AR-9, AR-11, AR-12 의 열한 계약. P0-6 에서 도구가 거부한 항목이 있으면 그 diff |
| **H-2a** | P0-7 의 4a | `harness.config` 를 고쳐 `harness-change` 라벨 PR 로 병합. 임계값 90 → 80 은 EI-2 상 사람의 결정 | 부록 F 의 내용. 열 명령이 로컬에서 전부 통과한 기록. 실행 시간 합계. improvement-log 항목 id |
| **H-2b** | P0-7 의 4b | `.github/workflows/harness.yml` 을 고쳐 **별도** `harness-change` PR 로 병합 | 부록 G 의 내용. H-2a 병합 후 로컬 verify 가 통과한 기록 |
| **H-3** | P0-9 의 2번과 4번 | 인증의 설계 검토(구현 전)와 PR 리뷰(구현 후) | 인터페이스 파일, 실패하는 테스트 목록, spec 2.9 대비 차이가 있으면 그 목록 |

H-1 을 P0-1 의 **선행 조건**으로 둔 이유: 단위 안에 두면 에이전트 세션이 사람을 기다리며 멈춥니다. 부록 A~E 의 내용은 P0-1 의 나머지와 독립이라 먼저 만들어도 잃는 것이 없고, `.importlinter` 가 아직 없는 패키지를 가리키는 것은 P0-1 이 끝나기 전에는 아무도 `lint-imports` 를 돌리지 않으므로 문제가 아닙니다.

## 4. 판정 절차

**P0-7 전.** `harness.config` 에는 self-check 6단계만 있어 `verify.sh` 는 제품 코드를 보지 않습니다. 그래서 P0-1 ~ P0-5 와 P0-8 은 spec 2.11 의 명령을 **손으로** 실행해 판정합니다. 단위를 끝낼 때 다음을 순서대로 실행하고 전부 exit 0 이어야 합니다.

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
PYTHONUTF8=1 uv run lint-imports
uv run pytest -q -m 'not integration'
pnpm -F sdk run generate && git diff --exit-code HEAD -- packages/sdk/src/generated && test -z "$(git status --porcelain packages/sdk/src/generated)" && pnpm -F web -F sdk run typecheck
pnpm -F web -F sdk run lint
pnpm exec depcruise apps/web --config .dependency-cruiser.cjs
pnpm -F web -F sdk run test:unit
pnpm -F web run build
uv run pytest -q -m integration
./harness/scripts/verify.sh          # self-check 는 여전히 통과해야 합니다
```

Windows 에서 testcontainers 가 Ryuk 컨테이너를 못 띄우면 integration 줄 앞에 `TESTCONTAINERS_RYUK_DISABLED=true` 를 붙입니다(P0-4 에서 확인. Linux CI 는 불필요). 아직 존재하지 않는 대상(예: P0-2 시점의 web)은 해당 줄을 건너뜁니다. 건너뛴 줄은 완료 보고에 "미측정" 으로 적습니다. 통과로 적지 않습니다(EI-7).

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
| 새 `.sh` 파일 | `git update-index --chmod=+x <파일>` 뒤에 커밋합니다. Windows 는 `core.fileMode=false` 라 100644 로 들어가고 Linux CI 가 exit 126 을 냅니다. 이 저장소의 첫 커밋이 그랬고, self-check 의 `syntax` 단계가 잡습니다 |

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
- [../CLAUDE.md](../CLAUDE.md) "아직 없는 것" 절 — `apps/`, `packages/`, `infra/` 가 이제 있으므로 절을 고침(대체할 항목과 함께)
- [../AGENTS.md](../AGENTS.md) 첫 문단 — "저장소에는 하네스 번들과 문서만" 이 거짓이 되므로
- [../PROVENANCE.md](../PROVENANCE.md) 8절 — 이력 한 줄

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
    google
# google 가 아니라 google 인 이유: import-linter 는 외부 패키지의 하위 패키지를
# 금지 대상으로 받지 않습니다("subpackages of external packages are not valid"). P0-1 에서 확인.
ignore_imports =
    aether_runtime.adapters.outbound.model_gateway.** -> openai
    aether_runtime.adapters.outbound.model_gateway.** -> anthropic
    aether_runtime.adapters.outbound.model_gateway.** -> google
unmatched_ignore_imports_alerting = warn
# 확인: ** 와일드카드는 import-linter 2.x. 미지원이면 어댑터 모듈을 개별 나열합니다.
# warn 인 이유: 위 ignore_imports 는 어댑터가 생기기 전까지 아무 import 도 매칭하지 않고,
# import-linter 의 기본값(error)은 그것을 실패로 봅니다. Phase 1 에 어댑터가 생기면 error 로 되돌립니다(사람).

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

# --- 패키지 안의 방향 (architecture.md 3.1) -----------------------------------

[importlinter:contract:ar8-inward-only]
name = AR-8 adapters -> application -> domain, inward only, in every package
type = layers
layers =
    adapters
    application
    domain
containers =
    aether_api
    aether_worker
    aether_runtime
    aether_workflow
    aether_context
    aether_memory
    aether_mcp
    aether_policy
    aether_evaluation

[importlinter:contract:ar9-core-is-framework-free]
name = AR-9 domain and application import no framework or I/O
type = forbidden
source_modules =
    aether_api.domain
    aether_api.application
    aether_worker.domain
    aether_worker.application
    aether_runtime.domain
    aether_runtime.application
    aether_workflow.domain
    aether_workflow.application
    aether_context.domain
    aether_context.application
    aether_memory.domain
    aether_memory.application
    aether_mcp.domain
    aether_mcp.application
    aether_policy.domain
    aether_policy.application
    aether_evaluation.domain
    aether_evaluation.application
forbidden_modules =
    fastapi
    starlette
    uvicorn
    sqlalchemy
    alembic
    psycopg
    asyncpg
    redis
    httpx
    aiohttp
    requests
    opentelemetry
    openai
    anthropic
    google
    mcp

[importlinter:contract:ar11-inbound-does-not-import-outbound]
name = AR-11 inbound adapters do not import outbound adapters
type = forbidden
source_modules =
    aether_api.adapters.inbound
    aether_worker.adapters.inbound
    aether_runtime.adapters.inbound
    aether_workflow.adapters.inbound
    aether_context.adapters.inbound
    aether_memory.adapters.inbound
    aether_mcp.adapters.inbound
    aether_policy.adapters.inbound
    aether_evaluation.adapters.inbound
forbidden_modules =
    aether_api.adapters.outbound
    aether_worker.adapters.outbound
    aether_runtime.adapters.outbound
    aether_workflow.adapters.outbound
    aether_context.adapters.outbound
    aether_memory.adapters.outbound
    aether_mcp.adapters.outbound
    aether_policy.adapters.outbound
    aether_evaluation.adapters.outbound

[importlinter:contract:ar11-outbound-does-not-import-inbound]
name = AR-11 outbound adapters do not import inbound adapters
type = forbidden
source_modules =
    aether_api.adapters.outbound
    aether_worker.adapters.outbound
    aether_runtime.adapters.outbound
    aether_workflow.adapters.outbound
    aether_context.adapters.outbound
    aether_memory.adapters.outbound
    aether_mcp.adapters.outbound
    aether_policy.adapters.outbound
    aether_evaluation.adapters.outbound
forbidden_modules =
    aether_api.adapters.inbound
    aether_worker.adapters.inbound
    aether_runtime.adapters.inbound
    aether_workflow.adapters.inbound
    aether_context.adapters.inbound
    aether_memory.adapters.inbound
    aether_mcp.adapters.inbound
    aether_policy.adapters.inbound
    aether_evaluation.adapters.inbound
[importlinter:contract:ar12-adapters-only-through-ports]
name = AR-12 adapters reach the application only through ports
type = forbidden
source_modules =
    aether_api.adapters
    aether_worker.adapters
    aether_runtime.adapters
    aether_workflow.adapters
    aether_context.adapters
    aether_memory.adapters
    aether_mcp.adapters
    aether_policy.adapters
    aether_evaluation.adapters
forbidden_modules =
    aether_api.application.usecases
    aether_worker.application.usecases
    aether_runtime.application.usecases
    aether_workflow.application.usecases
    aether_context.application.usecases
    aether_memory.application.usecases
    aether_mcp.application.usecases
    aether_policy.application.usecases
    aether_evaluation.application.usecases
# AR-10(조립은 apps/*/main.py 한 곳)은 어댑터가 실제로 생기는 Phase 1 에 forbidden 으로 승격합니다.
```

### E. `.dependency-cruiser.cjs` (루트)

```js
/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  // 반드시 저장소 루트에서 실행합니다: pnpm exec depcruise apps/web --config .dependency-cruiser.cjs
  // 아래 path 는 cwd 기준입니다. apps/web 안에서 돌리면 ^apps/web/ 이 매칭되지 않아 규칙이 발화하지 않습니다.
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
    // 절대 경로여야 합니다. dependency-cruiser 18 은 이 값을 TypeScript 의
    // parseJsonConfigFileContent 5번째 인자로 그대로 넘기고, 상대 경로면 include 가
    // 0건 매치해 TS18003 으로 죽습니다(P0-3 에서 확인).
    tsConfig: { fileName: require("node:path").resolve(__dirname, "apps/web/tsconfig.json") },
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
  "api-arch|architecture|true|PYTHONUTF8=1 uv run lint-imports"
  "api-unit|correctness|true|uv run pytest -q -m 'not integration'"
  "web-typecheck|quality|true|pnpm -F sdk run generate && git diff --exit-code HEAD -- packages/sdk/src/generated && test -z '$(git status --porcelain packages/sdk/src/generated)' && pnpm -F web -F sdk run typecheck"
  "web-lint|quality|true|pnpm -F web -F sdk run lint"
  "web-arch|architecture|true|pnpm exec depcruise apps/web --config .dependency-cruiser.cjs"
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
      - run: uv sync --all-packages --frozen
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
