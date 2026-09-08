# TypeScript 팩

TypeScript 또는 JavaScript 프로젝트(`package.json` 기준)에 하네스를 붙일 때 읽습니다. 이 팩은 두 kind 를 모두 갖습니다. 브라우저에서 실행되는 애플리케이션은 [frontend/](frontend/), Node.js 서버·워커·CLI 는 [backend/](backend/) 를 따릅니다. 팩 계약과 로딩 순서는 [../README.md](../README.md) 가 소유합니다.

| 소유자 | 재검토 조건 |
| --- | --- |
| unassigned | TypeScript 가 조직 스택에서 사라질 때, 또는 감지 근거 파일(lockfile 종류)·기본 도구가 바뀔 때 |

## 감지 조건

| 스택 ID | 근거 파일 | 스크립트 실행 접두사 |
| --- | --- | --- |
| `typescript:pnpm` | `package.json` + `pnpm-lock.yaml` | `pnpm run` |
| `typescript:yarn` | `package.json` + `yarn.lock` | `yarn run` |
| `typescript:bun` | `package.json` + `bun.lock(b)` | `bun run` |
| `typescript:npm` | `package.json` + `package-lock.json` 또는 `npm-shrinkwrap.json` | `npm run --silent` |
| `typescript` | `package.json` 만 (lockfile 없음) | `npm run --silent` |

옛 스택 ID `node`, `node:pnpm` 등은 로더가 자동으로 새 ID 로 바꾸고 경고를 남깁니다.

## kind 판정

`package.json` 의 `dependencies`, `devDependencies`, `peerDependencies`, `optionalDependencies` **블록 안의** 키 이름으로만 판정합니다. 파일을 실행하거나 설치하지 않습니다. 파일 전체를 보면 `scripts` 의 명령 이름이나 `overrides` 의 버전 고정이 판정을 뒤집기 때문에 블록을 잘라내 봅니다.

| kind | 판정 근거 (의존성 이름) |
| --- | --- |
| `frontend` | `react`, `react-dom`, `react-native`, `react-native-web`, `vue`, `vue-router`, `nuxt`, `next`, `svelte`, `@sveltejs/kit`, `@angular/core`, `@angular/common`, `@angular/platform-browser`, `solid-js`, `preact`, `astro`, `gatsby`, `vite`, `@remix-run/react`, `expo`, `@builder.io/qwik` 중 하나 |
| `backend` | `express`, `@nestjs/core`, `@nestjs/common`, `@nestjs/platform-express`, `fastify`, `koa`, `hono`, `elysia`, `@hapi/hapi`, `restify`, `@adonisjs/core`, `@trpc/server`, `@apollo/server`, `apollo-server`, `apollo-server-express`, `graphql-yoga`, `prisma`, `@prisma/client`, `typeorm`, `drizzle-orm`, `mongoose`, `knex`, `sequelize`, `mikro-orm`, `@mikro-orm/core` 중 하나 |
| `fullstack` | 두 목록 모두에 해당 (한 `package.json` 에 FE·BE 가 함께 있는 저장소) |
| `unknown` | 어느 목록에도 없음 (workspace 루트, 라이브러리) |

`fullstack` 과 `unknown` 은 두 kind 의 **단계**를 합집합으로 씁니다. 강제하려면 `HARNESS_KIND=frontend` 처럼 재정의합니다. pnpm workspace 루트에서는 보통 `unknown` 이 나오므로, 패키지별로 `HARNESS_PROJECT_ROOT` 를 나누거나 루트 `harness.config` 에 `HARNESS_STEPS` 를 직접 적습니다.

**보호 패턴은 kind 와 무관합니다.** 아래 보호 패턴 표의 frontend·backend 행은 어느 kind 로 판정되든 모두 적용됩니다. kind 를 잘못 판정해도 평가 설정이 무방비가 되지 않게 하기 위해서입니다. kind 가 실제로 바꾸는 것은 기본 verify 단계뿐이고, 그로 인해 제외된 단계는 `verify.sh` 가 알려 줍니다.

## 기본 verify 단계

`package.json` 의 `scripts` 에 **실제로 존재하는** 항목만 단계가 됩니다. 같은 id 로 두 스크립트가 있으면(`typecheck` / `type-check`) 먼저 발견된 것만 씁니다.

### 공통

| script | id | layer | required |
| --- | --- | --- | --- |
| `typecheck` / `type-check` | `typecheck` | `quality` | true |
| `lint` | `lint` | `quality` | true |
| `format:check` | `format-check` | `quality` | false |
| `build` | `build` | `correctness` | true |
| `test:arch` / `arch` | `arch-test` | `architecture` | true |
| `depcruise` | `dep-check` | `architecture` | false |
| `test` | `test` | `correctness` | true |
| `test:unit` | `unit` | `correctness` | true |
| `test:integration` | `integration` | `correctness` | true |
| `test:e2e` / `e2e` | `e2e` | `behavior` | false |
| `bench` | `bench` | `performance` | false |

### frontend 추가

| script | id | layer | required | 채널 |
| --- | --- | --- | --- | --- |
| `test:a11y` | `a11y` | `behavior` | false | OBS-F2 |
| `test:visual` | `visual` | `behavior` | false | OBS-F3 |
| `test:storybook` | `storybook` | `behavior` | false | OBS-F1 |
| `size` / `size-limit` | `bundle-size` | `performance` | false | — |
| `lighthouse` | `lighthouse` | `performance` | false | OBS-F1 |

### backend 추가

| script | id | layer | required | 채널 |
| --- | --- | --- | --- | --- |
| `test:contract` | `contract` | `correctness` | false | OBS-B1 |
| `db:validate` / `prisma:validate` | `db-validate` | `architecture` | false | OBS-B3 |
| `migrate:check` | `migration-check` | `architecture` | false | OBS-B3 |
| `smoke` | `smoke` | `behavior` | false | OBS-B2 |
| `test:load` | `load` | `performance` | false | OBS-B7 |

## 보호 패턴

| 범위 | 목록 | 패턴 | 이유 |
| --- | --- | --- | --- |
| 공통 | 차단 | `.eslintrc*`, `eslint.config.*`, `biome.json(c)`, `.oxlintrc.json`, `.stylelintrc*` | 규칙을 끄면 `quality` 가 측정되지 않은 채 오릅니다 |
| 공통 | 차단 | `tsconfig.json`, `tsconfig.*.json` | `strict` 완화, `exclude` 추가로 타입 검사 범위가 좁아집니다 |
| 공통 | 차단 | `.dependency-cruiser.*`, `knip.json`, `knip.config.*` | 의존 경계 규칙과 미사용 코드 검사 자체입니다 |
| 공통 | 경고 | `package.json`, `.eslintignore`, `vitest.config.*`, `vitest.workspace.*`, `jest.config.*`, `.npmrc`, `.nvmrc`, `.node-version`, `pnpm-workspace.yaml`, `turbo.json`, `nx.json` | 의존성 변경은 정상이지만 `scripts` 의 검증 명령과 테스트 `exclude` 가 같은 파일에 있습니다 |
| frontend | 차단 | `playwright.config.*`, `cypress.config.*`, `.size-limit.*`, `lighthouserc.*`, `.lighthouserc.*`, `axe.config.*`, `.storybook/test-runner.*` | 브라우저 관측 채널과 성능 예산의 정의입니다. `lighthouserc.*` 와 `.lighthouserc.*` 는 glob 상 별개라 둘 다 필요합니다 |
| frontend | 경고 | `vite.config.*`, `next.config.*`, `nuxt.config.*`, `svelte.config.*`, `angular.json`, `.storybook/*`, `.browserslistrc`, `postcss.config.*`, `tailwind.config.*` | 빌드 설정 변경은 정상이지만 타입 검사 플러그인 제거가 여기서 일어납니다 |
| backend | 차단 | `jest-e2e.json`, `test/jest-e2e.json`, `.mocharc.*` | 통합·E2E 테스트 러너 설정입니다 |
| backend | 경고 | `prisma/schema.prisma`, `prisma/migrations/*`, `drizzle.config.*`, `knexfile.*`, `ormconfig.*`, `docker-compose*.y(a)ml` | 스키마·마이그레이션 변경은 정상이지만 통합 테스트 환경이 바뀝니다 |
| 공통 | 보안 | `.npmrc`, `.yarnrc(.yml)` | 레지스트리 토큰이 들어가는 파일입니다. `loop.sh` 가 사람 검토로 에스컬레이션합니다 |

## 문서 예시

코어 문서의 언어 중립 예시를 각 kind 의 도구 이름으로 옮긴 판입니다.

| kind | examples | config | improvement-log |
| --- | --- | --- | --- |
| frontend | [frontend/examples.md](frontend/examples.md) | [frontend/harness.config.example](frontend/harness.config.example) | [frontend/improvement-log.example.yaml](frontend/improvement-log.example.yaml) |
| backend | [backend/examples.md](backend/examples.md) | [backend/harness.config.example](backend/harness.config.example) | [backend/improvement-log.example.yaml](backend/improvement-log.example.yaml) |
