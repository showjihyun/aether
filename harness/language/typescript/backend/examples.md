# TypeScript 백엔드 예시

이 문서는 코어 문서의 언어 중립 예시를 TypeScript 백엔드(Node.js, NestJS 또는 Express, pnpm, ESLint, dependency-cruiser, Jest, Prisma, Testcontainers) 스택의 실제 도구 이름으로 옮긴 판입니다. 코어 문서가 "아키텍처 규칙 도구", "통합 테스트" 처럼 추상적으로 적은 자리를 이 스택에서는 무엇으로 구현하는지 알고 싶을 때 읽습니다. 규칙 ID 를 발급하지 않으며, 코어 문장을 복제하지 않고 링크로 가리킵니다. 각 절은 코어의 어느 문서·어느 예시를 구체화한 것인지 첫 줄에 밝힙니다.

같은 언어의 프론트엔드 판은 [../frontend/examples.md](../frontend/examples.md) 입니다. 두 kind 는 lint·타입 검사를 공유하지만, 관측 채널(OBS-F 대 OBS-B)과 보호해야 할 설정 파일이 다릅니다.

## 1. 계층 규칙 위반과 승격 경로

> 코어: [../../../references/harness-elements.md](../../../references/harness-elements.md) 2.1 "승격 경로 예시", [../../../rules/lesson-placement.rule.md](../../../rules/lesson-placement.rule.md) 예시 1

프로젝트의 계층 규칙은 `controller → service(use-case) → repository → PrismaService` 입니다. 에이전트가 `MemberController` 에 `PrismaService` 를 직접 주입해 `prisma.member.findUnique` 를 호출하는 코드를 만들었고, 의존 경계 검사가 이를 잡았습니다.

사다리의 0~2단계와 5단계는 언어와 무관하므로 코어가 소유합니다. 이 팩이 채우는 것은 도구가 실제로 갈리는 3·4단계뿐입니다.

| 단계 | 등급 | 이 스택에서의 형태 |
| --- | --- | --- |
| 3 | EL-6 | dependency-cruiser 규칙을 `.dependency-cruiser.cjs` 에 추가 |
| 4 | EL-6+ | 규칙의 `comment` 에 허용 경로(service 경유)를 적어 넣음 |

3단계와 4단계의 규칙은 다음과 같습니다.

```js
// .dependency-cruiser.cjs
module.exports = {
  forbidden: [
    {
      name: 'controllers-not-to-persistence',
      severity: 'error',
      comment:
        'controller 는 service 를 경유합니다. 허용 경로: controller → service → repository → PrismaService ' +
        '(docs/architecture/layers.md)',
      from: { path: '\\.controller\\.ts$' },
      to: { path: '(\\.repository\\.ts$|/prisma/)' },
    },
    {
      name: 'domain-no-framework',
      severity: 'error',
      comment: 'domain 은 NestJS·Prisma 에 의존하지 않습니다. 프레임워크 타입은 adapter 계층에 둡니다.',
      from: { path: '^src/domain/' },
      to: { path: 'node_modules/(@nestjs|@prisma|prisma)/' },
    },
  ],
  options: { tsConfig: { fileName: 'tsconfig.json' } },
};
```

NestJS 모듈 경계를 컴파일 시점에 걸려면 `@nestjs/core` 의 모듈 `exports` 목록을 좁히는 것도 방법이지만, 그것은 런타임 DI 오류로 드러나므로 EL-5(테스트) 등급입니다. 정적 검사(EL-6)가 더 빠르고 메시지를 통제할 수 있습니다.

승격 후 하위 등급 중복을 제거하는 규범은 코어가 소유합니다. 이 스택에서 진입점 문서에 남기는 것은 "계층 규칙은 `.dependency-cruiser.cjs` 가 정본이며 `harness/scripts/verify.sh --only arch-test` 로 확인한다" 는 한 줄과 링크뿐입니다.

이 사건의 improvement candidate 는 [improvement-log.example.yaml](improvement-log.example.yaml) 입니다.

## 2. AGENTS.md 비대화 사례

> 코어: [../../../rules/context-hygiene.rule.md](../../../rules/context-hygiene.rule.md) 예시 1, [../../../rules/lesson-placement.rule.md](../../../rules/lesson-placement.rule.md) 예시 2

실패가 생길 때마다 한 줄씩 추가한 결과 진입점 문서가 규칙 목록이 된 NestJS 프로젝트의 사례입니다.

```markdown
# AGENTS.md

## Rules

- Controller 에서 PrismaService 를 직접 주입하지 않는다.
- Prisma 모델 객체를 응답으로 그대로 반환하지 않는다. DTO 를 거친다.
- 모든 엔드포인트에 supertest 통합 테스트를 작성한다.
- Date 대신 ISO 8601 문자열로 직렬화한다.
- moment 를 쓰지 말 것. (2026-03 타임존 버그 때문)
- MemberService.updateProfile 은 반드시 prisma.$transaction 안에서 호출한다.
- 단, 배치 워커에서는 트랜잭션 없이 호출해도 된다.
- 통합 테스트가 느리면 Testcontainers 대신 sqlite 로 돌린다.
- 급할 때는 통합 테스트 생략 가능.
- ... (이하 200줄)
```

각 줄을 어느 자리로 옮길지의 판정 절차, 정본 자리, `preferred_enforcement` 값은 코어의 두 규칙 문서가 소유합니다. 여기서는 **그 자리를 이 스택에서 무엇으로 구현하는가**만 적습니다.

| before 항목 | 이 스택의 도구 |
| --- | --- |
| Controller → PrismaService 직접 주입 금지 | dependency-cruiser `controllers-not-to-persistence` |
| Prisma 모델 응답 반환 금지 | dependency-cruiser (`controller → @prisma/client` 타입 import 금지) 또는 `no-restricted-imports` |
| 모든 엔드포인트에 통합 테스트 | `integration` 단계(supertest + Testcontainers) + Stop hook |
| `Date` 대신 ISO 문자열 | `class-transformer` 의 `@Transform` 규약 + ESLint `no-restricted-syntax` |
| `moment` 금지 (타임존 버그) | ESLint `no-restricted-imports: ['moment']` + 타임존 회귀 테스트 1건 |
| 특정 서비스 메서드의 트랜잭션 경계 | `docs/architecture/transactions.md` |

교정 후 AGENTS.md 에는 "계층 규칙은 `.dependency-cruiser.cjs`, 코드 규칙은 `eslint.config.js` 가 정본이며 `./harness/scripts/verify.sh` 가 잡는다" 만 남습니다.

## 3. verify 단계와 관측 채널

> 코어: [../../../references/agent-observability.md](../../../references/agent-observability.md) 2.2 "Backend 채널", 2.3 "공통 채널"

코어 문서는 채널의 정의와 우선순위만 정합니다. 이 스택에서 각 채널을 어떤 명령으로 확보하는지는 다음과 같습니다. 실제 `HARNESS_STEPS` 는 [harness.config.example](harness.config.example) 을 따릅니다.

| 채널 | 이 스택에서 확보하는 명령 | 공급하는 계층 |
| --- | --- | --- |
| OBS-B1 Integration Test | `jest --config test/jest-e2e.json` (supertest + `@testcontainers/postgresql` 로 실제 DB 기동) | `correctness`, `behavior` |
| OBS-B2 curl | `curl -sS -o /dev/null -w '%{http_code}' http://localhost:3000/health` (`@nestjs/terminus`) | `behavior` |
| OBS-B3 Database Query | 스키마 반영 확인은 `prisma migrate diff --from-migrations prisma/migrations --to-schema-datamodel prisma/schema.prisma --exit-code` (조회 자체는 `psql` 등 스택 무관 도구) | `behavior`, `architecture` |
| OBS-B4 Application Log | pino JSON 로그를 `.harness/logs/app.log` 에 남기고 `grep -cE '"level":(50|60)' .harness/logs/app.log` (50=error, 60=fatal) | `behavior` |
| OBS-B5 Metric | `prom-client` 의 `/metrics` 를 `curl -sS http://localhost:3000/metrics \| grep http_request_errors_total` | `performance` |
| OBS-B6 Trace | `@opentelemetry/sdk-node` + OTLP 수집기 조회 결과를 `.harness/logs/trace.log` 로 저장 | `performance` |
| OBS-B7 Load Test | `k6 run load/smoke.js` 또는 `autocannon -c 50 -d 10 http://localhost:3000/api/orders` | `performance` |

`OBS-C1`(exit code)과 `OBS-C3`(diff)은 언어와 무관하므로 여기 적지 않습니다. 코어가 소유합니다.

`smoke` 단계는 앱을 띄우고 curl 을 친 뒤 내리는 스크립트가 필요합니다. 그 스크립트는 프로젝트가 소유하며 `HARNESS_STEPS` 에서 `pnpm run smoke` 로 호출합니다.

```bash
#!/usr/bin/env bash
# scripts/smoke.sh — OBS-B2. 앱을 띄우고 health 를 확인한 뒤 내립니다.
set -euo pipefail
node dist/main.js > .harness/logs/app.log 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do
  code="$(curl -sS -o /dev/null -w '%{http_code}' http://localhost:3000/health || true)"
  [[ "$code" == "200" ]] && exit 0
  sleep 1
done
echo "health 가 30초 안에 200 을 돌려주지 않았습니다 (마지막: ${code})" >&2
exit 1
```

## 4. 보호 패턴의 근거

> 코어: [../../../rules/evaluation-integrity.rule.md](../../../rules/evaluation-integrity.rule.md) EI-1, EI-6, [../../../hooks/README.md](../../../hooks/README.md)

`lang.sh` 의 보호 목록은 다음 근거로 정했습니다. 공통 패턴(ESLint, tsconfig, dependency-cruiser)의 근거는 [../frontend/examples.md](../frontend/examples.md) 4절과 같습니다. 여기서는 backend 추가분만 적습니다.

| 패턴 | 목록 | 이 파일을 고치면 무엇이 약해지는가 |
| --- | --- | --- |
| `jest-e2e.json`, `test/jest-e2e.json` | 차단 | 통합 테스트 러너 설정입니다. `testPathIgnorePatterns` 를 늘리면 통합 테스트가 조용히 빠집니다 |
| `.mocharc.*` | 차단 | Mocha 를 쓰는 프로젝트의 같은 자리입니다 |
| `prisma/schema.prisma`, `prisma/migrations/*` | 경고 | 스키마 변경은 정상이지만 마이그레이션 없이 스키마만 바꾸면 `db-validate` 가 실패하고, 반대로 마이그레이션을 지우면 통과합니다 |
| `drizzle.config.*`, `knexfile.*`, `ormconfig.*` | 경고 | 테스트 DB 연결 대상을 바꿔 통합 테스트를 무력화할 수 있습니다 |
| `docker-compose*.y(a)ml` | 경고 | Testcontainers 대신 compose 로 의존성을 띄우는 프로젝트에서 통합 테스트 환경 자체입니다 |

`it.skip`, `describe.only`, `jest.mock` 으로 실제 DB 호출을 통째로 가짜로 바꾸는 것은 파일 패턴으로 잡히지 않습니다. 이것은 EI-6 의 "테스트 skip" 이며 리뷰와 REP-3 과제가 잡습니다.

## 5. improvement candidate 예시

- [improvement-log.example.yaml](improvement-log.example.yaml) — 1절 사건을 기록한 candidate. 코어 예시 [../../../improvement-log/2026-08-09-001.example.yaml](../../../improvement-log/2026-08-09-001.example.yaml) 과 같은 사건이며 클래스·도구 이름만 구체적입니다.

## 관련 문서

- [../README.md](../README.md) — TypeScript 팩 개요와 kind 판정
- [../frontend/examples.md](../frontend/examples.md) — 같은 언어의 프론트엔드 판
- [../../README.md](../../README.md) — 팩 규약
- [../../../references/agent-observability.md](../../../references/agent-observability.md) — OBS-* 채널 정의
- [../../../rules/evaluation-integrity.rule.md](../../../rules/evaluation-integrity.rule.md) — 보호 패턴의 규범
