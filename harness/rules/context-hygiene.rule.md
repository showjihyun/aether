# 컨텍스트 위생 규칙 (CX)

이 문서는 AGENTS.md·CLAUDE.md 같은 진입점 문서가 비대해지는 것을 막습니다. 전역 지시를 추가하려 할 때, 진입점 문서를 편집하기 직전에, 그리고 문서가 길어져 에이전트가 규칙을 놓치기 시작했다고 의심될 때 읽습니다. lesson을 어느 요소에 둘지 고르는 판정은 [lesson-placement.rule.md](lesson-placement.rule.md) 가 담당하고, 이 문서는 그중 진입점 문서로 들어오는 몫의 총량과 형태를 통제합니다.

## 규칙

| ID | 규칙 |
| --- | --- |
| **CX-1** | AGENTS.md·CLAUDE.md 는 모든 지식을 담는 백과사전이 아니라 프로젝트를 탐색하기 위한 지도입니다. 진입점 문서는 무엇을 어디서 읽고, 무엇을 실행하고, 실패했을 때 어디로 가는지만 알려줍니다. 설명해야 할 내용이 생기면 문서를 만들고 진입점에서는 링크만 둡니다. |
| **CX-2** | 진입점 문서 본문은 120줄, 전역 지시 항목은 20개를 넘지 않습니다. 초과하면 새 항목을 추가하기 전에 초과분을 먼저 해소합니다. 해소 방법은 결정론적 검증으로 승격, 상세 문서로 이관, 낡은 항목 삭제 중 하나이며 요약만 해서 줄 수를 줄이지 않습니다. |
| **CX-3** | 단일 사건에서 나온 지나치게 구체적인 규칙은 전역 지시로 승격하지 않습니다. 관측 1회짜리 사건은 improvement log에 `candidate` 로 남기고, 재발이 확인된 뒤에 배치를 다시 판정합니다. 특정 파일·특정 함수 이름이 등장하는 지시는 전역 지시의 후보가 아닙니다. |
| **CX-4** | 상충하는 규칙을 동시에 남기지 않습니다. 새 지시가 기존 지시와 다른 행동을 요구하면 둘 중 하나를 삭제하거나, 두 지시가 각각 적용되는 조건을 명시해 하나의 항목으로 합칩니다. 나중에 쓴 규칙이 자동으로 이긴다고 가정하지 않습니다. |
| **CX-5** | 모든 전역 지시는 소유자와 재검토 조건을 가집니다. 근거가 된 improvement log 항목 ID로 연결하며, `owner` 와 `expires` 가 없는 항목은 추가하지 않습니다. 이미 들어 있는데 연결이 없는 항목은 GC의 삭제 후보입니다. |
| **CX-6** | 규칙을 추가할 때는 기존 규칙 중 대체·삭제할 대상을 함께 판정합니다. 추가만 하는 편집은 받지 않으며, 삭제할 것이 없다는 결론이라도 그 판단을 improvement log에 남깁니다. |

## 판정 절차

진입점 문서를 편집하려 할 때마다 아래 순서로 판정합니다. 어느 한 단계에서 중단 조건에 걸리면 편집하지 않고 되돌아갑니다.

1. **이 내용이 정말 진입점 문서의 몫인지 확인합니다.** [lesson-placement.rule.md](lesson-placement.rule.md) 의 판정 절차를 먼저 실행하고, 8번(전역 원칙)에 도달했을 때만 다음 단계로 갑니다. 그 앞 단계에서 멈췄다면 편집하지 않습니다.
2. **적용 범위를 확인합니다.** 특정 모듈·특정 파일·특정 사건에만 해당하면 전역 지시가 아닙니다(CX-3). improvement log에 남기고 종료합니다.
3. **관측 횟수를 확인합니다.** 1회 관측이면 `candidate` 로 두고 종료합니다(CX-3). 2회 이상이면 계속 진행합니다.
4. **기존 항목과 대조합니다.** 같은 취지의 항목이 있으면 새로 추가하지 않고 기존 항목을 고칩니다. 다른 행동을 요구하는 항목이 있으면 하나로 합치거나 하나를 삭제합니다(CX-4).
5. **대체·삭제 대상을 정합니다.** 이번 추가로 불필요해지는 기존 항목을 지목합니다. 없다면 없다는 판단을 근거와 함께 남깁니다(CX-6).
6. **소유자와 재검토 조건을 붙입니다.** improvement log 항목의 `owner`, `expires` 를 채우고 항목 ID를 지시문에 연결합니다(CX-5).
7. **상한을 확인합니다.** 편집 결과가 본문 120줄 또는 지시 항목 20개를 넘으면 넘긴 만큼을 먼저 해소합니다(CX-2). 해소 순서는 결정론적 검증으로 승격할 수 있는 항목, 상세 문서로 옮길 수 있는 항목, 만료된 항목 순입니다.
8. **편집 후 형태를 확인합니다.** 남은 문장이 "무엇을 읽어라 / 무엇을 실행해라 / 실패하면 어디로 가라" 의 형태인지 봅니다. 배경 설명이나 예외 조건이 본문에 남아 있으면 문서로 옮깁니다(CX-1).

상한 초과가 반복적으로 발생하면 그 자체를 하나의 improvement candidate로 기록합니다. 진입점 문서가 계속 넘친다는 것은 결정론적 검증이 부족하다는 신호입니다.

## 위반 예시와 교정

### 예시 1 — 수백 줄로 비대해진 AGENTS.md 를 지도형으로 되돌리기

**위반 (before)**: 실패가 생길 때마다 한 줄씩 추가한 결과, 진입점 문서가 규칙 목록이 되었습니다.

```markdown
# AGENTS.md

## Rules

- Controller에서 Repository를 직접 사용하지 않는다.
- Entity를 API 응답으로 그대로 반환하지 않는다.
- 모든 API에는 Integration Test를 작성한다.
- 시간 값은 표준 시각 타입(UTC 기준)만 사용한다.
- 로컬 시각 타입도 쓰지 말 것. (2026-03 결제 모듈 버그 때문)
- UserService.updateProfile 은 반드시 트랜잭션 안에서 호출한다.
- 단, 배치 작업에서는 트랜잭션 없이 호출해도 된다.
- 테스트가 느리면 앱 전체를 띄우는 테스트 대신 슬라이스 테스트를 쓴다.
- 급할 때는 슬라이스 테스트도 생략 가능.
- ... (이하 200줄)
```

이 문서에는 네 가지 문제가 동시에 있습니다. 결정론적으로 검증 가능한 항목이 지시문으로 남아 있고(CX-1), 단일 사건에서 나온 항목이 전역 지시가 되었으며(CX-3), 트랜잭션과 테스트 항목은 바로 다음 줄과 상충하고(CX-4), 어느 항목에도 소유자와 만료 조건이 없습니다(CX-5).

**교정 (after)**: 판정 절차를 항목별로 실행해 자리를 옮기고, 진입점 문서는 지도로 되돌립니다.

```markdown
# Repository Guide

## Architecture

Read:
- docs/architecture/index.md
- docs/engineering/principles.md

계층 규칙과 시간 타입 규칙은 architecture rule과 lint rule이 정본입니다.
위반은 ./scripts/verify.sh 가 잡습니다.

## Verification

Before declaring a task complete:

1. Run ./scripts/verify.sh
2. Fix failures before stopping
3. Never weaken tests to make them pass

## Learning

If a recurring failure is discovered:

- record an improvement candidate
- prefer tests, lint rules or tools over global instructions
- do not promote an unverified lesson
```

옮긴 결과는 다음과 같습니다.

| before 항목 | 조치 | 이후 정본 위치 |
| --- | --- | --- |
| Controller → Repository 직접 호출 금지 | 결정론적 검증으로 승격 | architecture rule |
| Entity 반환 금지 | 결정론적 검증으로 승격 | architecture rule |
| Integration Test 필수 | verify 단계와 hook로 강제 | `scripts/verify.sh`, `hooks/` |
| 시간 타입 규칙 | lint rule로 승격 | lint 설정 |
| 특정 결제 모듈 버그 대응 | 단일 사건이므로 전역 지시에서 제거 | 회귀 테스트 + improvement log |
| `UserService.updateProfile` 트랜잭션 | 특정 함수 지시이므로 제거 | 설계 문서 |
| 트랜잭션 예외 조건 | 상충 항목을 조건과 함께 하나로 통합 | 설계 문서 |
| 테스트 생략 허용 | 검증 약화를 허용하므로 삭제 | 삭제 |

같은 사례를 실제 스택의 어노테이션·도구 이름으로 적은 판은 언어 팩에 있습니다. Java/Spring 은 [../language/java/backend/examples.md](../language/java/backend/examples.md) 2절, TypeScript 프론트엔드는 [../language/typescript/frontend/examples.md](../language/typescript/frontend/examples.md) 2절, TypeScript 백엔드는 [../language/typescript/backend/examples.md](../language/typescript/backend/examples.md) 2절, Python 은 [../language/python/backend/examples.md](../language/python/backend/examples.md) 2절입니다. **이 프로젝트에서 감지된 스택의 것 하나만 읽습니다.**

### 예시 2 — 상충하는 규칙을 나란히 남긴 편집

**위반**: 리뷰에서 "커밋 전에 전체 테스트를 돌려라"라는 지시가 추가되었는데, 문서 앞부분에는 "느린 테스트는 CI에 맡기고 로컬에서는 변경 범위만 검증한다"가 이미 있었습니다. 두 문장이 모두 남아 에이전트가 상황마다 다르게 행동했고, 어느 쪽이 맞는지 판단할 근거가 문서에 없습니다. CX-4와 CX-6 위반입니다.

**교정**: 판정 절차 4번에서 두 항목을 하나로 합치고, 적용 조건을 명시합니다. 그리고 이 결정을 검증으로 옮겨 지시문 의존을 없앱니다.

```markdown
## Verification

Before declaring a task complete:

1. Run ./scripts/verify.sh (변경 범위 기준으로 단계를 선택합니다)
2. Fix failures before stopping
```

전체 테스트를 언제 도는지는 `scripts/verify.sh` 와 CI 설정이 정본이 되고, 진입점 문서에는 실행 명령 한 줄만 남습니다. 제거한 두 항목과 그 근거는 improvement log 항목에 `owner`, `expires` 와 함께 기록합니다.

## 관련 문서

- [RULES.md](RULES.md)
- [lesson-placement.rule.md](lesson-placement.rule.md)
- [harness-gc.rule.md](harness-gc.rule.md)
- [untrusted-experience.rule.md](untrusted-experience.rule.md)
- [../templates/AGENTS.md](../templates/AGENTS.md)
- [../templates/CLAUDE.md](../templates/CLAUDE.md)
- [../references/lesson-placement.md](../references/lesson-placement.md)
