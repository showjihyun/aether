# DESIGN

이 문서는 `apps/web` 에 화면을 만들거나 고치기 전에 읽습니다. 목적은 하나입니다 — **디자인 결정을 최소화**합니다. 여기 적힌 것 외의 모든 시각적 결정은 **shadcn/ui 의 기본값**이 답이고, 기본값을 바꾸고 싶으면 이 문서를 먼저 고칩니다. 화면을 만드는 사람이나 에이전트가 색·간격·모양을 고르는 순간이 없어야 합니다.

근거와 출처는 [PROVENANCE.md](PROVENANCE.md) 7.1 절이, 아키텍처 규칙(AR-1: web 은 sdk 만 안다)은 [docs/architecture.md](docs/architecture.md) 가 소유합니다. 이 문서는 표현만 정합니다.

## 1. 스택

| 층 | 선택 | 왜 이것인가 |
| --- | --- | --- |
| 프레임워크 | Next.js App Router (`apps/web`) | spec 0001 2.5 |
| 스타일 | **Tailwind CSS v4** | shadcn/ui 의 전제. 유틸리티만 쓰고 CSS 파일을 손으로 쓰지 않습니다. PostCSS 설정은 `apps/web/package.json` 의 `postcss` 필드에 둡니다 — 별도 `.mjs` 설정 파일은 보호 파일 두 개(`tsconfig.json` 의 `include`, `eslint.config.js` 의 `projectService`)의 조합에서 lint 파싱 오류를 냅니다(P0-3b) |
| 컴포넌트 | **shadcn/ui** — style `new-york`, base color `neutral`, CSS variables 켬. **CLI 는 `shadcn@3.8.5` 로 고정**(`apps/web` devDependency) | 소스가 저장소에 복사되는 모델이라 의존성이 아니라 우리 코드가 됩니다. 기본값이 곧 디자인 시스템입니다. v4 CLI 는 init 을 프리셋 8종으로 바꿔 `new-york + neutral` 을 지정할 수 없고, 프리셋을 고르는 것은 그 자체가 새 시각적 결정이라 3.x 마지막 안정판에 고정했습니다(P0-3b). 올리려면 이 문서를 먼저 고칩니다 |
| 프리미티브 | Radix UI (shadcn 이 가져옴 — 3.8.5 는 단일 패키지 `radix-ui` 에서 import) | 접근성·키보드·포커스가 이미 되어 있습니다. 직접 import 하지 않습니다(3절) |
| 아이콘 | `lucide-react` 만 | shadcn 기본. 세트를 섞지 않습니다 |
| 폰트 | Geist Sans / Geist Mono — **`geist` npm 패키지** | 로컬 번들이라 오프라인(DP-4)에서도 뜹니다. `next/font/google` 은 빌드 시 네트워크에서 폰트를 받아 오프라인 빌드를 깨뜨리므로 쓰지 않습니다(P0-3b) |
| 테마 전환 | `next-themes`, `class` 전략 | 다크 모드는 선택이 아니라 기본 요구입니다(8절) |
| 캔버스 | **`@xyflow/react`** — 버전 `12.12.0` 고정. `dist/base.css` **만** import 하고 기본 테마 `dist/style.css` 는 쓰지 않습니다. 색·선폭은 `app/globals.css` 에서 `--xy-*` 를 2절 토큰으로 덮습니다. attribution 링크는 **그대로 둡니다**(끄지 않습니다) | Workflow 그래프를 그리는 유일한 자리(P5-5·P5-6). MIT, 설치 스크립트 없음, **런타임 네트워크 없음** — 오프라인(DP-4) 실측은 [docs/measurements/canvas-dependency-2026-10-23.md](docs/measurements/canvas-dependency-2026-10-23.md) 입니다. 색·선폭 28곳이 `var(--xy-X, var(--xy-X-default))` 꼴이라 토큰으로 전부 덮입니다. attribution 을 끄는 것은 한 줄이지만 상류가 유료 구독을 요청하므로, 돈을 쓰지 않고 라이선스 위험도 없는 쪽을 골랐습니다 — 에어갭에서 그 링크는 열리지 않을 뿐 네트워크를 타지 않습니다 |

여기 없는 라이브러리(차트, 모션, 다른 컴포넌트 킷)는 필요가 생긴 단위에서 이 문서를 고쳐 추가합니다. 먼저 넣고 나중에 적지 않습니다.

## 2. 토큰

shadcn 이 `app/globals.css` 에 만드는 CSS 변수(`--background`, `--foreground`, `--primary`, `--muted`, `--destructive`, `--border`, `--ring`, `--radius` …)가 **유일한** 색·모양 토큰입니다.

| 규칙 | 뜻 |
| --- | --- |
| **D-1 토큰만** | 색은 `bg-background`, `text-muted-foreground`, `border-border` 처럼 토큰 클래스로만. 임의 값(`bg-[#1f2937]`, `text-[13px]`)과 Tailwind 팔레트 직접 참조(`bg-slate-800`)를 쓰지 않습니다. 팔레트가 필요한 곳은 토큰이 부족한 곳이고, 그때는 토큰을 더합니다 |
| **D-2 간격·크기는 Tailwind 스케일** | `p-4`, `gap-2`, `text-sm`. 스케일 밖의 수를 만들지 않습니다 |
| **D-3 모양은 `--radius` 하나** | 카드·입력·버튼의 라운드는 전부 여기서 파생됩니다. 개별 컴포넌트에서 라운드를 바꾸지 않습니다 |

기본값을 그대로 둡니다 — accent 색도, radius 도. aether 의 브랜드 색은 **결정하지 않았고**, 결정할 때까지 shadcn `neutral` 의 `primary` 가 그 자리입니다. 이것은 미결이 아니라 결정입니다.

## 3. 컴포넌트 정책

```text
apps/web/
  components/ui/        shadcn 생성물. `pnpm -F web exec shadcn add <name>` (고정된 3.8.5) 으로만 추가. 커밋합니다
  components/           aether 도메인 컴포넌트 — ui/ 를 조합한 것 (RunStatusBadge, AppShell …)
  app/                  페이지. components/ 를 조합만 합니다. 페이지 안에 스타일 결정을 두지 않습니다
```

| 규칙 | 뜻 |
| --- | --- |
| **D-4 새 UI 는 shadcn 조합** | 필요한 것이 `components/ui/` 에 없으면 먼저 `pnpm -F web exec shadcn add <name>`(고정 버전 — `dlx shadcn@latest` 를 쓰지 않습니다). shadcn 에도 없으면 Radix 프리미티브 위에 같은 규약(`cva`, `cn`, 토큰)으로 `components/ui/` 에 만들고 이 문서 4절에 적습니다 |
| **D-5 Radix·Tailwind 팔레트를 페이지에서 직접 쓰지 않음** | `app/` 과 `components/` 는 `@/components/ui` 만 import. `radix-ui` / `@radix-ui/*` 직접 import 는 `components/ui/` 안에서만 |
| **D-6 생성물은 우리 코드** | `components/ui/` 를 고치는 것은 허용(shadcn 의 모델)이되, 고친 이유를 파일 머리 주석에 남깁니다. 고친 파일은 `shadcn add` 로 다시 덮지 않습니다 |
| **D-7 조합은 도메인 컴포넌트에** | 같은 조합이 두 번 나오면 `components/` 로 올립니다. 페이지는 얇게 |

## 4. 초기 세트

P0-3b 가 설치했습니다(17개). MVP-2(Chat, Run 목록, Run 상세)가 필요로 하는 것과 그 전에 필요한 것만입니다. 더 필요해지면 그 단위에서 `shadcn add` 하고 이 표에 한 줄 더합니다. `tooltip` 은 `app/layout.tsx` 의 `TooltipProvider` 가 전제입니다(P0-3b 가 감쌈).

| 컴포넌트 | 어디에 쓰는가 |
| --- | --- |
| `button`, `input`, `textarea`, `label` | 폼과 Chat 입력 |
| `card` | healthz, Run 상세의 구획 |
| `badge` | Run 상태(6절), 버전 |
| `alert` | 오류·경고 상태(7절) |
| `skeleton` | 로딩 상태(7절) |
| `separator`, `scroll-area` | 레이아웃·긴 목록 |
| `table` | Run 목록 |
| `tabs` | Run 상세(이벤트 / 트레이스 / 입력) |
| `dialog`, `sheet` | 확인·상세 패널 |
| `dropdown-menu`, `tooltip` | 행 동작·보조 설명 |
| `sonner` | 토스트 |

`form`(react-hook-form + zod)은 Agent 생성 폼이 생기는 Phase 1 P1-1 의 UI 에서 추가합니다.

## 5. 앱 셸과 화면

화면은 전부 하나의 **앱 셸** 안에 있습니다. 셸은 P0-3b 가 만들고 이후 화면은 그 안에 놓입니다.

```text
┌──────────┬────────────────────────────────────┐
│ Sidebar  │ Header (현재 위치, 테마 토글)          │
│ Agents   ├────────────────────────────────────┤
│ Runs     │ Content                            │
│ Knowledge│   max-w-6xl, p-6, 세로 스크롤        │
│ Workflows│                                    │
│ Settings │                                    │
└──────────┴────────────────────────────────────┘
```

사이드바 항목은 MVP 범위만입니다(Agents, Runs, Knowledge, Workflows, Settings). 로드맵의 나중 Phase(Marketplace, Passport …)를 미리 넣지 않습니다.

| 화면 | 단위 | 구성 |
| --- | --- | --- |
| `/` healthz | P0-3 → P0-3b 가 다시 표현 | `card` 안에 status·service·version, 상태는 `badge` |
| `/agents` 목록 | **MVP-2a** | `table` — 이름, 현재 Version, 수정 시각. **이름 칸이 대화(`/agents/{id}/chat`)로 가는 링크**입니다(목적지는 **MVP-2e** 가 만들었습니다) |
| `/runs` 목록 | **MVP-2a** | `table` — 상태 `badge`, Agent(**짧은 ID** — `RunSummary` 에 이름이 없습니다. 이름을 보이려면 N+1 호출이나 목록 응답 변경이 필요하고 둘 다 이 단위 밖입니다), 시작(`started_at`, 없으면 `—`)·소요. 행 클릭 → 상세는 **MVP-2b** 가 목적지를 만들 때 겁니다 |
| `/runs/{id}` 상세 | **MVP-2b** | `card` 머리(상태·trace id·요청자·시각), `tabs`(**이벤트 타임라인 / 트레이스** — 둘입니다). **"입력" 탭은 두지 않습니다**: 입력 본문은 어떤 API 응답에도 없습니다(`GET /runs/{id}` 는 `control.runs` 투영 열만 읽습니다, spec 0001 D-11). 내용이 "API 가 돌려주지 않습니다" 한 줄인 탭은 9절이 금지하는 자리표시입니다. 보이려면 API 가 그 열을 돌려줘야 합니다(이 단위 밖) |
| `/knowledge` 목록 | **MVP-2c** | `table` — 세트 이름(클릭 → 적재), 생성 시각. **적재는 하위 경로 `/knowledge/{id}`** 입니다 — 적재 API 가 세트별 경로여서 목록에 끌어오면 N+1 이고, `/runs` 가 Agent 이름을 뺀 것과 같은 이유입니다. **청크 수는 보이지 않습니다** — `IngestionSummary` 에 그 값이 없습니다(아래) |
| `/workflows` 목록 | **MVP-2c** | `table` 둘 — 정의(이름·현재 Version·수정)와 실행(상태 `badge`·현재 노드·기다리는 대상·요청). 표가 둘이라 **커서도 둘**이고(`cursor`·`runsCursor`) 한 표의 "다음 쪽"·"처음부터 보기" 는 상대편 커서를 **지킵니다**. 기다리는 대상에는 **라벨**을 붙입니다(자식 Run / 노드 실행 / 깨어남) — id 둘이 같은 mono 조각으로 그려져 라벨이 없으면 무엇을 기다리는지 구별되지 않습니다(MVP-2c 리뷰). 실행 행의 상태 칸에 **노드 상세로 가는 링크**가 있습니다(**P5-3** — 그 전까지 이 표는 Run 수준까지였습니다) |
| `/agents/new` 생성 | **P5-4** | `card` 안의 폼 — 이름·시스템 프롬프트·모델 id(비우면 배포 설정의 모델). 저장은 **서버 액션**이고(7.2) 성공하면 그 Agent 의 대화로 갑니다. 목록의 빈 결과에서도 이 화면으로 오는 길이 있습니다(7절) |
| `/agents/{id}/edit` 수정 | **P5-4** | 같은 폼에서 **이름 칸이 없습니다** — `PUT /agents/{id}` 는 정의만 바꿉니다. 저장 자리에 **"저장하면 새 버전이 만들어지고, 돌고 있는 Run 은 이전 버전을 계속 씁니다"**(R-12·spec 2.8). 폼에 없는 정의 칸(tools·memory…)은 **서버 액션이 현재 정의를 읽어 보존**합니다 — 브라우저가 정의를 보내지 않습니다(7.2) |
| `/workflows/runs/{id}` 노드 실행 | **P5-3** | `table` — 노드, 종류, 상태 `badge`, 시작, 종료, 실패 사유. 실패한 행은 **배경과 굵은 이름**으로 표시하고 표 위에 **"실패한 노드 N개"** 를 둡니다 — 색만으로 구별하지 않습니다(8절). **노드 출력 열은 두지 않습니다**: 출력은 `data` 평면에 머물고 조회 API 와 투영에 아예 없습니다(spec 0007 **D-4**, spec 0005 D-8). `card` 머리(Run 의 상태·요청 시각)도 **없습니다** — SDK 에 `getWorkflowRun` 이 없고, 내용이 비는 카드는 9절이 금지하는 자리표시입니다 |
| `/agents/{id}/chat` 대화 | **MVP-2e** | 위: 주고받은 것(`scroll-area`), 아래: `textarea` + 보내기 `button`. `model.delta` 를 **도착하는 대로 append** 합니다(MVP-2d 가 그 이벤트를 흘리게 했습니다). 항목마다 상태 `badge` 와 `/runs/{id}` 로 가는 "타임라인 보기". 도구 호출은 **이름만** 한 줄(본문은 그 타임라인이 보여줍니다). **맨 위에 무엇이 이어지는지 한 줄**을 둡니다 — 아래가 그 이유입니다. 좌우로 나누지 않습니다(목록 하나와 입력 하나라 나눌 것이 없습니다) |
| `/settings` | **MVP-2c** | `card` 셋 — 테마 선택, 연결(API base URL 읽기 전용 · `/healthz` 의 버전과 상태), API 키 안내. **키를 만들거나 보여주지 않습니다**(아래) |

**MVP-2 는 2a·2b·2c 로 쪼개졌습니다**(plan 0006 1절) — 목록 → 상세 → 대화. 사이드바의 **다섯 항목 전부**를 2a·2c 가 채웁니다(지금은 404 입니다). `/settings` 를 포함하는 것은 사람 결정입니다(2026-10-18, spec 0006 **D-13**) — 앱 셸에 Settings 가 없는 것이 더 낯설고, 사이드바에 두면서 404 로 보내는 것은 9절이 금지하는 바로 그것이기 때문입니다.

**`/settings` 는 키를 만들거나 보여주지 않습니다.** 키 원문은 발급 때 **한 번만** stdout 에 나가는 계약이고(spec 0001 2.9), 인증·비밀값에 닿는 변경은 사람 검토로 올립니다(AGENTS.md Loop). 그래서 그 화면이 담는 것은 **이미 존재하는 것들**뿐입니다 — 테마, API base URL(읽기 전용), `/healthz` 의 버전과 상태, 그리고 "키는 CLI 로 발급합니다" 라는 안내와 그 명령. 담을 것이 더 생기기 전까지 **자리표시를 두지 않습니다**(9절).

**`/knowledge` 는 청크 수를 보이지 않고, 대화 화면은 2c 에서 빠졌습니다 — 둘 다 이 문서가 없는 값을 요구했기 때문입니다.**
`IngestionSummary` 는 `{ingestion_id, knowledge_set_id, source, status, requested_at, started_at, finished_at, failure_reason}`
이고 청크 수가 없습니다. 대화는 더 큰 쪽입니다 — `model.completed` 의 payload 는 `finish_reason`·`usage` 뿐이고,
텍스트를 담는 `model.delta` 는 **예약**이라 런타임이 발생시키지 않으며(`packages/runtime/.../domain/events.py`,
spec 0002 2.7), `GET /runs/{id}` 에도 출력 열이 없습니다. 그러니 "스트리밍 텍스트를 append" 할 원본이 없습니다.
답변 없는 대화창은 9절이 금지하는 자리표시이므로(MVP-2b 의 "입력" 탭을 지운 것과 같은 판단) 그 화면은 **런타임이
답변을 이벤트로 흘리게 하는 단위**(spec 0006 **D-16**) 뒤로 갔습니다. 이 문서가 API 에 없는 값을 요구한 것이 이번이
**세 번째**입니다(입력 탭 → 청크 수 → 대화 텍스트) — `improvement-log/2026-10-18-005`.

**대화 화면은 "무엇이 이어지는가" 를 먼저 말합니다.** 이 화면은 대화처럼 보이지만 **대화가 아닙니다** —
`POST /agents/{id}/run` 의 본문은 `{ input, agent_version? }` 이고 **이력을 받는 자리가 없습니다**. 각 입력은
독립 Run 이고 모델은 이전 **질문**을 보지 못합니다. 다만 `memory_enabled` 인 Agent 는 Run 이 **`succeeded`**
로 끝날 때 그 **답변**이 Memory 에 남고 다음 Run 의 Context Compiler 가 그것을 포함합니다
(`packages/runtime/.../execute_run.py` 의 `_remember`). 그래서 화면은 그 플래그(`GET /agents/{id}` 의
`definition.memory_enabled`)로 **두 경우를 갈라** 말합니다 — 켜져 있으면 "성공으로 끝난 실행의 답변만 …
이전 질문은 전달되지 않습니다", 꺼져 있으면 "각 실행은 독립입니다". 뭉개면 9절이 금지하는 바로 그것이
됩니다: 이어지는 것처럼 보이는데 이어지지 않는 화면(MVP-2e, 2026-10-18).

**쓰기는 중계를 지나지 않습니다**(spec 0006 **D-18**). 실행 시작은 Next **서버 액션**이 받아 web 서버가 SDK 로
부릅니다. 중계 허용 목록은 `GET` 넷 그대로이고 브라우저는 중계로 쓰기를 하지 않습니다.

**Workflow 화면이 노드 수준까지 내려갔습니다**(P5-3). MVP-2c 까지는 Run 수준이 끝이었고(spec 0006 D-4) 이유는 노드 실행 목록이 `data` 평면에 있어 api 역할이 볼 수 없다는 것이었습니다 — **투영이 먼저 필요했고**(P5-1) 조회 경로가 생겼습니다(P5-2, `GET /workflow-runs/{id}/nodes`). 그 사이 **자리표시를 두지 않았습니다** — 없는 것을 있을 것처럼 그리지 않았고(9절의 정신), 화면은 데이터가 생긴 **뒤에** 왔습니다. 그래프 그림(캔버스)은 여전히 없습니다 — **P5-5** 이고 그 의존은 1절의 사람 결정을 기다립니다.

## 6. 도메인 → 표현 규약

용어는 [docs/domain.md](docs/domain.md) 의 것입니다. 표현을 여기서 고정하면 화면마다 다르게 그리는 일이 없습니다.

**Run 상태** — spec 0001 2.8 의 enum 과 1:1 입니다. `RunStatusBadge` 도메인 컴포넌트가 이 표를 소유합니다.

| status | `badge` variant | 아이콘(lucide) |
| --- | --- | --- |
| `queued` | `secondary` | `Clock` |
| `running` | `default` | `Loader2`(회전) |
| `waiting` | `outline` | `Hand` — HITL, 사람을 기다림 |
| `succeeded` | `secondary` | `CircleCheck` — 초록 계열 색으로 구분하지 않습니다(D-1). 색이 아니라 아이콘이 뜻을 전달합니다 |
| `failed` | `destructive` | `CircleX` |
| `cancelled` | `outline` | `Ban` |
| `timed_out` | `destructive` | `TimerOff` |

색으로만 뜻을 전달하지 않습니다 — 아이콘과 텍스트가 항상 같이 갑니다(8절 접근성).

**Workflow Run 상태** — `WorkflowRunStatus` enum(여덟)과 1:1 입니다. Run 과 **다른 enum** 이므로 badge 도 다릅니다(`WorkflowRunStatusBadge`). 기다림이 셋이고 전부 `outline` 이라 **아이콘이 구별합니다**.

| status | `badge` variant | 아이콘(lucide) |
| --- | --- | --- |
| `queued` | `secondary` | `Clock` |
| `running` | `default` | `Loader2`(회전) |
| `waiting_run` | `outline` | `CornerDownRight` — 자식 Run 을 기다림 |
| `waiting_approval` | `outline` | `Hand` — 사람을 기다림(Run 의 `waiting` 과 같은 뜻) |
| `waiting_timer` | `outline` | `Timer` — 시각을 기다림 |
| `succeeded` | `secondary` | `CircleCheck` |
| `failed` | `destructive` | `CircleX` |
| `cancelled` | `outline` | `Ban` |

**적재 상태** — `IngestionStatus` enum(넷). `IngestionStatusBadge` 가 소유하고 위 표의 같은 이름 행과 같은 모양입니다(`queued`·`running`·`succeeded`·`failed`).

세 badge 의 키 집합은 SDK 의 타입과 `Record<Status, …>` 로 묶여 있습니다 — api 에 상태가 하나 생기면 **컴파일이 깨집니다**(MVP-2c).


| 대상 | 규약 |
| --- | --- |
| 시간 | 상대 시간(`3분 전`)을 보이고 `title` 에 절대 시간(ISO). 소요 시간은 `1m 12s` |
| ID (`Run`, `Agent Version`) | `font-mono text-xs`, 앞 8자 + `…`, 클릭으로 복사(`tooltip` "복사됨") |
| 버전 | `badge` `outline`, `v3` |
| **외부에서 온 텍스트** (`Observation`, 도구 출력, 사용자 입력 재표시) | 항상 텍스트로 렌더합니다. `dangerouslySetInnerHTML` 금지. 코드·JSON 은 `<pre>` 에 `font-mono`. 이것은 표현 규약이자 신뢰 경계입니다([docs/architecture.md](docs/architecture.md) 3.1) |

## 7. 상태 규약

세 상태를 모든 데이터 화면이 같은 모양으로 갖습니다.

| 상태 | 표현 |
| --- | --- |
| 로딩 | `skeleton` — 실제 레이아웃과 같은 자리·크기 |
| 빈 결과 | 가운데 정렬, `text-muted-foreground` 한 줄 + **갈 곳이 있으면** 다음 행동 하나. `/agents` 는 **P5-4 가 생성 화면을 만든 뒤** 그 길을 둡니다(빈 목록에서도 「새 Agent」) — 그 전까지는 한 줄뿐이었습니다. **아직 갈 곳이 없는 목록은 지금도 한 줄만입니다**(404 로 가는 버튼은 9절 위반). **커서 쪽이 비어 있으면** 막다른 길이므로 "처음부터 보기" 를 붙입니다(MVP-2a, 2026-10-18) |
| 오류 | `alert` `destructive`. **첫 문장은 사용자가 할 수 있는 일**이고, SDK·HTTP 원문은 `details`("기술 정보", 기본 닫힘) 안에 `<pre>` 로 둡니다 — `aether-sdk: GET /runs?cursor=… failed with status …` 를 그대로 보이면 할 수 있는 일이 아무것도 적혀 있지 않습니다. 분기는 **상태 코드 필드**(`AetherHttpError.status`)로 하고 메시지 문구를 파싱하지 않습니다(MVP-2a 리뷰, 2026-10-18) |
| API 도달 불가 | 페이지가 깨지지 않고 오류 상태를 표시합니다. `/` healthz 가 첫 실례(spec F-4) |
| **없는 id**(404) | 목록의 오류 문구와 **다릅니다**. "api 가 떠 있는지 확인" 은 떠 있는 api 에 대해 틀린 지시이므로, 404 는 "…을 찾을 수 없습니다" + **목록으로 돌아가는 링크**입니다. 하나를 여는 화면들이 `DetailError` 하나를 씁니다(`/runs/{id}`·`/knowledge/{id}`). 분기는 `AetherHttpError.status` 필드입니다 — MVP-2c 리뷰 2026-10-18 |

### 7.1 목록의 정렬과 더 보기 (MVP-0 이 정한 계약)

목록 API 는 **커서 페이지**입니다(`limit` 기본 50, `cursor`, `next_cursor`). 화면의 규약을 여기서 고정합니다 — 화면마다 다르게 고르는 일이 없게.

| 결정 | 값 |
| --- | --- |
| 다음 쪽 | **링크 하나**("다음 쪽", `next_cursor` 가 있을 때만, 버튼 모양). `?cursor=` 로 **쪽을 교체**합니다 — 앞 쪽에 이어 붙이지 않습니다. **무한 스크롤을 쓰지 않습니다** — 스크롤 위치 복원·키보드 접근성·"끝" 의 표시가 전부 새 결정이 됩니다. 이어 붙이기도 같은 이유로 쓰지 않습니다(클라이언트 상태가 필요하고 같은 결정들이 돌아옵니다). 링크이므로 **뒤로 가기가 이전 쪽**이고 "이전" 규약이 따로 필요하지 않습니다. 라벨이 "더 보기" 가 아닌 이유는 하는 일이 그것이 아니기 때문입니다(MVP-2a, 2026-10-18) |
| 정렬 | **API 가 정합니다.** `/runs`·`/workflow-runs`·적재는 **최신 것부터**, `/agents`·`/workflows`·`/knowledge-sets` 는 오래된 것부터. 화면에 정렬 토글을 두지 않습니다(`order` 파라미터가 없습니다) |
| 열 정렬 표시 | 두지 않습니다. 정렬이 고정이므로 헤더는 클릭할 수 없습니다 |
| 마지막 쪽 | `next_cursor` 가 `null` 이면 버튼을 **숨깁니다**(비활성이 아니라 없음) |
| 깨진 커서 | API 가 `422 invalid_cursor` 를 줍니다 — 7절의 **오류** 상태로 표시하고, 다음 행동은 "처음부터 보기" 입니다 |

`/runs` 가 최신 것부터인 이유: 목록의 첫 쪽에 **방금 돌린 것**이 있어야 합니다. 그 결정은 API 쪽에 있고([docs/api.md](docs/api.md) 5.1), 화면은 그것을 뒤집지 않습니다.

### 7.2 쓰기 경로 규약 (P5-4 가 세웠습니다 — spec 0007 D-2)

브라우저의 쓰기는 **Next 서버 액션**만 받습니다. 중계(`lib/relay.ts`)의 허용 목록은 `GET` 넷 그대로이고 한 칸도 늘지 않습니다 — 중계는 키를 들고 있어 **열어 둔 만큼이 그대로 공개**되므로, 쓰기를 통과시키는 구멍 대신 **요청 모양을 web 이 소유**합니다. 선례는 MVP-2e 의 D-18(대화의 Run 시작)이고 P5-4 가 그것을 Agent 쓰기로 넓혔습니다.

| 결정 | 값 |
| --- | --- |
| 인자 | **원시 타입만**. 객체·`FormData` 를 통째로 받지 않습니다 — 받으면 브라우저가 요청 본문을 쓰는 것과 같습니다 |
| 검증 자리 | 액션 **본문의 첫 줄들**. 각 인자는 `typeof` + **내용 검사**(모양 정규식·공백·길이)를 함께 거치고, 실패하면 그 자리에서 `return` 합니다 — `createClient(` 보다 **앞**입니다 |
| 반환 | 던지지 않고 `{ ok: true, … }` 또는 `{ ok: false, message }`. 폼은 `message` 를 **폼 위 `alert`** 으로 보이고 **입력을 지우지 않습니다** |
| 분기 | `AetherHttpError.status` **필드**로만(문구 파싱 금지). 401/403 · 404 · 409 · 그 밖의 상태 · 네트워크의 다섯 갈래 |
| 메시지 | 키·`AETHER_API_URL`·업스트림 본문·SDK 오류 원문을 **넣지 않습니다**. 상태 코드만 보입니다 |
| `409` | **뜻은 부르는 쪽이 압니다** — 생성은 "같은 이름의 Agent 가 이미 있습니다", 수정은 "누군가 먼저 저장했습니다"(spec 0007 D-8) |
| 정의를 바꾸는 쓰기 | 폼이 **모르는 칸을 지우지 않습니다**. 액션이 현재 정의를 읽어 보이는 칸만 교체합니다 |
| 새 비밀값 | **없습니다**. web 은 이미 가진 `AETHER_API_KEY`·`AETHER_API_URL` 만 씁니다(spec 0007 D-10) |

이 규약을 **파일에서** 고정하는 구조 테스트가 있습니다 — `tests/arch/test_use_server_actions_are_sdk_only_and_validated.py`(R-2). `"use server"` 파일의 import·`fetch`·동적 import·`process.env` 읽기, 인자의 타입과 검증 순서, 브라우저 코드의 쓰기 호출, 그리고 중계에 쓰기 경로가 없다는 것까지 봅니다.

**세션·권한은 여기 없습니다.** "web 에 닿는 사람은 Agent 를 만들 수 있다" 가 지금의 선이고, 그것을 사람 단위로 긋는 것은 Phase 8 입니다(spec 0007 2.2·C-2 — 사람이 받아들인 비용).

## 8. 다크 모드 · 접근성 · 반응형

- **다크 모드는 기본 요구**입니다. 토큰만 쓰면(D-1) 공짜로 따라옵니다. `next-themes` 로 `class` 전략, 시스템 설정 따름 + 헤더 토글.
- **접근성**은 Radix 가 주는 것을 깨지 않는 것으로 시작합니다: 포커스 링(`ring`) 제거 금지, 아이콘 전용 버튼에 `aria-label`, 색만으로 뜻 전달 금지(6절). 평가 세트의 프런트엔드 팩 단계(`a11y`)가 켜지면(MVP-2 이후) 기계 판정이 됩니다.
- **반응형**은 앱 셸 하나로 답합니다: `lg` 미만에서 사이드바는 `sheet` 로. 표는 가로 스크롤(`scroll-area`), 카드는 세로 쌓임. 그 외 화면별 반응형 결정을 하지 않습니다.

## 9. 하지 않는 것

| 하지 않음 | 대신 |
| --- | --- |
| 손으로 쓴 CSS 파일, `style=` 인라인 | 토큰 유틸리티 |
| 임의 색·크기, Tailwind 팔레트 직접 참조 | 토큰. 부족하면 토큰 추가 |
| 두 번째 컴포넌트 라이브러리, 아이콘 세트 혼용 | shadcn + lucide |
| 페이지마다 다른 레이아웃 | 앱 셸 하나 |
| 애니메이션 라이브러리 선제 도입 | Tailwind `transition` + Radix 의 기본. 필요가 생기면 이 문서를 고치고 추가 |
| 캔버스의 기본 CSS 테마(`style.css`), 캔버스 안의 임의 색 | `base.css` + `--xy-*` 를 토큰으로 덮기(1절) |
| `dangerouslySetInnerHTML` | 텍스트 렌더(6절) |

## 10. 기계 판정 후보

이 문서의 규칙 중 도구로 잡을 수 있는 것입니다. 지금은 리뷰 항목이고, 승격은 [improvement-log/](improvement-log/README.md) 후보와 [harness/rules/promotion-gate.rule.md](harness/rules/promotion-gate.rule.md) 를 거칩니다. 규칙 파일은 보호 파일이라 사람이 반영합니다.

| 규칙 | 도구 | 계약 |
| --- | --- | --- |
| D-5 Radix 직접 import 금지 | dependency-cruiser | `apps/web/(app\|components)/(?!ui/)` → `radix-ui`, `@radix-ui/*` 금지. 지금은 P0-3b 의 grep — `from` 뒤에 `@radix-ui` 또는 `radix-ui` 가 오는 import 를 `components/ui/` 밖에서 찾는 것 — 이 대신합니다 |
| D-1 임의 값 금지 | `eslint-plugin-better-tailwindcss` 류 | `no-unregistered-classes` / arbitrary value 규칙 |
| 8절 접근성 | Playwright + axe (`a11y` 단계) | 프런트엔드 팩 `test:a11y`. MVP-2 에서 켬 |

## 이 문서를 갱신하는 때

| 사건 | 무엇을 바꾸는가 |
| --- | --- |
| 컴포넌트를 `shadcn add` 했다 | 4절에 한 줄 |
| 도메인 값의 표현을 정했다 (새 상태, 새 엔티티) | 6절 |
| 새 화면이 생겼다 | 5절 표 |
| 브랜드 색을 정했다 | 2절 — 그때까지는 `neutral` 이 결정입니다 |
| 라이브러리를 더했다 | 1절, 그리고 9절에서 그것을 "하지 않는 것" 에서 뺌 |

## 관련 문서

- [PROVENANCE.md](PROVENANCE.md) 7.1 — shadcn/ui 채택의 출처와 근거
- [specs/0001-phase-0-foundation.md](specs/0001-phase-0-foundation.md) 2.5 — `apps/web` 의 자리
- [intents/mvp-backlog.md](intents/mvp-backlog.md) P0-3b, MVP-2 — 이 문서가 구현되는 단위
- [docs/architecture.md](docs/architecture.md) AR-1 — web 은 sdk 만 압니다
- [docs/domain.md](docs/domain.md) — 6절이 표현하는 용어
