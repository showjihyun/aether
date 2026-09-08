# Lesson 배치 규칙 (LP)

이 문서는 작업 중에 얻은 lesson을 하네스의 어느 요소에 남길지 정합니다. 실패를 고친 직후, retro를 수행할 때, improvement log 항목의 `preferred_enforcement` 값을 정할 때 읽습니다. 같은 실수가 반복되는데 어디를 고쳐야 할지 판단이 서지 않을 때도 이 문서의 판정 절차를 그대로 실행합니다. lesson을 정본으로 기록해도 되는지(승격 여부)는 이 문서가 아니라 [promotion-gate.rule.md](promotion-gate.rule.md) 가 정합니다.

## 규칙

| ID | 규칙 |
| --- | --- |
| **LP-1** | 결정론적으로 검증할 수 있는 lesson은 자연어 지시가 아니라 검증으로 남깁니다. 같은 내용을 지시문과 검증 중 하나로만 쓸 수 있다면 검증을 택합니다. 지시문은 에이전트가 놓칠 수 있지만 검증은 놓치면 실패합니다. |
| **LP-2** | 특정 버그는 회귀 테스트로 남깁니다. 버그를 재현하는 테스트를 먼저 실패시키고, 수정 후 통과시킵니다. 재현 테스트 없이 수정만 한 버그는 lesson이 남지 않은 것으로 취급합니다. |
| **LP-3** | 반복되는 코드 실수는 lint rule 또는 architecture rule로 남깁니다. 같은 유형의 실수가 두 번 이상 관측되면 개별 수정에 그치지 않고 규칙화 대상으로 올립니다. |
| **LP-4** | AGENTS.md·CLAUDE.md 에는 프로젝트 전역에 적용되는 원칙만 둡니다. 특정 모듈·특정 사건에만 해당하는 내용은 전역 지시로 쓰지 않습니다. 길이 상한과 초과 시 조치는 [context-hygiene.rule.md](context-hygiene.rule.md) 를 따릅니다. |
| **LP-5** | 상세한 설계 지식은 문서에 둡니다. 왜 그렇게 설계했는지, 어떤 대안을 버렸는지, 경계가 어디인지는 `references/` 또는 프로젝트의 아키텍처 문서에 두고, 진입점 문서에서는 링크로만 가리킵니다. |
| **LP-6** | 실행 형태에 따라 자리를 나눕니다. 반복되는 절차는 skill, 특정 분야의 전문적 판단은 subagent, 반드시 실행해야 하는 검사는 hook, 에이전트가 반복하기 비효율적인 수작업은 script 또는 tool로 남깁니다. |
| **LP-7** | 같은 lesson을 두 자리 이상에 정본으로 두지 않습니다. 정본은 하나이고 나머지 자리에는 정본을 가리키는 링크만 둡니다. 검증과 문서가 같은 내용을 다룰 때 정본은 검증이며, 문서는 그 검증의 이유를 설명하는 자리입니다. |
| **LP-8** | 배치 결정은 improvement log 항목의 `harness_element` 와 `preferred_enforcement` 에 기록합니다. `preferred_enforcement` 값은 `test`, `lint`, `arch-rule`, `hook`, `script`, `doc`, `skill`, `subagent`, `instruction` 중 하나이며, 기록되지 않은 배치 결정은 수행하지 않은 것으로 봅니다. |

## 판정 절차

[../references/lesson-placement.md](../references/lesson-placement.md) 의 결정 트리를 실행 순서로 옮긴 것입니다. 위에서부터 순서대로 판정하고, 처음으로 참이 되는 항목에서 멈춥니다. 뒤 단계를 먼저 적용하지 않습니다.

1. **재현 가능한 단일 결함인가.** 입력과 기대 결과를 특정할 수 있다면 회귀 테스트로 남깁니다(LP-2). `preferred_enforcement` 는 `test` 입니다.
2. **코드 형태만 보고 기계적으로 판별할 수 있는 반복 실수인가.** 명명, import 방향, 금지 API, 계층 의존성처럼 정적으로 판별되면 lint rule 또는 architecture rule로 남깁니다(LP-3). `preferred_enforcement` 는 `lint` 또는 `arch-rule` 입니다.
3. **빠뜨리면 안 되는 필수 검사인가.** 사람이나 에이전트의 기억에 의존해서는 안 되는 검사라면 hook으로 강제합니다(LP-6). `preferred_enforcement` 는 `hook` 입니다.
4. **정해진 순서가 있는 반복 절차인가.** 매번 같은 단계를 밟는 작업이라면 skill로 남깁니다(LP-6). `preferred_enforcement` 는 `skill` 입니다.
5. **매번 판단이 필요한 전문 영역인가.** 절차로 고정되지 않고 맥락에 따른 판단이 필요하면 subagent로 분리합니다(LP-6). `preferred_enforcement` 는 `subagent` 입니다.
6. **에이전트가 반복하기 비효율적이거나 오류가 잦은 수작업인가.** 명령 조합, 데이터 수집, 상태 확인 같은 작업은 script 또는 tool로 남깁니다(LP-6). `preferred_enforcement` 는 `script` 입니다.
7. **설계의 배경과 경계를 설명해야 하는 지식인가.** 문서로 남기고 진입점에서 링크합니다(LP-5). `preferred_enforcement` 는 `doc` 입니다.
8. **위 어디에도 해당하지 않고, 프로젝트 전역에 항상 적용되는 원칙인가.** 이때만 AGENTS.md·CLAUDE.md 에 한 줄로 추가합니다(LP-4). `preferred_enforcement` 는 `instruction` 입니다.
9. **여기까지 와도 참이 되는 항목이 없다면 배치하지 않습니다.** improvement log 항목을 `candidate` 상태로 남기고 재발을 기다립니다. 관측 1회짜리 사건을 전역 지시로 만들지 않습니다.

배치 자리를 정한 뒤에는 다음을 확인합니다.

- 같은 내용을 이미 다른 자리에서 다루고 있는지 검색합니다. 있으면 새로 만들지 않고 기존 정본을 강화합니다(LP-7).
- 1~3번에서 멈출 수 있었는데 4번 이하를 택했다면 그 이유를 improvement log의 `evidence` 에 남깁니다(LP-1).
- 배치 결과가 실제로 실패를 잡는지 회귀 검증합니다. 절차는 [harness-change-control.rule.md](harness-change-control.rule.md) 를 따릅니다.

## 위반 예시와 교정

### 예시 1 — Controller가 Repository를 직접 호출한 사건

프로젝트의 계층 규칙은 다음과 같습니다.

```text
Controller
   ↓
Application Service
   ↓
Domain
   ↓
Repository
```

그런데 에이전트가 다음 구조의 코드를 만들었고, 아키텍처 테스트가 이를 잡았습니다.

```text
Controller
   ↓
Repository
```

**위반**: 에이전트에게 "Controller에서 Repository를 직접 호출하지 말고 Application Service를 거쳐라"라고 지시해 코드를 고치고 종료했습니다. 테스트는 통과했지만 lesson은 대화 안에만 남았고, 다음 기능에서 같은 실수가 다시 발생할 수 있습니다. LP-1과 LP-3 위반입니다.

**교정**: 판정 절차 2번에서 멈춥니다. 계층 의존성은 정적으로 판별되므로 architecture rule로 남깁니다.

```text
실패
 ↓
원인 분석
 ↓
architecture 문서 보강 (LP-5)
 ↓
진입점 문서에서 해당 문서 링크 (LP-4)
 ↓
architecture rule 보강 (LP-3)
 ↓
위반 시 원인을 알려주는 실패 메시지 제공
```

improvement log 항목에는 `harness_element: HE-4`, `preferred_enforcement: arch-rule` 을 기록합니다. 전역 지시에는 "계층 규칙은 architecture 문서와 architecture rule이 정본"이라는 한 줄과 링크만 남기고, 규칙 본문은 옮기지 않습니다(LP-7).

### 예시 2 — AGENTS.md 무한 증식

**위반**: 실패가 발생할 때마다 AGENTS.md에 한 줄씩 규칙을 추가했습니다.

```markdown
- Controller에서 Repository를 직접 사용하지 않는다.
- Entity를 Controller에 반환하지 않는다.
- 모든 API에는 Integration Test를 작성한다.
- 시간 값은 표준 시각 타입(UTC 기준)만 사용한다.
```

몇 달 뒤 수백 줄짜리 문서가 되고, 모든 규칙이 중요하다고 표시되어 결국 어느 규칙도 중요하지 않게 됩니다. 낡은 규칙과 서로 모순되는 규칙이 남고, 단일 사건 때문에 추가한 지나치게 구체적인 규칙이 계속 context를 차지합니다. 개선을 시도하다가 context pollution을 만든 것이며, LP-1과 LP-4 위반입니다.

**교정**: 네 줄을 판정 절차에 각각 통과시킵니다.

| 원래 문장 | 판정 절차 | 정본 자리 | `preferred_enforcement` |
| --- | --- | --- | --- |
| Controller에서 Repository를 직접 사용하지 않는다 | 2번 | architecture rule | `arch-rule` |
| Entity를 Controller에 반환하지 않는다 | 2번 | architecture rule | `arch-rule` |
| 모든 API에는 Integration Test를 작성한다 | 3번 | verify 단계와 hook | `hook` |
| 시간 값은 표준 시각 타입(UTC 기준)만 사용한다 | 2번 | lint rule | `lint` |

네 줄 모두 전역 지시에서 제거하고, AGENTS.md에는 검증이 어디에 있고 실패했을 때 무엇을 읽어야 하는지만 남깁니다. 전역 지시의 총량 관리는 [context-hygiene.rule.md](context-hygiene.rule.md) 가 이어받습니다.

두 예시의 "architecture rule", "lint rule" 이 실제로 어떤 도구인지는 언어와 kind 에 따라 다릅니다. Java 백엔드(ArchUnit, Checkstyle)는 [../language/java/backend/examples.md](../language/java/backend/examples.md), TypeScript 프론트엔드(dependency-cruiser, ESLint)는 [../language/typescript/frontend/examples.md](../language/typescript/frontend/examples.md), TypeScript 백엔드는 [../language/typescript/backend/examples.md](../language/typescript/backend/examples.md), Python 백엔드(import-linter, ruff)는 [../language/python/backend/examples.md](../language/python/backend/examples.md) 가 같은 사건을 그 스택의 이름으로 보여 줍니다. **이 프로젝트에서 감지된 스택의 것 하나만 읽습니다.**

## 관련 문서

- [RULES.md](RULES.md)
- [context-hygiene.rule.md](context-hygiene.rule.md)
- [promotion-gate.rule.md](promotion-gate.rule.md)
- [harness-change-control.rule.md](harness-change-control.rule.md)
- [harness-gc.rule.md](harness-gc.rule.md)
- [../references/lesson-placement.md](../references/lesson-placement.md)
- [../references/harness-elements.md](../references/harness-elements.md)
- [../improvement-log/schema.md](../improvement-log/schema.md)
