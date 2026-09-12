# MVP 작업 단위 (backlog)

이 문서는 로드맵 10장 **Month 4 — Technical MVP** 까지 해야 할 일을, 에이전트가 한 번에 하나씩 집어 끝낼 수 있는 크기로 쪼갠 목록입니다. 원본은 [../Open_Hybrid_Enterprise_AI_OS_Final_Roadmap.md](../Open_Hybrid_Enterprise_AI_OS_Final_Roadmap.md) 5~10장이고, 계층·용어는 [../docs/architecture.md](../docs/architecture.md) 와 [../docs/domain.md](../docs/domain.md) 의 것만 씁니다.

이 문서는 intent 가 아닙니다. **아직 발급하지 않은 intent 와 그 안의 작업 단위를 미리 적어 둔 후보 목록**입니다. 승인 절차는 intent 가 발급될 때 그 파일에서 밟습니다.

## MVP 가 무엇인가

로드맵 10장이 정한 것을 그대로 옮깁니다.

| 항목 | 값 |
| --- | --- |
| 목표 | Offline-capable Portable AI Runtime |
| 반드시 되어야 하는 시나리오 | `docker compose up` → 인터넷 없이 → Local LLM → Local Vector DB → Local MCP → Agent 실행 성공 |
| KPI | **Time to First Successful Agent < 10분** (clone 부터 첫 Run 성공까지) |
| 포함 기능 | Agent, Agent Runtime, MCP, Context, Memory, Workflow, CLI, Basic UI, Streaming, Trace |
| 포함 Phase | 0 Foundation, 1 Agent Runtime, 2 MCP Gateway, 3 Context/RAG, 4 Workflow |

MVP 에 **없는 것**: Visual Agent Builder(5), Model Registry(6), 제품 Evaluation(7), Trust Layer(8), Policy Engine(9), MCP Firewall(10), Air-Gapped 번들(11), Passport(12), Marketplace(13). 이 목록에 있는 것을 "미리 준비" 하지 않습니다([../docs/roadmap.md](../docs/roadmap.md) "이 표를 쓰는 법").

## 쪼갠 기준

| 원칙 | 뜻 |
| --- | --- |
| 단위 하나 = 세션 하나 | 한 에이전트 세션의 반복 예산(8회) 안에서 끝납니다. 넘치면 단위가 큰 것이지 예산이 작은 것이 아닙니다 |
| 완료 판정은 실행으로 | 모든 단위의 `완료 판정` 은 `./harness/scripts/verify.sh` 또는 실제 실행으로 확인할 수 있는 명제입니다. "잘 동작한다" 는 판정이 아닙니다 |
| **테스트가 먼저** | 동작이 있는 단위는 `완료 판정` 의 테스트를 **먼저 쓰고 실패를 본 뒤** 구현합니다(red → green → refactor). 구현 세션의 보고 `red 증거` 가 그것을 증명하고, 없으면 리뷰가 반려합니다. 테스트가 성립하지 않는 단위(설정·문서·compose)는 그 사실을 적습니다 — 빈칸이 아니라 |
| 수직으로 자릅니다 | 계층 하나를 통째로 만들지 않고, 위에서 아래까지 관통하는 얇은 조각을 먼저 만듭니다. 계층 경계(AR-*)가 실제 호출로 검증되는 것은 이때뿐입니다 |
| 의존은 번호로 | `의존` 에 적힌 단위가 `완료` 가 아니면 시작하지 않습니다. 병렬 가능한 단위는 의존이 같습니다 |
| 게이트는 사람이 엽니다 | `게이트` 에 적힌 열린 질문이 닫히기 전에는 시작하지 않습니다. 추측으로 명령을 적으면 그 명령이 검증 게이트가 됩니다 |
| 🔒 는 사람 검토 | 인증·권한·비밀값·Policy·승인에 닿는 단위입니다. 에이전트가 진행하지 않고 설계를 제안한 뒤 사람 검토로 넘깁니다([../AGENTS.md](../AGENTS.md) Loop) |

## 에이전트가 단위를 집는 순서

1. [intent.md](intent.md) 를 열어 활성 intent 가 어느 Phase 인지 봅니다. 그 Phase 밖의 단위는 집지 않습니다.
2. 그 Phase 안에서 `상태` 가 `대기` 이고 `의존` 이 전부 `완료` 이며 `게이트` 가 닫힌 단위 중 **번호가 가장 작은 것**을 집습니다.
3. 단위의 `범위 밖` 을 먼저 읽습니다. 그것을 하고 싶어지는 순간이 범위가 번지는 순간입니다.
4. 끝나면 `완료 판정` 의 명제를 실제로 실행해 확인하고, 이 표의 `상태` 를 같은 커밋에서 `완료` 로 바꿉니다.
5. 단위를 끝내며 겪은 반복 실패는 `improvement-log/` 후보로 남깁니다. 이 문서에 규칙을 적지 않습니다.

Phase 가 바뀔 때는 새 intent 를 발급합니다(`cp _template.md NNNN-<슬러그>.md`). 그 intent 의 `Proposed Outcome` 은 아래 각 Phase 의 `Phase 완료 판정` 이고, `Non-goals` 는 다음 Phase 의 단위입니다.

## 상태 값

`대기` · `진행` · `완료` · `보류`(게이트 또는 사람 검토 대기). 한 시점에 `진행` 은 하나입니다.

**완료의 정의**는 하나입니다: 완료 판정 통과 + 주 세션 리뷰(판정 재현, `red 증거` 확인) + **PR 이 CI 를 통과해 사람이 병합** + backlog `상태`·관련 문서 갱신. 병합 전에는 `진행` 입니다.

---

## Phase 0 — Architecture & Foundation

Intent: [0001](0001-phase-0-foundation.md) (승인됨 2026-09-08 · **완료 2026-09-11**, 마지막 PR #10). Spec: [../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) (승인됨 2026-09-09). Plan: [../plans/0001-phase-0-foundation.md](../plans/0001-phase-0-foundation.md) (승인됨 2026-09-09 — 순서는 plan 이 소유하며 P0-6 을 앞당깁니다). 기간: Week 1~2.

**Phase 완료 판정** — 새로 clone 한 사람이 저장소 정보만으로 명령 하나를 찾아 실행하면 Web 과 API 가 뜨고, `verify.sh` 가 제품 코드를 실제로 검사하며, AR-2·AR-3·AR-5 위반이 `arch-test` 에서 exit 0 이 아닌 값으로 드러나고, `docker compose up` 이 인터넷 없이 성립합니다.

| 번호 | 단위 | 의존 | 게이트 | 상태 |
| --- | --- | --- | --- | --- |
| P0-1 | 모노레포 뼈대와 빈 패키지 경계 | — | — | 완료 |
| P0-2 | `apps/api` 최소 기동 | P0-1 | — | 완료 |
| P0-3 | `packages/sdk` 와 `apps/web` 최소 기동 | P0-2 | — | 완료 |
| P0-3b | UI 기반: Tailwind + shadcn/ui + 앱 셸 | P0-3 | — | 완료 |
| P0-4 | `apps/worker` 최소 기동 | P0-1 | — | 완료 |
| P0-5 | Docker Compose 로 전부 기동 | P0-2, P0-3, P0-4 | — | 완료 |
| P0-6 | AR-* 를 기계 판정으로 | P0-1 | — | 완료 |
| P0-7 | `harness.config` 제품 단계 활성화와 CI | P0-5, P0-6 | — | 완료 |
| P0-8 | 데이터 모델 v1 (Agent / Agent Version / Run) | P0-2 | — | 완료 |
| P0-9 | 🔒 인증 기준선 | P0-8 | — | 완료 |

### P0-1 모노레포 뼈대와 빈 패키지 경계

| 항목 | 내용 |
| --- | --- |
| 범위 | 로드맵 Phase 0 의 트리를 그대로 만듭니다: `apps/{web,api,worker}`, `packages/{runtime,workflow,context,memory,mcp,policy,evaluation,sdk}`, `infra/{docker,kubernetes}`. 각 Python 패키지는 이름·한 줄 책임과 빈 껍데기(`domain`, `application/ports/{inbound,outbound}`, `application/usecases`, `adapters/{inbound,outbound}` — [../docs/architecture.md](../docs/architecture.md) 3.1)만 가집니다. 루트에 Python 워크스페이스와 Node 워크스페이스 설정 |
| 범위 밖 | 패키지 안의 구현. 서로를 import 하는 코드. `infra/kubernetes` 는 디렉터리와 README 한 줄만 |
| 완료 판정 | 의존성 설치 명령 두 개(Python, Node)가 깨끗한 checkout 에서 성공. 트리가 [../docs/architecture.md](../docs/architecture.md) 2절의 `패키지 자리` 열과 일치. 각 패키지 README 의 책임 문장이 2절의 `책임` 열과 같음 |
| 걸리는 규칙 | DP-5 Modular Monolith. 패키지 경계로만 표현합니다 |
| 게이트 | 닫힘 (2026-09-08). **Q1 → uv**, **Q2 → pnpm workspace 단독**(turborepo 없음). 기록은 [0001](0001-phase-0-foundation.md) Open Questions 1·2 |

### P0-2 `apps/api` 최소 기동

| 항목 | 내용 |
| --- | --- |
| 범위 | FastAPI 앱. `GET /healthz` 하나. 설정은 환경변수로만 읽고 기본값으로 뜹니다. OpenTelemetry SDK 초기화(exporter 없이도 기동). 테스트 1건 |
| 범위 밖 | DB 연결, 인증, 도메인 API. `/healthz` 는 DB 를 보지 않습니다 — DB 가 없어도 프로세스가 살아 있음을 답하는 것이 목적입니다 |
| 완료 판정 | 로컬에서 서버가 뜨고 `GET /healthz` 가 200. `pytest` 1건 통과. 부팅 경로에 외부 네트워크 호출 0건(DP-4) |
| 걸리는 규칙 | DP-1 API-first: `/healthz` 응답 스키마를 먼저 고정. DP-4 |

### P0-3 `packages/sdk` 와 `apps/web` 최소 기동

| 항목 | 내용 |
| --- | --- |
| 범위 | `packages/sdk` 에 API 클라이언트의 최소 형태(`healthz()` 하나). `apps/web` 은 Next.js 페이지 하나가 sdk 를 통해 `/healthz` 를 호출해 결과를 표시 |
| 범위 밖 | 화면 디자인, 상태 관리, 다른 페이지. web 이 api 의 코드나 `packages/*` 를 직접 import 하는 것(AR-1) |
| 완료 판정 | `build` 성공. 페이지가 api 의 healthz 값을 표시. `apps/web` 의 import 그래프에 `packages/sdk` 외의 `packages/*` 가 없음 |
| 걸리는 규칙 | **AR-1** web 은 HTTP 계약과 sdk 만 압니다 |
| 게이트 | 닫힘 (2026-09-09). **Q5 → 타입은 생성, 호출은 수기** (spec D-2, [../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) 2.4) |

### P0-3b UI 기반: Tailwind + shadcn/ui + 앱 셸

| 항목 | 내용 |
| --- | --- |
| 범위 | [../DESIGN.md](../DESIGN.md) 를 코드로: Tailwind CSS v4, `shadcn init`(new-york · neutral · CSS 변수), 4절의 초기 세트 `add`, `components/ui/` 커밋. 앱 셸(`components/AppShell.tsx` — 사이드바 5항목 · 헤더 · 콘텐츠, `lg` 미만은 `sheet`), `next-themes` 토글, Geist 폰트. 도메인 컴포넌트 `RunStatusBadge`(6절 표 소유) + 테스트. P0-3 의 healthz 페이지를 `card`·`badge` 로 다시 표현하고 오류 상태(7절) |
| 범위 밖 | 실제 화면(Chat·Run 목록·상세 = MVP-2), `form`(P1-1), 브랜드 색, 차트·모션 라이브러리, a11y 자동 판정(MVP-2 에서 켬) |
| 완료 판정 | `pnpm -F web run build`·`typecheck`·`lint`·`test:unit` 0. `pnpm exec depcruise apps/web --config .dependency-cruiser.cjs` 0. `RunStatusBadge` 가 7개 상태를 6절 표대로 렌더하는 테스트. `app/`·`components/`(ui 제외)에 `@radix-ui` 직접 import 0건, 임의 색 클래스(`bg-[`, `text-[#`, `-slate-`, `-gray-` 등) 0건 — grep 으로 확인. 보호 파일(`tsconfig.json`, `eslint.config.js`) 무수정 |
| 걸리는 규칙 | AR-1. DESIGN.md D-1 ~ D-7. `tailwind.config.*`·`postcss.config.*` 는 가드 경고 파일(만들 수 있음) |
| 근거 | spec 0001 개정 6, D-14. PROVENANCE 7.1 |

### P0-4 `apps/worker` 최소 기동

| 항목 | 내용 |
| --- | --- |
| 범위 | Redis 에 연결해 큐를 기다리는 프로세스. 작업 정의 없음. 종료 신호를 받으면 깨끗이 내려갑니다 |
| 범위 밖 | 실제 작업 처리. Run 실행(Phase 1) |
| 완료 판정 | Redis 가 있으면 "ready" 로그 후 대기, 없으면 재시도 후 명확한 오류로 종료. SIGTERM 에 5초 내 종료 |
| 걸리는 규칙 | AR-7 준비: worker 는 Data Plane 입니다. Control Plane(api)이 worker 를 직접 호출하는 경로를 만들지 않고 큐로만 선언합니다 |

### P0-5 Docker Compose 로 전부 기동

| 항목 | 내용 |
| --- | --- |
| 범위 | `infra/docker/compose.yaml`: PostgreSQL, Redis, migrate(일회성), api, web, worker. 이미지 빌드 포함. `.dockerignore`, `.env.example`. `compose.offline.yaml`(internal 네트워크 + 판정용 `probe` 서비스). **루트 `README.md`** — 기동 명령과 verify 명령 한 줄씩(R-1 의 발견 경로) |
| 범위 밖 | Local LLM, Vector DB 서비스(MVP-3). Kubernetes 매니페스트. 프로덕션 설정 |
| 완료 판정 | README 의 명령으로 기동 후 `GET /healthz` 200, web 200. 이미지 빌드 후 `docker compose -f compose.yaml -f compose.offline.yaml run probe` 가 exit 0(판정은 호스트 curl 이 아니라 네트워크 안의 probe). `.dockerignore` 가 `.env*` 를 제외하고 이미지 layer 에 `.env` 없음. `AETHER_VERSION` 빌드 인자는 `git describe --tags --always` 로 채워져 `/healthz` 의 `version` 에 커밋이 보임(릴리스 정의는 Month 6 의 intent — 그때까지 버전 = 커밋) |
| 걸리는 규칙 | **DP-4** Offline-capable 의 첫 근거. Trust: 비밀값을 커밋하지 않습니다 |

### P0-6 AR-* 를 기계 판정으로

| 항목 | 내용 |
| --- | --- |
| 범위 | `.importlinter`(Python): AR-2(packages 는 apps 를 모름), AR-3(runtime → mcp/context 단방향), AR-4(policy 는 runtime/mcp/context 를 부르지 않음), AR-5(LLM SDK import 는 runtime 의 model gateway 어댑터에서만), **AR-8(패키지 안은 안쪽으로만), AR-9(domain·application 은 프레임워크·I/O 없음), AR-11(inbound ↔ outbound 어댑터 상호 금지), AR-12(어댑터는 포트로만 application 을 만남)**. `.dependency-cruiser.cjs`(TS): AR-1. 각 규칙에 대해 **일부러 위반한 예시가 실패하는 것**을 테스트로 남깁니다. 파일 자체는 plan 의 H-1 에서 사람이 만듭니다(spec C-1) |
| 범위 밖 | AR-6(외부 접근은 MCP 경유)·AR-7 — 대상 코드가 없어 지금은 규칙만 등록하고 검사는 Phase 2 에서 걸립니다 |
| 완료 판정 | `lint-imports` 와 `depcruise` 가 exit 0. 위반 예시를 넣으면 exit 0 이 아님. 두 설정 파일이 하네스 보호 목록에 잡힘(`guard-evaluation-tampering.sh --list`) |
| 걸리는 규칙 | 하네스 EL-2 → EL-6 승격. 이 파일들은 이후 보호 파일입니다 |
| 게이트 | 닫힘 (2026-09-09). **Q3 → 한 번에** (spec D-1, [../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) 2.11) |

### P0-7 `harness.config` 제품 단계 활성화와 CI

| 항목 | 내용 |
| --- | --- |
| 범위 | `harness.config` 의 "Phase 0 이후" 블록을 spec 2.11 의 단계 표로 교체(제품 단계 10개, 명시 필터, 작은따옴표). `HARNESS_THRESHOLD` 를 90 → 80 (AD-2 시작값). `HARNESS_SELF_CHECK_LINK_DIRS` 에 `specs`. CI 에 uv·pnpm 설치와 비밀값 스캔 job. 로컬 verify 전체 시간을 실측해 기록(R-11, 예산 10분). **AD-2 진입 직후 improvement candidate 1건 더**: P0-4 에서 자연어 TDD 지시가 무시된 관측(근거: 구현 세션 보고서의 작업 순서) → 그 id 로 REP-9(기능 단위 test-first)를 평가 세트에 제안. **그리고** `PROVENANCE.md` 이력에 그림자 로그로 쌓인 관측 전부(가드 `install` 오탐, cp949 ×3, Node LTS, shadcn v4 프리셋, depcruise 상대 경로, `uv sync` 의미, eslint `projectService`·`.mjs`)를 candidate 로 일괄 전환. **평가 기준선**: REP-3·5·7("지금 가능")을 새 세션으로 1회씩 실행해 `evaluation/runs/` 첫 기록과 `.harness/baseline-eval.json`. H-2b 에 Dependabot 설정(`.github/dependabot.yml` — uv·pnpm·actions, 보호 경로) |
| 범위 밖 | 단계를 열 개 넘게 늘리기. `required` 를 내려서 통과시키기. smoke/e2e/load 는 Phase 1 이후 |
| 완료 판정 | `verify.sh` 가 self-check 단계와 제품 단계를 함께 집계해 pass. `.github/workflows/harness.yml` 이 녹색. 임계값 변경의 근거가 `improvement-log/` 에 1건 |
| 걸리는 규칙 | **보호 파일 변경.** [../harness/rules/harness-change-control.rule.md](../harness/rules/harness-change-control.rule.md) 를 따르고 한 번에 하나만 바꿉니다. EI-2: 임계값은 사람이 소유 — 변경은 제안하고 사람이 커밋합니다 |

### P0-8 데이터 모델 v1

| 항목 | 내용 |
| --- | --- |
| 범위 | 스키마 `control` / `data` 와 역할 `aether_control` / `aether_data` 분리. 테이블: `control.agents`, `control.agent_versions`(불변 트리거), `control.api_keys`, `control.runs`(선언), `data.run_executions`(실행 상태). 스키마·테이블·GRANT 는 Alembic 마이그레이션(`apps/api/migrations/`)이, 역할은 초기화 스크립트가 소유. `docs/data-model.md` 신설. 열과 제약은 [../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) 2.8 |
| 범위 밖 | Task, Observation, Memory, Workflow 테이블(각 Phase 에서). API 노출(P1-1) |
| 완료 판정 | 초기화 스크립트 없는 빈 DB(testcontainers)에서 마이그레이션 up/down 왕복. **UPDATE 권한이 있는 역할로** `agent_versions` UPDATE/DELETE 를 시도해 트리거가 거부. `aether_control` 로 `data.*` 접근 시 permission denied. `docs/data-model.md` 가 [../docs/README.md](../docs/README.md) 의 "아직 없는 문서" 에서 빠짐 |
| 걸리는 규칙 | 용어를 새로 만들지 않습니다. `Agent` 와 `Run` 을 한 테이블에 넣지 않습니다 |

### P0-9 🔒 인증 기준선

| 항목 | 내용 |
| --- | --- |
| 범위 | API 에 인증 한 가지를 넣습니다. 범위(API 키 / 세션 / OIDC)는 **Q4** 의 답이 정합니다. 미인증 요청이 보호 경로에서 401 |
| 범위 밖 | 권한(Permission), 조직·사용자 모델, SSO. Trust Layer 는 Phase 8 |
| 완료 판정 | 보호 경로가 인증 없이 401, 있으면 200. `/healthz` 는 인증 없이 200. 비밀값이 코드·로그·커밋에 없음 |
| 걸리는 규칙 | **DP-6, AGENTS.md Trust.** 에이전트는 설계와 테스트 목록을 제안하고 구현은 사람 검토를 거칩니다 |
| 게이트 | 닫힘 (2026-09-09). **Q4 → API 키** (spec D-3, [../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) 2.9). 🔒 는 그대로 — 구현은 사람 검토 |

---

## Phase 1 — Agent Runtime

2026-09-12 plan 0002 리뷰로 P1-2 → **P1-2a·P1-2b**, P1-5 → **P1-5a·P1-5b** 로 분할했습니다(범위의 합은 불변, 반복 예산 8회 안에 끝내기 위해). 순서는 plan 이 소유합니다.

Intent: [0002](0002-phase-1-agent-runtime.md) (승인됨 2026-09-12). Spec: [../specs/0002-phase-1-agent-runtime.md](../specs/0002-phase-1-agent-runtime.md) (승인됨 2026-09-12 — 결정 D-1 ~ D-19 가 아홉 단위의 공통 결정). 기간: Week 3~5.

**Phase 완료 판정** — `POST /agents` 로 만든 Agent 를 `POST /agents/{id}/run` 으로 실행하면 worker 가 Model → Tool → Observation → Model 루프를 돌아 `GET /runs/{id}` 가 최종 상태를 답하고, 이벤트가 스트리밍되며, 취소·타임아웃·재시도가 상태에 반영되고, 모든 과정이 트레이스로 남습니다. 인터넷 없이 됩니다.

| 번호 | 단위 | 의존 | 게이트 | 상태 |
| --- | --- | --- | --- | --- |
| P1-1 | Agent Registry API | P0-8, P0-9, P1-2b | — | 대기 |
| P1-2a | 테스트 도구 · 마이그레이션 0002 · 의존성 | P0-8 | — | 완료 |
| P1-2b | Run 상태 기계 · lease · `RunStateStore` · `AgentDefinition` (`packages/runtime`) | P1-2a | — | 완료 |
| P1-3 | Model gateway 와 첫 어댑터 | P0-1 | Q6 (닫힘 — spec 0002 D-1) | 완료 |
| P1-4 | Planner/Executor 루프 (도구는 프로세스 내부) | P1-2b, P1-3 | — | 대기 |
| P1-5a | worker 실행 경로 (`ExecuteRun` 호출 · heartbeat · Redis/DB 어댑터) | P1-4, P0-4 | — | 대기 |
| P1-5b | Run API (`run` / `runs/{id}` / `cancel`) · 투영 · e2e | P1-1, P1-5a | — | 대기 |
| P1-6 | Streaming | P1-5b | — | 대기 |
| P1-7 | Retry / Timeout / Error Handling | P1-5b | — | 대기 |
| P1-8 | Trace | P1-5b | — | 대기 |
| P1-9 | smoke 단계와 성능 기준값 고정 | P1-6, P1-8 | — | 대기 |

### P1-1 Agent Registry API

| 항목 | 내용 |
| --- | --- |
| 범위 | `POST /agents`, `GET /agents`, `GET /agents/{id}`. 생성 시 `Agent Version` 1이 함께 생김. 수정은 새 Version 을 만들고 이전 Version 은 불변 |
| 범위 밖 | 실행. 도구 바인딩(P2-6). 삭제(soft/hard 는 Control Plane 정책이 정해진 뒤) |
| 완료 판정 | 계약(OpenAPI)이 먼저 커밋되고 구현이 그것을 만족. `apps/api` 가 `packages/runtime` 의 `domain` 만 import 하고 `application`·`adapters` 는 import 하지 않음(spec 0002 D-13, `api-arch` 통과 — 2026-09-12 [편집]). 테스트: 생성 → 조회 → 수정 후 Version 2건 |
| 걸리는 규칙 | DP-1, AR-2. `Agent` 와 `Agent Version` 과 `Run` 을 혼용하지 않습니다 |
| 열리는 것 | 평가 세트 REP-1, REP-5 가 실행 가능해집니다 |

### P1-2a 테스트 도구, 마이그레이션 0002, 의존성

| 항목 | 내용 |
| --- | --- |
| 범위 | 루트 `pyproject.toml` 의 pytest·mypy 설정(spec 0002 D-18 개정 1: `pythonpath`, `explicit_package_bases` + `mypy_path`, `pytest-socket` 플래그), 루트 `conftest.py`, `tests/support/{pg,waiting}.py`, 기존 테스트의 네임스페이스 import 전환과 `sleep` 제거(프로덕션 무변경), `tests/arch/test_no_sleep_in_tests.py`(`ast`), 마이그레이션 0002(spec 2.10 전부), `packages/runtime` 의존성(pydantic·psycopg·redis), `docs/data-model.md`(주 세션) |
| 범위 밖 | 도메인 코드. 인증 어댑터 시그니처 변경(🔒) |
| 완료 판정 | `verify.sh` pass(`api-unit` 이 loopback 외 소켓 차단 상태로), `uv run mypy` 0, 마이그레이션 왕복과 새 열·권한 테스트, `test_no_sleep_in_tests.py` 0건, `apps/api/src` 무변경 |
| 걸리는 규칙 | spec 0002 R-6·R-11·D-18, spec 0001 R-7(역할 권한 불변) |

### P1-2b Run 상태 기계, lease, `RunStateStore`, `AgentDefinition`

| 항목 | 내용 |
| --- | --- |
| 범위 | `packages/runtime` 에 `Run` 의 상태와 전이: `queued → running → (waiting) → succeeded / failed / cancelled / timed_out`. `State` 는 재시작 후 이어붙일 수 있게 영속(`data.run_states`). `Task` 모델. 실행 권한 lease(spec 0002 D-10). `AgentDefinition`(2.3)과 `BUILTIN_TOOL_NAMES`. `RunStateStore` 포트와 fake·PostgreSQL 구현의 계약 테스트. LLM 없이 순수 도메인 |
| 범위 밖 | 모델 호출, 도구 호출, API, 루프. 이 단위는 테스트만으로 완결됩니다 |
| 완료 판정 | 허용되지 않은 전이가 예외를 내는 테스트. lease 가 있으면 두 번째 실행자가 물러나는 테스트(R-15). 새 store 인스턴스가 같은 `State` 를 load 하는 테스트 — "프로세스를 죽였다 살려도 `running` Run 이 같은 `State` 에서 재개" 의 유스케이스 절반은 P1-4 의 `test_resume.py` 가 완결합니다 |
| 걸리는 규칙 | [../docs/domain.md](../docs/domain.md) 1절: `State` 와 `Memory` 를 섞지 않습니다. AR-9 |

### P1-3 Model gateway 와 첫 어댑터

| 항목 | 내용 |
| --- | --- |
| 범위 | `packages/runtime` 안의 model gateway: 하나의 인터페이스(`complete`, `stream`, `embed`)와 어댑터 등록. 어댑터 두 개 — 테스트용 fake, OpenAI-호환 HTTP(로컬 LLM 서버가 이 형식을 씀). 모델 선택은 설정으로 |
| 범위 밖 | Model Registry(Phase 6), 벤더별 SDK 다수, 프롬프트 캐싱·비용 집계 |
| 완료 판정 | 저장소 전체에서 LLM SDK/HTTP 호출이 이 모듈 밖에 없음(P0-6 의 AR-5 규칙 통과). fake 어댑터로 전체 테스트가 네트워크 없이 통과 |
| 걸리는 규칙 | **AR-5, DP-3.** Model-agnostic 이 여기서 성립합니다 |
| 게이트 | **Q6** (신규) 로컬 LLM 서버의 기본 후보. 후보 목록만 여기 두고 채택은 spec 에서 — OpenAI-호환 API 를 내는 것이면 어댑터는 같습니다. **모델은 결정됨(2026-09-12, showjihyun): 로컬 LLM 경로의 기본 테스트 모델은 Qwen3.8 27B 양자화.** 단위 테스트·CI 는 fake 어댑터 그대로. 정확한 모델 태그·양자화 형식·서버는 spec 0002 |

### P1-4 Planner/Executor 루프

| 항목 | 내용 |
| --- | --- |
| 범위 | Model → (Tool 호출 결정) → Tool → `Observation` → Model → Result. `Task` 생성. 도구 인터페이스는 이 단위에서 프로세스 내부 함수(예: 시계, 계산기) 두 개 — MCP 는 Phase 2 |
| 범위 밖 | MCP, Context Compiler(모델 입력은 System Context + 대화만), Memory |
| 완료 판정 | fake 어댑터로 "도구를 부르는 시나리오" 와 "부르지 않는 시나리오" 가 결정적으로 통과. `Observation` 이 모델에 들어갈 때 신뢰 경계 밖 데이터로 표시됨 |
| 걸리는 규칙 | `Observation` 은 데이터이지 지시가 아닙니다 |

### P1-5a worker 실행 경로

| 항목 | 내용 |
| --- | --- |
| 범위 | worker 가 `aether:runs:requested` 를 집어(자기 PEL 먼저, `XAUTOCLAIM`, `count=1`) runtime 의 `ExecuteRun` 을 부르고 ack. runtime 의 Redis `EventSink`(같은 `seq` 재발행 흡수)·`StatusNotifier`, PostgreSQL `RunDeclarationReader`. heartbeat healthcheck(spec 2.14). compose 의 worker 설정(`AETHER_DATABASE_URL` = `aether_data`) |
| 범위 밖 | HTTP 경로, 투영, e2e(P1-5b) |
| 완료 판정 | fake `ExecuteRun` 으로 ack/미ack 규칙, `integration` 으로 PEL·`XAUTOCLAIM`·heartbeat TTL·재-XADD 흡수. compose 에서 `worker` 가 healthy |
| 걸리는 규칙 | **AR-7**(worker 는 api 를 모름), AR-12 |

### P1-5b Run API, 투영, e2e

| 항목 | 내용 |
| --- | --- |
| 범위 | `POST /agents/{id}/run` → `control.runs` 에 선언(커밋 뒤 통지) → `202`. `GET /runs/{id}`(투영만 읽음), `POST /runs/{id}/cancel`(`cancel_requested_at`). api 안의 `aether:runs:status` 소비자가 `seq` 로 멱등 투영. sdk 함수 셋. `docs/api.md` 의 runs 절과 스트림 계약 표(주 세션) |
| 범위 밖 | 스트리밍(P1-6), 재시도·타임아웃(P1-7) |
| 완료 판정 | 통합 e2e 에서 Run 이 `succeeded` 까지 감(R-2). `cancel` 후 `cancelled`. api 가 worker 의 코드를 import 하지 않고 `aether_runtime.domain` 만 봄(AR-7 확장, `api-arch`). compose 에서 손으로 Run 하나 `succeeded` |
| 걸리는 규칙 | **AR-7.** Control Plane 은 선언만 합니다. DP-1 |
| 열리는 것 | REP-2 가 실행 가능해집니다 |

### P1-6 Streaming

| 항목 | 내용 |
| --- | --- |
| 범위 | Run 이벤트(상태 전이, 모델 토큰, 도구 호출·결과)를 SSE 로. 이벤트 스키마 고정 |
| 범위 밖 | WebSocket, 재접속 시 이어보기(이벤트 id 만 남겨 둠) |
| 완료 판정 | 스트림 응답에서 이벤트 순서가 상태 전이 순서와 같음. 클라이언트가 끊겨도 Run 은 계속됨 |
| 걸리는 규칙 | DP-1: 이벤트 스키마가 계약입니다. 바꾸면 파괴적 변경 판정 |
| 열리는 것 | REP-4 |

### P1-7 Retry / Timeout / Error Handling

| 항목 | 내용 |
| --- | --- |
| 범위 | Run 단위 타임아웃 → `timed_out`. 모델 호출·도구 호출의 재시도 정책(횟수·백오프)을 `Agent Version` 에 저장. 오류를 분류해 `failed` 의 사유로 남김 |
| 범위 밖 | 무한 재시도, 사람 개입(HITL 은 Phase 4) |
| 완료 판정 | 타임아웃 테스트가 실제 시간 대신 주입된 시계로 결정적으로 통과. 재시도 횟수를 넘긴 Run 의 사유가 조회됨 |

### P1-8 Trace

| 항목 | 내용 |
| --- | --- |
| 범위 | OpenTelemetry span: Run → Task → 모델 호출 / 도구 호출. compose 에 collector 하나(로컬). `GET /runs/{id}` 응답에 trace id |
| 범위 밖 | 대시보드, 샘플링 정책, 비용 집계 |
| 완료 판정 | 한 Run 의 span 트리가 collector 에서 확인됨. 부팅 경로에 외부 exporter 호출 0건 |
| 걸리는 규칙 | DP-4 |

### P1-9 smoke 단계와 성능 기준값 고정

| 항목 | 내용 |
| --- | --- |
| 범위 | `scripts/smoke.sh`: compose up → agent 생성 → run → succeeded 확인. `harness.config` 의 `smoke` 단계 활성화. Run 생성 응답 P95 를 측정해 [../evaluation/README.md](../evaluation/README.md) 의 `{{성능_기준}}` 값을 **사람이** 고정 |
| 범위 밖 | 부하 테스트(`load` 단계는 이후) |
| 완료 판정 | `verify.sh` 에 `smoke` 가 집계됨. 기준값이 evaluation/README 에 적힘 |
| 걸리는 규칙 | 보호 파일 변경. EI-2: 기준값은 에이전트가 정하지 않습니다 |
| 열리는 것 | REP-8. 성숙도 AD-2 |

---

## Phase 2 — Enterprise MCP Gateway

Intent: 0003 (미발급). 기간: Week 6~8.

**Phase 완료 판정** — Agent 의 모든 도구 호출이 `packages/mcp` 의 Gateway 한 곳을 지나고, Gateway 가 연결된 MCP Server 에서 Tool 을 발견하며, 호출마다 권한 판정과 감사 기록이 남습니다. Filesystem·HTTP·PostgreSQL MCP Server 가 인터넷 없이 붙습니다.

| 번호 | 단위 | 의존 | 게이트 | 상태 |
| --- | --- | --- | --- | --- |
| P2-1 | MCP Client 와 Tool Discovery | P0-1 | — | 대기 |
| P2-2 | MCP Gateway (단일 통로, 연결 관리, 감사 기록) | P2-1 | — | 대기 |
| P2-3 | Runtime 이 Gateway 로만 도구를 부름 | P2-2, P1-4 | — | 대기 |
| P2-4 | 🔒 Permission 판정 지점 | P2-2 | — | 대기 |
| P2-5 | 초기 Integration: Filesystem, HTTP, PostgreSQL | P2-3 | — | 대기 |
| P2-6 | Agent 에 MCP Server 바인딩 | P2-3, P1-1 | — | 대기 |

### P2-1 MCP Client 와 Tool Discovery

| 항목 | 내용 |
| --- | --- |
| 범위 | `packages/mcp`: MCP Server 에 붙는 클라이언트(stdio, HTTP). `Tool Discovery` 로 `Tool` 목록과 스키마를 얻음. 테스트용 MCP Server 하나를 저장소 안에 둠 |
| 범위 밖 | Gateway, 권한, 실제 외부 시스템 |
| 완료 판정 | 테스트 서버에 붙어 도구 2개 이상을 스키마와 함께 발견하는 테스트. 네트워크 없이 통과 |

### P2-2 MCP Gateway

| 항목 | 내용 |
| --- | --- |
| 범위 | 모든 도구 호출이 지나는 함수 하나. 연결 수명 관리(재연결, 종료). 호출마다 `Audit` 기록(누가·어느 Run·어느 Tool·언제·결과 크기). Firewall 이 들어올 자리(hook point)만 비워 둠 |
| 범위 밖 | MCP Firewall·DLP(Phase 10). Policy Engine(Phase 9) |
| 완료 판정 | Gateway 를 거치지 않는 MCP 호출 경로가 저장소에 없음(P0-6 에 AR-6 규칙 추가 → `arch-test` 통과). 감사 기록이 호출 수와 일치하는 테스트 |
| 걸리는 규칙 | **AR-6, DP-2.** 우회 경로를 만들면 Firewall 이 관측하지 못합니다 |

### P2-3 Runtime 이 Gateway 로만 도구를 부름

| 항목 | 내용 |
| --- | --- |
| 범위 | P1-4 의 프로세스 내부 도구를 MCP Server 로 옮기거나 제거. Executor 의 도구 호출이 전부 Gateway 경유 |
| 범위 밖 | 새 도구 추가 |
| 완료 판정 | P1-4 의 시나리오 테스트가 Gateway 경유로 그대로 통과. Executor 에 Gateway 외의 도구 호출 코드가 없음 |
| 걸리는 규칙 | AR-3 runtime → mcp 단방향 |
| 열리는 것 | REP-6 |

### P2-4 🔒 Permission 판정 지점

| 항목 | 내용 |
| --- | --- |
| 범위 | `packages/policy` 에 판정 함수 하나: (주체=Agent Version, 자원=Tool) → allow/deny. Gateway 가 호출 전에 이것을 묻습니다. 정책 저장은 단순 표(Agent × Tool) |
| 범위 밖 | Policy Engine 의 실행 구조(Phase 9), 조직·역할, 승인 흐름 |
| 완료 판정 | deny 된 Tool 호출이 Gateway 에서 막히고 감사에 남음. `packages/policy` 가 `runtime`·`mcp`·`context` 를 import 하지 않음(AR-4) |
| 걸리는 규칙 | **AR-4, DP-6, Trust.** 에이전트는 인터페이스와 테스트를 제안하고 사람 검토를 거칩니다 |

### P2-5 초기 Integration

| 항목 | 내용 |
| --- | --- |
| 범위 | Filesystem, HTTP, PostgreSQL MCP Server 를 compose 에 넣고 Gateway 에 등록. 셋 다 인터넷 없이 동작하는 것 |
| 범위 밖 | GitHub, Slack — 외부 네트워크가 필요하므로 MVP 오프라인 시나리오 밖입니다. 로드맵에는 있으니 Public Beta 전에 붙입니다 |
| 완료 판정 | 오프라인 compose 에서 Agent 가 Filesystem 도구로 파일을 읽어 Run 이 `succeeded` |
| 걸리는 규칙 | DP-4 |

### P2-6 Agent 에 MCP Server 바인딩

| 항목 | 내용 |
| --- | --- |
| 범위 | `Agent Version` 에 사용할 MCP Server 목록. API 로 붙이고 떼기(새 Version 생성). Run 시작 시 그 목록만 Gateway 에 연결 |
| 범위 밖 | Marketplace, Tool 검색 UI |
| 완료 판정 | 바인딩되지 않은 Tool 은 Discovery 에 나타나지 않음. 바인딩 변경이 새 Version 을 만듦 |

---

## Phase 3 — Context Compiler / RAG

Intent: 0004 (미발급). 기간: Week 9~12.

**Phase 완료 판정** — 모델 호출마다 `Context Compiler` 가 예산 안에서 System Context · Conversation · Knowledge · Memory · Tools 를 조립하고, Knowledge 는 로컬 Vector DB 에서 검색되며, Memory 는 Knowledge 와 다른 저장소에 검증 전 표시를 달고 있고, Run 마다 컨텍스트 토큰 수가 트레이스에 남습니다.

| 번호 | 단위 | 의존 | 게이트 | 상태 |
| --- | --- | --- | --- | --- |
| P3-1 | Context Compiler v1 (예산과 조립 규칙) | P1-4 | — | 대기 |
| P3-2 | Knowledge 적재: Connector → Indexer → Embedding → Vector DB | P1-3 | Q7 | 대기 |
| P3-3 | 검색 결과를 Context 에 | P3-1, P3-2 | — | 대기 |
| P3-4 | Memory v1 (Knowledge 와 분리) | P3-1, P1-5 | — | 대기 |
| P3-5 | KPI 계측: Task Success / Context Token | P3-3, P1-8 | — | 대기 |

### P3-1 Context Compiler v1

| 항목 | 내용 |
| --- | --- |
| 범위 | `packages/context`: 입력 소스(System Context, Conversation, Tools 스키마)와 토큰 예산을 받아 모델 입력을 결정적으로 조립. 넘치면 무엇을 빼는지 규칙이 코드에 있음. Executor 가 모델 호출 전에 이것을 부름 |
| 범위 밖 | Knowledge·Memory 소스(P3-3, P3-4), Ranking·Compression(v1.1) |
| 완료 판정 | 같은 입력에 같은 출력(결정성 테스트). 예산 초과 입력이 예산 안으로 잘리는 테스트. runtime → context 단방향(AR-3) |
| 걸리는 규칙 | `Context` 는 예산이 있는 자원입니다 |

### P3-2 Knowledge 적재

| 항목 | 내용 |
| --- | --- |
| 범위 | Connector(Filesystem 하나) → Indexer(청크) → Embedding(P1-3 gateway 의 `embed`) → 로컬 Vector DB. 적재 API 와 진행 상태 |
| 범위 밖 | 다른 Connector, 증분 갱신, 권한별 검색 |
| 완료 판정 | 오프라인 compose 에서 디렉터리 하나를 적재하고 벡터 검색 1건이 답함 |
| 걸리는 규칙 | AR-5: 임베딩도 gateway 를 지납니다. DP-4 |
| 게이트 | **Q7** (신규) 로컬 Vector DB. 새 서비스를 늘리지 않는 선택(PostgreSQL 확장)과 전용 서비스 사이의 결정. 채택은 spec 에서 |

### P3-3 검색 결과를 Context 에

| 항목 | 내용 |
| --- | --- |
| 범위 | Compiler 에 Knowledge 소스 추가. 검색 결과에 출처를 붙여 `Observation` 처럼 신뢰 경계 표시. Agent Version 에 Knowledge 집합 바인딩 |
| 범위 밖 | Reranker, 인용 UI |
| 완료 판정 | 적재된 문서의 사실을 묻는 Run 이 출처와 함께 답함(fake 모델로 결정적 테스트 + 로컬 LLM 으로 1회 실제 확인) |

### P3-4 Memory v1

| 항목 | 내용 |
| --- | --- |
| 범위 | `packages/memory`: Run 이 끝날 때 남기는 경험을 Agent 별로 저장. Knowledge 와 **다른 저장소**. 읽을 때 "검증 전" 표시가 붙어 Context 에 들어감 |
| 범위 밖 | 자동 승격, 요약, 망각 정책 |
| 완료 판정 | Memory 와 Knowledge 가 같은 테이블·같은 인덱스를 쓰지 않음. Memory 항목이 Context 에 들어갈 때 표시가 있음(테스트) |
| 걸리는 규칙 | [../docs/domain.md](../docs/domain.md) 3절: 섞이면 검증되지 않은 경험이 사실로 승격됩니다 |

### P3-5 KPI 계측

| 항목 | 내용 |
| --- | --- |
| 범위 | Run 마다 소스별 컨텍스트 토큰 수와 성공 여부를 span 속성으로. 집계 쿼리 하나 |
| 범위 밖 | 최적화 자체(v1.1). 대시보드 |
| 완료 판정 | 트레이스에서 Task Success / Context Token 을 계산할 수 있음 |
| 걸리는 규칙 | EI-3 의 제품판: 이 숫자를 단일 목표로 주지 않습니다 |

---

## Phase 4 — Workflow Engine

Intent: 0005 (미발급). 기간: Week 13~16.

**Phase 완료 판정** — START → AGENT → CONDITION 분기 → HUMAN 승인 → AGENT → END 인 Workflow 가 worker 에서 실행되고, 승인에서 멈췄다가 사람의 승인 API 호출로 재개되며, PARALLEL·LOOP·WAIT 노드가 동작합니다.

| 번호 | 단위 | 의존 | 게이트 | 상태 |
| --- | --- | --- | --- | --- |
| P4-1 | Workflow 모델과 영속 (START/END/AGENT/CONDITION) | P0-8 | — | 대기 |
| P4-2 | Workflow 실행기: 순차와 CONDITION | P4-1, P1-5 | — | 대기 |
| P4-3 | PARALLEL / LOOP / WAIT | P4-2 | — | 대기 |
| P4-4 | 🔒 HUMAN / APPROVAL (HITL) | P4-2 | — | 대기 |
| P4-5 | LLM / MCP / TOOL 노드 | P4-2, P2-3 | — | 대기 |

WEBHOOK, SCHEDULE 노드는 인바운드 네트워크와 스케줄러가 필요해 오프라인 MVP 시나리오 밖입니다. Public Beta 전에 붙입니다.

### P4-1 Workflow 모델과 영속

| 항목 | 내용 |
| --- | --- |
| 범위 | `packages/workflow`: 노드·간선 그래프, 검증(START 하나, END 도달 가능), Workflow Version(불변). 노드 종류는 넷 |
| 범위 밖 | 실행. UI(Phase 5) |
| 완료 판정 | 잘못된 그래프(END 없음, 고아 노드)가 검증에서 거부되는 테스트 |

### P4-2 Workflow 실행기

| 항목 | 내용 |
| --- | --- |
| 범위 | worker 가 Workflow Run 을 집어 노드를 순서대로 실행. AGENT 노드는 P1-5 의 Run 을 만들고 기다림. CONDITION 은 이전 노드 출력으로 분기. Workflow Run 의 `State` 영속 |
| 범위 밖 | 병렬, 루프, 사람 |
| 완료 판정 | 분기 양쪽을 타는 두 테스트. 프로세스 재시작 후 이어 실행되는 테스트 |
| 걸리는 규칙 | AR-3: workflow 가 runtime 을 쓰고 역방향은 없음 |

### P4-3 PARALLEL / LOOP / WAIT

| 항목 | 내용 |
| --- | --- |
| 범위 | 병렬 분기와 합류, 조건 루프(최대 횟수 필수), 시간 대기(주입된 시계) |
| 범위 밖 | 분산 실행 |
| 완료 판정 | 루프 상한을 넘기면 `failed` 가 되는 테스트. 병렬 분기 하나의 실패가 합류에서 관측되는 테스트 |

### P4-4 🔒 HUMAN / APPROVAL

| 항목 | 내용 |
| --- | --- |
| 범위 | Run 이 `waiting` 으로 멈추고, `Approval` 사건을 받는 API 로 재개. 누가 언제 승인했는지 기록 |
| 범위 밖 | 알림, 승인자 권한 모델(Trust Layer) |
| 완료 판정 | 승인 전 재개 시도가 거부됨. 승인 후 재개되어 END 도달. 승인 기록이 조회됨 |
| 걸리는 규칙 | **DP-6, Trust.** 승인은 보안에 닿습니다 — 사람 검토 |

### P4-5 LLM / MCP / TOOL 노드

| 항목 | 내용 |
| --- | --- |
| 범위 | Agent 를 거치지 않고 모델 한 번, Tool 한 번을 부르는 노드. 각각 gateway(AR-5)와 Gateway(AR-6)를 지남 |
| 범위 밖 | 노드별 재시도 정책의 세분화 |
| 완료 판정 | 세 노드가 각각 한 번씩 들어간 Workflow 가 END 도달. `arch-test` 통과 |

---

## MVP 통합 — Month 4

Intent: 0006 (미발급). Phase 1~4 가 끝난 뒤가 아니라 **Phase 1 이 끝나면 MVP-1·MVP-3 부터** 시작할 수 있습니다. 시나리오를 늦게 붙일수록 그 사이의 결정이 시나리오와 어긋납니다.

**Phase 완료 판정** — 로드맵 10장의 시나리오가 자동 테스트로 성립하고, 처음 보는 사람이 clone 부터 첫 Run 성공까지 10분 안에 도달한 측정 기록이 있습니다.

| 번호 | 단위 | 의존 | 게이트 | 상태 |
| --- | --- | --- | --- | --- |
| MVP-1 | CLI | P1-6, P0-3 | — | 대기 |
| MVP-2 | Basic UI: Chat, Run 목록, Run 상세(스트림·트레이스) | P1-6, P1-8, P0-3 | — | 대기 |
| MVP-3 | Local LLM 을 compose 에 | P1-3, P0-5 | Q6 | 대기 |
| MVP-4 | 오프라인 시나리오 e2e | MVP-3, P2-5, P3-3, P4-2 | — | 대기 |
| MVP-5 | Time to First Successful Agent 측정 | MVP-1, MVP-4 | — | 대기 |

### MVP-1 CLI

| 항목 | 내용 |
| --- | --- |
| 범위 | `aether` 명령: `up`(compose), `agent create/list`, `run <agent>`(스트림 출력), `runs get`. `packages/sdk` 만 씀 |
| 범위 밖 | 대화형 TUI, 플러그인 |
| 완료 판정 | CLI 만으로 P1-5 의 시나리오가 됨. CLI 가 api 코드를 import 하지 않음(AR-1 의 CLI 판) |

### MVP-2 Basic UI

| 항목 | 내용 |
| --- | --- |
| 범위 | 세 화면: Agent 와 대화(스트림), Run 목록, Run 상세(이벤트 타임라인 + trace id). 디자인은 최소 |
| 범위 밖 | Agent Builder(Phase 5), Workflow 편집, Admin, Analytics |
| 완료 판정 | 오프라인 compose 에서 세 화면이 실제 데이터로 뜸. `apps/web` 이 sdk 외 `packages/*` 를 import 하지 않음 |
| 걸리는 규칙 | AR-1 |
| 열리는 것 | 프런트엔드 팩 단계(e2e)를 켤 근거 |

### MVP-3 Local LLM 을 compose 에

| 항목 | 내용 |
| --- | --- |
| 범위 | 로컬 LLM 서버를 compose 서비스로. 모델 파일을 미리 받아 두는 경로(볼륨)와 없을 때의 명확한 안내. model gateway 기본값이 로컬 |
| 범위 밖 | 모델 선택 UI, GPU 스케줄링, Model Registry(Phase 6) |
| 완료 판정 | 네트워크를 끊은 compose 에서 Run 이 로컬 모델로 `succeeded`. 부팅 경로에 모델 다운로드가 없음(미리 받아 둔 것을 씀) |
| 걸리는 규칙 | DP-4. AR-5 |
| 게이트 | Q6 |

### MVP-4 오프라인 시나리오 e2e

| 항목 | 내용 |
| --- | --- |
| 범위 | 로드맵 10장 시나리오를 테스트 하나로: 네트워크 차단 → compose up → Knowledge 적재 → Agent 생성(Filesystem MCP 바인딩) → Workflow 실행 → 성공. `harness.config` 의 `e2e` 단계로 등록 |
| 범위 밖 | 성능, 다중 사용자 |
| 완료 판정 | 이 테스트가 CI 에서 통과. 통과 로그가 `.harness/logs/` 에 남음 |
| 걸리는 규칙 | 보호 파일 변경. EI-7 |
| 열리는 것 | held-out 세트 첫 실행 |

### MVP-5 Time to First Successful Agent 측정

| 항목 | 내용 |
| --- | --- |
| 범위 | Quickstart 문서 한 장. 저장소를 처음 보는 사람이 그 문서만 보고 clone → 첫 Run 성공까지 걸린 시간을 측정. 결과와 막힌 지점을 기록 |
| 범위 밖 | 측정 조건을 바꿔 숫자를 맞추기 |
| 완료 판정 | 측정 기록이 커밋됨. 10분을 넘겼다면 막힌 지점이 다음 단위로 등록됨 — 숫자를 조정하지 않습니다 |
| 걸리는 규칙 | EI-3 의 정신: 이 KPI 하나를 위해 다른 것을 훼손하지 않습니다 |

---

## 열린 질문 (게이트)

Q1~Q5 는 [0001](0001-phase-0-foundation.md) 의 것이며, 여기서 다시 답하지 않습니다. 이 문서가 새로 드러낸 것은 두 개입니다. 둘 다 해당 Phase 의 intent 를 발급할 때 그 intent 의 Open Questions 로 옮깁니다.

| # | 질문 | 어느 단위를 막는가 | 누가 답하는가 |
| --- | --- | --- | --- |
| Q6 | 로컬 LLM 서버 기본 후보. OpenAI-호환 API 를 내는 것이면 어댑터는 하나로 족합니다 | P1-3, MVP-3 | 사람, Phase 1 intent 발급 시 |
| Q7 | 로컬 Vector DB. 서비스를 늘리지 않는 선택(PostgreSQL 확장)인가 전용 서비스인가 | P3-2 | 사람, Phase 3 intent 발급 시 |

## 이 문서를 갱신하는 때

| 사건 | 무엇을 바꾸는가 |
| --- | --- |
| 단위를 시작·완료했다 | 그 Phase 표의 `상태`. 같은 커밋에서 |
| 단위가 한 세션에서 끝나지 않았다 | 쪼갭니다. 번호 뒤에 `a`, `b` 를 붙이고 의존을 다시 적습니다. 예산을 늘리지 않습니다 |
| Phase 의 intent 를 발급했다 | 그 Phase 머리의 `Intent:` 를 링크로 |
| 로드맵이 바뀌었다 | 원본을 고치고, 이 문서는 그것을 따라 고칩니다. 반대 방향은 없습니다 |

## 관련 문서

- [intent.md](intent.md) — 지금 활성인 intent
- [0001-phase-0-foundation.md](0001-phase-0-foundation.md) — Phase 0 의 intent 와 Q1~Q5
- [../docs/roadmap.md](../docs/roadmap.md) — Phase 표와 하네스 대응
- [../docs/architecture.md](../docs/architecture.md) — AR-*, DP-*
- [../docs/domain.md](../docs/domain.md) — 용어
- [../evaluation/tasks/representative.md](../evaluation/tasks/representative.md) — 각 단위가 열어 주는 REP task
- [../harness/rules/harness-change-control.rule.md](../harness/rules/harness-change-control.rule.md) — 보호 파일에 닿는 단위의 절차
