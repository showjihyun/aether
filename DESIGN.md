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
| Chat | MVP-2 | 좌: 대화(`scroll-area`), 하: `textarea` + `button`. 스트리밍 텍스트는 그대로 append |
| Run 목록 | MVP-2 | `table` — 상태 `badge`, Agent, 시작·소요, 행 클릭 → 상세 |
| Run 상세 | MVP-2 | `card` 머리(상태·trace id), `tabs`(이벤트 타임라인 / 트레이스 / 입력) |

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
| 빈 결과 | 가운데 정렬, `text-muted-foreground` 한 줄 + 다음 행동 `button` 하나("첫 Agent 만들기") |
| 오류 | `alert` `destructive`. 메시지는 사용자가 할 수 있는 일을 말합니다. 스택 트레이스는 접힘 |
| API 도달 불가 | 페이지가 깨지지 않고 오류 상태를 표시합니다. `/` healthz 가 첫 실례(spec F-4) |

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
