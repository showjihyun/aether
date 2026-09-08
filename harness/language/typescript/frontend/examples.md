# TypeScript 프론트엔드 예시

이 문서는 코어 문서의 언어 중립 예시를 TypeScript 프론트엔드(React/Vite, pnpm, ESLint, dependency-cruiser, Vitest, Playwright) 스택의 실제 도구 이름으로 옮긴 판입니다. 코어 문서가 "아키텍처 규칙 도구", "브라우저 관측 채널" 처럼 추상적으로 적은 자리를 이 스택에서는 무엇으로 구현하는지 알고 싶을 때 읽습니다. 규칙 ID 를 발급하지 않으며, 코어 문장을 복제하지 않고 링크로 가리킵니다. 각 절은 코어의 어느 문서·어느 예시를 구체화한 것인지 첫 줄에 밝힙니다.

프론트엔드는 백엔드와 달리 **테스트가 전부 통과해도 화면이 비어 있거나 클릭이 죽어 있을 수 있습니다.** 그래서 이 스택의 하네스는 `behavior` 계층의 관측 채널(3절)을 다른 어떤 것보다 먼저 확보합니다.

## 1. 경계 규칙 위반과 승격 경로

> 코어: [../../../references/harness-elements.md](../../../references/harness-elements.md) 2.1 "승격 경로 예시", [../../../rules/lesson-placement.rule.md](../../../rules/lesson-placement.rule.md) 예시 1

프로젝트의 데이터 흐름 규칙은 `component → query hook → api client → fetch` 입니다. 에이전트가 `OrderSummary` 컴포넌트에서 `src/api/orders.ts` 의 `fetchOrder` 를 직접 호출하는 코드를 만들었고, 의존 경계 검사가 이를 잡았습니다. 백엔드의 "Controller → Repository 직접 의존" 과 같은 종류의 사건입니다.

사다리의 0~2단계와 5단계는 언어와 무관하므로 코어가 소유합니다. 이 팩이 채우는 것은 도구가 실제로 갈리는 3·4단계뿐입니다.

| 단계 | 등급 | 이 스택에서의 형태 |
| --- | --- | --- |
| 3 | EL-6 | dependency-cruiser 규칙을 `.dependency-cruiser.cjs` 에 추가 |
| 4 | EL-6+ | 규칙의 `comment` 에 허용 경로(query hook 경유)를 적어 넣음 |

3단계와 4단계의 규칙은 다음과 같습니다.

```js
// .dependency-cruiser.cjs
module.exports = {
  forbidden: [
    {
      name: 'components-not-to-api-client',
      severity: 'error',
      comment:
        'component 는 query hook 을 경유합니다. 허용 경로: component → query hook → api client ' +
        '(docs/architecture/data-flow.md)',
      from: { path: '^src/components' },
      to: { path: '^src/api' },
    },
    {
      name: 'features-no-cross-import',
      severity: 'error',
      comment: 'feature 간 직접 import 금지. 공유가 필요하면 src/shared 로 올립니다.',
      from: { path: '^src/features/([^/]+)/' },
      // $1 은 from 의 캡처를 가리킵니다. 제외는 lookahead 가 아니라 pathNot 으로 씁니다.
      // (?!$1) 로 쓰면 뒤에 경계가 없어 order 가 orders 를 import 하는 것을 놓칩니다.
      to: {
        path: '^src/features/([^/]+)/',
        pathNot: '^src/features/$1/',
      },
    },
  ],
  options: { tsConfig: { fileName: 'tsconfig.json' } },
};
```

ESLint 로 같은 경계를 걸려면 `eslint-plugin-boundaries` 또는 `no-restricted-imports` 의 `patterns` 와 `message` 를 씁니다. 어느 쪽이든 **실패 메시지에 허용 경로가 들어가야** 4단계입니다.

승격 후 하위 등급 중복을 제거하는 규범은 코어가 소유합니다. 이 스택에서 진입점 문서에 남기는 것은 "import 경계는 `.dependency-cruiser.cjs` 가 정본이며 `harness/scripts/verify.sh --only arch-test` 로 확인한다" 는 한 줄과 링크뿐입니다.

이 사건의 improvement candidate 는 [improvement-log.example.yaml](improvement-log.example.yaml) 입니다.

## 2. AGENTS.md 비대화 사례

> 코어: [../../../rules/context-hygiene.rule.md](../../../rules/context-hygiene.rule.md) 예시 1, [../../../rules/lesson-placement.rule.md](../../../rules/lesson-placement.rule.md) 예시 2

실패가 생길 때마다 한 줄씩 추가한 결과 진입점 문서가 규칙 목록이 된 React 프로젝트의 사례입니다.

```markdown
# AGENTS.md

## Rules

- 컴포넌트에서 api 모듈을 직접 import 하지 않는다.
- useEffect 안에서 직접 fetch 하지 않는다. TanStack Query 를 쓴다.
- any 를 쓰지 않는다.
- console.log 를 남기지 않는다.
- 모든 페이지에 Playwright E2E 를 작성한다.
- 결제 페이지는 반드시 lazy import 한다. (2026-03 번들 크기 사고 때문)
- PaymentForm 은 반드시 Suspense 경계 안에서 렌더링한다.
- 단, 서버 컴포넌트에서는 직접 fetch 해도 된다.
- 급할 때는 E2E 생략 가능.
- ... (이하 200줄)
```

각 줄을 어느 자리로 옮길지의 판정 절차, 정본 자리, `preferred_enforcement` 값은 코어의 두 규칙 문서가 소유합니다. 여기서는 **그 자리를 이 스택에서 무엇으로 구현하는가**만 적습니다.

| before 항목 | 이 스택의 도구 |
| --- | --- |
| 컴포넌트 → api 직접 import 금지 | dependency-cruiser `components-not-to-api-client` |
| `useEffect` 안 직접 fetch 금지 | ESLint `no-restricted-syntax` 또는 `@tanstack/eslint-plugin-query` |
| `any` 금지 | `@typescript-eslint/no-explicit-any: error` + `tsconfig` 의 `strict: true` |
| `console.log` 금지 | ESLint `no-console: ['error', { allow: ['warn', 'error'] }]` |
| 모든 페이지에 E2E | `e2e` 단계(Playwright) + Stop hook |
| 결제 페이지 번들 사고 | `.size-limit.json` 의 결제 청크 예산 1건 (`bundle-size` 단계) |
| 특정 컴포넌트의 Suspense 경계 | `docs/architecture/loading-states.md` |
| 서버 컴포넌트 예외 | dependency-cruiser `from.pathNot: '^src/app/.*/page\\.tsx$'` |

교정 후 AGENTS.md 에는 "import 경계는 `.dependency-cruiser.cjs`, 코드 규칙은 `eslint.config.js` 가 정본이며 `./harness/scripts/verify.sh` 가 잡는다" 만 남습니다.

## 3. verify 단계와 관측 채널

> 코어: [../../../references/agent-observability.md](../../../references/agent-observability.md) 2.1 "Frontend 채널", 2.3 "공통 채널", 4 "채널 확보 우선순위"

코어 문서는 채널의 정의와 우선순위만 정합니다. 이 스택에서 각 채널을 어떤 명령으로 확보하는지는 다음과 같습니다. 실제 `HARNESS_STEPS` 는 [harness.config.example](harness.config.example) 을 따릅니다.

| 채널 | 이 스택에서 확보하는 방법 | 공급하는 계층 |
| --- | --- | --- |
| OBS-F1 Browser | `pnpm exec playwright test --reporter=line` 을 `e2e` 단계로 등록 | `behavior` |
| OBS-F2 DOM | Playwright 안에서 `await page.locator('main').innerHTML()` 을 `.harness/logs/dom.log` 로 저장. 접근성 트리는 `@axe-core/playwright` 로 `a11y` 단계 | `behavior` |
| OBS-F3 Screenshot | `playwright.config.ts` 의 `use.screenshot = 'only-on-failure'`. 산출 경로 `test-results/` 를 `.harness/logs/` 로 복사 | `behavior` (판정은 `subjective`) |
| OBS-F4 Console | 아래 fixture 로 `page.on('console')` 을 수집해 `.harness/logs/console.log` 에 남기고, error 가 1건이라도 있으면 테스트를 실패시킴 | `behavior` |
| OBS-F5 Network | 아래 fixture 로 `page.on('response')` 에서 `status >= 400` 을 집계해 `.harness/logs/network.log` 에 남김 | `behavior` |

`OBS-C1`(exit code)과 `OBS-C3`(diff)은 언어와 무관하므로 여기 적지 않습니다. 코어가 소유합니다.

OBS-F4 와 OBS-F5 를 한 번에 확보하는 Playwright fixture 입니다. 코어 우선순위표에서 5순위이지만, 브라우저 러너(6순위)를 도입하는 순간 함께 확보됩니다.

```ts
// e2e/fixtures.ts
import { test as base, expect } from '@playwright/test';
import { appendFileSync, mkdirSync } from 'node:fs';

mkdirSync('.harness/logs', { recursive: true });

export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    const consoleErrors: string[] = [];
    const failedResponses: string[] = [];

    page.on('console', (msg) => {
      const line = `[${testInfo.title}] ${msg.type()}: ${msg.text()}\n`;
      appendFileSync('.harness/logs/console.log', line);
      if (msg.type() === 'error') consoleErrors.push(line);
    });
    page.on('response', (res) => {
      if (res.status() >= 400) {
        const line = `[${testInfo.title}] ${res.status()} ${res.request().method()} ${res.url()}\n`;
        appendFileSync('.harness/logs/network.log', line);
        failedResponses.push(line);
      }
    });

    await use(page);

    // 판정 명제는 기계가 판정 가능한 형태여야 합니다(rubric 2.3).
    expect(consoleErrors, 'console error 0건').toEqual([]);
    expect(failedResponses, 'HTTP >= 400 응답 0건').toEqual([]);
  },
});
export { expect };
```

`behavior` 계층의 판정 명제는 "화면이 좋아 보인다" 가 아니라 다음처럼 씁니다.

| 명제 | 판정 방법 |
| --- | --- |
| console error 0건 | 위 fixture 의 `consoleErrors` |
| HTTP >= 400 응답 0건 | 위 fixture 의 `failedResponses` |
| 결제 버튼이 뷰포트 안에 보이고 클릭 가능 | `await expect(page.getByRole('button', { name: '결제' })).toBeVisible()` + `toBeEnabled()` |
| 클릭 후 주문 완료 화면으로 전환 | `await expect(page).toHaveURL(/\/orders\/\d+\/complete/)` |
| 접근성 위반 0건 | `expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])` |

## 4. 보호 패턴의 근거

> 코어: [../../../rules/evaluation-integrity.rule.md](../../../rules/evaluation-integrity.rule.md) EI-1, EI-6, [../../../hooks/README.md](../../../hooks/README.md)

`lang.sh` 의 보호 목록은 다음 근거로 정했습니다. 목록을 늘리거나 줄이는 것은 하네스 변경이며 승격 절차를 거칩니다.

| 패턴 | 목록 | 이 파일을 고치면 무엇이 약해지는가 |
| --- | --- | --- |
| `eslint.config.*`, `.eslintrc*`, `biome.json(c)` | 차단 | 규칙을 `off` 로 바꾸거나 `ignores` 를 늘리면 `quality` 가 측정되지 않은 채 오릅니다 |
| `tsconfig.json`, `tsconfig.*.json` | 차단 | `strict: false`, `skipLibCheck`, `exclude` 추가로 타입 검사 범위가 좁아집니다 |
| `.dependency-cruiser.*` | 차단 | 1절의 경계 규칙 자체입니다. `severity: 'warn'` 으로 내리면 `architecture` 가 통과로 바뀝니다 |
| `playwright.config.*`, `cypress.config.*` | 차단 | `testIgnore`, `retries`, `screenshot` 설정이 관측 채널의 범위를 정합니다 |
| `.size-limit.*`, `lighthouserc.*` | 차단 | 성능 예산의 기준값입니다. 기준값 상향은 EI-2 의 평가 정의 변경입니다 |
| `lighthouserc.*`, `.lighthouserc.*` | 차단 | 두 이름은 glob 상 별개입니다. 둘 다 있어야 `.lighthouserc.json` 이 잡힙니다 |
| `axe.config.*`, `.storybook/test-runner.*` | 차단 | 접근성·컴포넌트 테스트의 규칙 집합입니다 |
| `package.json` | 경고 | 의존성 추가는 정상이지만 `scripts.test` 에 `--passWithNoTests` 를 붙이거나 검증 스크립트를 지우는 곳도 여기입니다 |
| `vitest.config.*`, `jest.config.*` | 경고 | `exclude`, `coverage.thresholds` 변경이 여기서 일어납니다 |
| `vite.config.*`, `next.config.*` | 경고 | `typescript.ignoreBuildErrors`, `eslint.ignoreDuringBuilds` 같은 빌드 시 검사 우회 옵션이 있습니다 |

`test.skip`, `test.only`, `// eslint-disable-next-line`, `// @ts-expect-error` 를 소스에 추가하는 것은 파일 패턴으로 잡히지 않습니다. 이것은 EI-6 의 "테스트 skip·억제 주석" 이며 리뷰와 REP-3 과제가 잡습니다. `eslint-comments/no-unlimited-disable` 같은 규칙으로 일부는 lint 단계에서 잡을 수 있습니다.

## 5. 조직 Baseline 과의 대응

이 팩의 기본값은 별도의 프론트엔드 Baseline(`FTS-*` 기술 스택 표)이 있는 조직에서 그 기본값과 맞도록 골랐습니다. Baseline 이 다른 도구를 기본값으로 정했다면 Baseline 이 이깁니다. 하네스는 검증 단계를 등록할 뿐 도구를 정하지 않습니다.

| FTS 항목 | Baseline 기본값 | 이 팩에서 쓰는 자리 |
| --- | --- | --- |
| 패키지 매니저 | pnpm | 스택 ID `typescript:pnpm`, 실행 접두사 `pnpm run` |
| lint·format·정적 분석 | ESLint + Prettier, Biome, tsc 중 선택 | `lint`, `typecheck` 단계, 차단 패턴 |
| unit·component test | Vitest + React Testing Library | `unit` 단계 |
| integration·E2E test | Playwright | `e2e` 단계, OBS-F1~F5 fixture |
| visual·accessibility | Playwright screenshot, axe-core | `a11y`, `visual` 단계 |

## 6. improvement candidate 예시

- [improvement-log.example.yaml](improvement-log.example.yaml) — 1절 사건을 기록한 candidate. 코어 예시 [../../../improvement-log/2026-08-09-001.example.yaml](../../../improvement-log/2026-08-09-001.example.yaml) 과 같은 종류의 사건이며 모듈·도구 이름만 구체적입니다.

## 관련 문서

- [../README.md](../README.md) — TypeScript 팩 개요와 kind 판정
- [../backend/examples.md](../backend/examples.md) — 같은 언어의 백엔드 판
- [../../README.md](../../README.md) — 팩 규약
- [../../../references/agent-observability.md](../../../references/agent-observability.md) — OBS-* 채널 정의
- [../../../evaluation/rubric.md](../../../evaluation/rubric.md) — `behavior` 판정 명제의 형식
