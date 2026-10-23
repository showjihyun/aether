# 캔버스 의존 실측 — `@xyflow/react` 와 `shadcn` 핀 (2026-10-23)

이 문서는 **H-1**(사람 결정)에 넘기는 측정 기록입니다. plan [0007](../../plans/0007-phase-5-visual-agent-builder.md) 3절이 H-1 의 산출물로 "DESIGN.md diff, 라이선스·크기·오프라인 설치 실측, '코드는 바뀌지 않는다'" 를 적었고, 그중 **측정**이 여기 있습니다.

**이 문서는 결정하지 않습니다.** ① 캔버스 라이브러리 채택 여부와 정확한 버전 ② attribution 방침 ③ `shadcn` 핀을 문서·코드 중 어느 쪽으로 닫을지 — 셋 다 [../../DESIGN.md](../../DESIGN.md) 1절을 소유한 사람이 정합니다.

| 항목 | 값 |
| --- | --- |
| 측정자 | 주 세션(에이전트). 사람 측정이 아닙니다 |
| 측정일 | 2026-10-23 |
| 방법 | npm registry 메타데이터 조회 + 배포 tarball 을 저장소 밖 격리 디렉터리에 받아 내용 검사(CSS·번들·`package.json`) |
| 저장소 영향 | **없음**. `package.json`·`pnpm-lock.yaml`·`node_modules` 를 바꾸지 않았고 설치도 하지 않았습니다 |

## 1. `@xyflow/react` — 측정값

후보는 plan 0007 의 P5-5·P5-6 절이 이미 이름을 적은 `@xyflow/react` 입니다. 측정 대상은 **최신 안정판 12.12.0**(2026-09-24 배포, 12.0.0 은 2024-07-09, 다음 메이저 `13.0.0-next.0` 은 아직 프리릴리스).

| 항목 | 실측값 | 왜 묻는가 |
| --- | --- | --- |
| 라이선스 | **MIT**. 전이 의존 전부 permissive — `zustand`·`classcat`·`@xyflow/system`·`use-sync-external-store` MIT, `d3-drag`·`d3-zoom`·`d3-selection`·`d3-interpolate` **ISC**. copyleft 없음 | On-Prem 배포에 따라가는 라이선스 |
| 패키지 크기 | tarball **251 KB**, 펼쳐 **1.19 MB** / 516 파일(대부분 `.d.ts`·소스맵). `@xyflow/system@0.0.83` 은 펼쳐 **694 KB** | 오프라인 번들에 담는 용량 |
| 브라우저로 가는 양 | ESM `dist/esm/index.js` **233,341 B raw / 52,290 B gzip**. CSS: `dist/base.css` **13,585 B / 2,451 B gzip**, `dist/style.css`(기본 테마) 18,596 B / 3,068 B gzip | 화면 무게 |
| 설치 시 실행되는 스크립트 | **없습니다** — 배포 `package.json` 에 `install`·`postinstall` 이 없습니다(`dev`·`build`·`css`·`lint`·`typecheck` 뿐). 네이티브 바이너리(`.node`·`.exe`) **0개**, `optionalDependencies` 없음 | 에어갭 설치에서 네트워크를 타는 지점 |
| **오프라인 설치(DP-4)** | **가능**. 순수 JS tarball 사슬이고 설치 중 빌드가 돌지 않으므로, pnpm 스토어를 복제한(또는 `pnpm fetch` 로 받아 둔) 환경에서 네트워크 없이 설치됩니다 | spec 0007 DP-4 |
| **런타임 네트워크** | **없습니다**. ESM 번들에 `fetch(`·`XMLHttpRequest`·`importScripts` **0건**, 두 CSS 에 `url(`·`http` **0건** — 폰트·아이콘·스프라이트를 받지 않습니다. 번들 안의 `https://…` 문자열은 전부 JSDoc 주석과 아래의 attribution 링크입니다 | plan 0007 의 중단 조건("캔버스 라이브러리가 런타임 네트워크를 요구") |
| React 19 / Next 16 | peer 는 `react >=17`·`react-dom >=17`·`@types/react >=17`. 전이 `zustand@^4.4.0` → **4.5.7**(peer `react >=16.8`) → `use-sync-external-store@^1.2.2` → **1.7.0**(peer 에 `^19.0.0` 명시). `apps/web` 의 `react@^19.3.0`·`next@^16.3.5` 를 막는 핀이 없습니다 | 설치가 되는지 |

### 1.1 걸리는 것 하나 — 기본으로 그려지는 attribution 링크

`<ReactFlow>` 는 기본으로 캔버스 우하단에 `.react-flow__attribution` 패널을 그리고, 그 안은 `<a href="https://reactflow.dev…" target="_blank" rel="noopener noreferrer" aria-label="React Flow attribution">React Flow</a>` 입니다.

- **네트워크를 타지는 않습니다**(클릭하지 않으면 요청이 없습니다). 그래서 에어갭에서 빌드·렌더가 깨지지 않습니다. 다만 **열리지 않는 외부 링크가 화면에 남습니다.**
- 끄는 수단은 `proOptions={{ hideAttribution: true }}` 한 줄이고, 개발 모드에서만 콘솔 경고가 한 번 납니다.
- 패키지 소스 주석은 "숨기려면 React Flow Pro 를 구독해 달라" 고 **요청**합니다. MIT 라이선스 본문이 금지하는 것은 **아니며**, 유료 구독 요구입니다.
- 그러므로 이것은 **돈·정책 결정이고 에이전트가 고르지 않습니다.** 선택지 셋: **(a)** 링크를 그대로 둔다 **(b)** 구독하고 끈다 **(c)** 구독 없이 끈다(라이선스 위반은 아니나 상류의 요청을 어깁니다).

### 1.2 토큰 규약(D-1)과 양립하는가 — 예, 예외 둘을 적습니다

`base.css` 는 색·선폭을 **`--xy-*` 변수 28곳**에서 `var(--xy-X, var(--xy-X-default))` 꼴로 읽습니다. 따라서 `app/globals.css` 에서 `--xy-edge-stroke: var(--border)` 처럼 **우리 토큰으로 덮으면 패키지 기본 hex 가 전혀 쓰이지 않습니다**. 기본 테마 `style.css` 는 쓰지 않습니다(plan 0007 P5-5 의 「주의」).

변수 뒤에 숨지 않은 hex 가 `base.css` 에 **둘** 있습니다 — 숨기지 않고 적습니다.

| 위치 | 값 | 평가 |
| --- | --- | --- |
| `.react-flow__attribution a` | `color: #999` | 1.1 의 attribution 결정에 딸린 것입니다. (b)·(c) 를 고르면 그 요소가 사라집니다 |
| `.react-flow__resize-control.handle` | `border: 1px solid #fff` | **NodeResizer** 전용입니다. P5-5·P5-6 은 좌표를 저장하지 않으므로(spec 0007 D-9) 그 컴포넌트를 쓰지 않습니다 |

### 1.3 "채택하지 않는다" 의 비용

캔버스를 손으로 그리면(SVG + 자동 배치) 의존은 0이지만 **확대·이동·히트테스트·키보드 접근성**을 직접 만들어야 하고, DESIGN.md 8절과 P5-8(a11y 러너)이 그 코드를 판정합니다. `@xyflow/react` 는 `A11yDescriptions` 와 키보드 이동을 이미 가지고 있습니다. P5-5 는 "그리기만" 이라 차이가 작지만 **P5-6(쓰기)에서 커집니다**.

## 2. `shadcn` 핀 불일치 — 원인

spec 0007 **C-6** 이 보고만 하기로 한 불일치(문서 `3.8.5` ↔ `package.json` `4.21.0`)의 출처를 찾았습니다.

| 사실 | 근거 |
| --- | --- |
| P0-3b 는 문서대로 `"shadcn": "3.8.5"` 를 박았습니다 | `git show d266b01:apps/web/package.json` 39행 |
| 지금 `package.json` 과 `pnpm-lock.yaml` 은 **4.21.0** 입니다 | `apps/web/package.json` 39행, `pnpm-lock.yaml` 99행 |
| 바꾼 것은 **Dependabot 의 major 범프 병합**입니다 | 커밋 `f72728c` *Bump shadcn from 3.8.5 to 4.21.0*, dependabot[bot], **2026-10-03** |
| 그 범프 뒤 **4.x CLI 는 한 번도 쓰이지 않았습니다** | `git log f72728c..HEAD -- apps/web/components/ui` → 커밋 **0건**. `apps/web/components.json` 도 3.x 모양 그대로(`tailwind.config: ""`, `registries: {}`) |
| 로컬 설치 트리에는 아직 3.8.5 만 있습니다 | `node_modules/.pnpm/shadcn@3.8.5_*` 둘, 4.21.0 디렉터리 없음 — lock 보다 오래된 설치 |

즉 불일치는 설계 변경이 아니라 **자동 범프가 DESIGN.md 의 의도적 핀을 지나간 것**이고, 그 핀의 이유(v4 는 `init` 을 프리셋 8종으로 바꿔 `new-york + neutral` 을 지정할 수 없다)는 **아직 시험되지 않았습니다**.

| 방향 | 비용 | 위험 |
| --- | --- | --- |
| **(가) 코드를 문서대로 3.8.5 로 내린다** | `apps/web/package.json` 한 줄 + `pnpm install` 로 lock 갱신. 생성물 `components/ui/` 17개는 **그대로** — 4.x 가 만든 파일이 하나도 없습니다 | 거의 없습니다. 다만 Dependabot 이 같은 범프를 또 올리므로 `.github/dependabot.yml` 에 major `ignore` 를 더하는 것이 세트이고, 그것은 **보호 파일이라 사람이 커밋합니다** |
| **(나) 문서를 4.21.0 으로 올린다** | DESIGN.md 1절 그 칸의 **이유 문장까지** 다시 써야 합니다("3.x 마지막 안정판에 고정" 이 근거를 잃습니다). 그리고 4.x CLI 로 `shadcn add` 가 **지금의 `components.json` 에서 도는지** 한 번 실측해야 합니다 | `add` 가 프리셋·registry 를 요구하면 그 자리에서 **새 시각적 결정**이 생깁니다 — DESIGN.md 가 피하려던 바로 그 순간입니다 |

**측정에서 나오는 권고는 (가) 입니다** — 핀의 근거가 아직 유효하고, 생성물이 4.x 로 오염되지 않아 되돌리는 비용이 지금 가장 쌉니다. 결정은 사람입니다.

## 3. DESIGN.md 를 어떻게 고치는가 (사람이 커밋)

### 3.1 1절 표 — 캔버스 행 (캔버스를 **채택**할 때만)

`테마 전환` 행 다음에 한 줄을 넣습니다. 세 칸의 내용은 이렇습니다.

- **층**: `캔버스`
- **선택**: **`@xyflow/react`** — 버전 고정(`12.12.0`). `dist/base.css` 만 import 하고 **기본 테마 `style.css` 는 쓰지 않습니다**. 색·선폭은 `app/globals.css` 에서 `--xy-*` 를 2절 토큰으로 덮습니다
- **왜 이것인가**: Workflow 그래프를 그리는 유일한 자리(P5-5·P5-6). MIT, 설치 스크립트·런타임 네트워크 없음(오프라인 DP-4 실측 — 이 문서를 `docs/measurements/canvas-dependency-2026-10-23.md` 로 링크). attribution 링크는 1.1 에서 고른 방침을 적습니다

> 한 줄짜리 마크다운 표 조각을 코드 블록으로 붙이지 않은 이유: 하네스의 `links` 단계는 코드 블록 안의 마크다운 링크 표기도 **이 문서 위치 기준**으로 검사합니다. DESIGN.md 는 저장소 루트에 있어 같은 경로가 다른 곳을 가리킵니다. (이 문서를 쓰면서 실제로 그 단계에 한 번 걸렸습니다 — 괄호 표기를 백틱으로 감싸도 검사는 그것을 링크로 읽습니다.)

### 3.2 `shadcn` 핀

**(가)** 를 고르면 **문서는 그대로 두고** `apps/web/package.json` 의 `"shadcn": "4.21.0"` 을 `"3.8.5"` 로 내리고 `pnpm install --filter web` 로 lock 을 갱신합니다. **(나)** 를 고르면 DESIGN.md 1절 13행의 세 자리와 3절 37·44행의 "(고정된 3.8.5)" 를 고치고 이유 문장을 다시 씁니다.

### 3.3 9절 — plan 과의 작은 불일치를 **보고합니다**

plan 0007 의 H-1 절은 "9절 '하지 않는 것' 에서 그 항목을 뺌" 을 요구하는데, **9절에 캔버스 항목이 없습니다.** 지금 9절의 라이브러리 금지 행은 「두 번째 컴포넌트 라이브러리, 아이콘 세트 혼용」과 「애니메이션 라이브러리 선제 도입」둘이고 캔버스는 어느 쪽도 아닙니다. 그러므로 **뺄 것이 없고**, 1절 마지막 문장("여기 없는 라이브러리(차트, 모션, 다른 컴포넌트 킷)는 필요가 생긴 단위에서 이 문서를 고쳐 추가합니다")이 이미 그 절차를 소유합니다. 한 줄을 보태고 싶다면 9절 「하지 않음」에 "캔버스의 기본 CSS 테마(`style.css`), 캔버스 안의 임의 색", 「대신」에 "`base.css` + `--xy-*` 를 토큰으로 덮기(1절)" 입니다.

### 3.4 "코드는 바뀌지 않는다"

H-1 은 **문서와 핀 결정**입니다. 3.1 은 DESIGN.md 한 줄, 3.2 는 `package.json` 한 줄과 lock 입니다. **`apps/web` 의 화면 코드와 테스트는 한 글자도 바뀌지 않습니다** — `@xyflow/react` 를 실제로 import 하는 것은 **P5-5** 이고, spec 0007 R-10 의 문서 테스트도 P5-5 가 세웁니다(plan 0007 의 H-1·R-10 행).

## 관련 문서

- [../../DESIGN.md](../../DESIGN.md) — H-1 이 고치는 문서(1절 스택, 2절 토큰, 9절 하지 않는 것)
- [../../plans/0007-phase-5-visual-agent-builder.md](../../plans/0007-phase-5-visual-agent-builder.md) — H-1·P5-5·P5-6 과 중단 조건
- [../../specs/0007-phase-5-visual-agent-builder.md](../../specs/0007-phase-5-visual-agent-builder.md) — D-1·D-9·R-10·C-6·DP-4
- [../../intents/mvp-backlog.md](../../intents/mvp-backlog.md) — H-1 의 상태 정본
