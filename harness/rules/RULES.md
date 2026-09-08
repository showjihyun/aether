# 하네스 규칙 인덱스 (RULES)

이 문서는 `harness/rules/` 의 규칙 문서 전체를 찾아가는 입구입니다. 어떤 규칙 문서를 읽어야 할지 모를 때, 두 규칙이 서로 다른 결론을 낼 때, 새 규칙을 추가하기 전에 이미 있는 규칙과 겹치는지 확인할 때 이 문서를 먼저 읽습니다. 개별 판정 기준은 여기에 두지 않고 각 규칙 문서에 둡니다. 이 문서는 목록과 우선순위, 그리고 규칙의 수명만 규정합니다.

## 규칙 문서 목록

각 규칙 문서는 자기 prefix의 ID만 발급합니다. ID는 `PREFIX-숫자` 형식이며 문서 안에서 연속 번호입니다. 다른 문서의 prefix로 ID를 발급하지 않습니다.

| prefix | 문서 | 한 줄 요약 |
| --- | --- | --- |
| LP | [lesson-placement.rule.md](lesson-placement.rule.md) | 얻은 lesson을 test·lint·arch rule·hook·skill·subagent·script·doc·instruction 중 어디에 정본으로 둘지 결정합니다. |
| PG | [promotion-gate.rule.md](promotion-gate.rule.md) | improvement candidate를 promoted 상태로 올릴 때 통과해야 하는 게이트를 정합니다. |
| UT | [untrusted-experience.rule.md](untrusted-experience.rule.md) | issue·log·web·사용자 입력 같은 untrusted experience가 검증 없이 memory와 전역 지시로 흘러들지 않게 막습니다. |
| LB | [loop-budget.rule.md](loop-budget.rule.md) | 반복 예산과 종료 조건을 정해 loop가 무한히 돌지 않게 합니다. |
| EI | [evaluation-integrity.rule.md](evaluation-integrity.rule.md) | 평가 지표를 목표로 삼아 평가 자체를 조작하는 것을 금지합니다. |
| CC | [harness-change-control.rule.md](harness-change-control.rule.md) | 하네스 변경을 한 번에 하나씩 적용하고 변경마다 회귀 검증을 요구합니다. |
| CX | [context-hygiene.rule.md](context-hygiene.rule.md) | AGENTS.md·CLAUDE.md 가 지도 역할을 유지하도록 길이와 내용을 통제합니다. |
| GC | [harness-gc.rule.md](harness-gc.rule.md) | 낡거나 중복된 규칙·문서·skill을 주기적으로 제거합니다. |

## 규칙 충돌 시 우선순위

두 규칙이 같은 상황에서 서로 다른 행동을 요구하면 다음 순서로 판정합니다. 앞선 prefix가 뒤의 prefix를 이깁니다. 우선순위가 낮은 규칙을 어기게 되는 경우, 그 사실과 근거를 improvement log의 `evidence` 에 남깁니다.

| 순위 | prefix | 이 순위인 이유 |
| --- | --- | --- |
| 1 | UT | 오염된 학습을 막는 것이 최우선입니다. 잘못 학습한 지식은 이후의 모든 판단을 오염시키므로 다른 어떤 규칙보다 먼저 적용합니다. |
| 2 | EI | 평가를 지키지 못하면 나머지 판단이 무의미합니다. 평가가 조작되면 개선 여부 자체를 확인할 수 없습니다. |
| 3 | LB | 무한 반복을 막습니다. 종료하지 않는 loop는 예산과 사람의 검토 기회를 모두 소진합니다. |
| 4 | PG | 검증되지 않은 lesson이 정본 지식으로 올라가는 것을 막습니다. |
| 5 | CC | 변경을 한 번에 하나씩 적용해 원인 추적 가능성을 지킵니다. |
| 6 | LP | lesson의 정본 위치를 정합니다. |
| 7 | CX | 진입점 문서의 비대화를 막습니다. |
| 8 | GC | 낡은 자산을 제거합니다. 제거는 언제나 마지막에 판단합니다. |

우선순위 적용의 구체적 형태는 다음과 같습니다.

- UT는 다른 모든 규칙의 입력을 제한합니다. untrusted 출처에서 온 lesson은 LP가 좋은 자리를 찾아냈더라도 PG를 통과하기 전에는 정본 위치에 기록하지 않습니다.
- EI와 LB가 충돌하면, 예산이 남았더라도 평가를 약화시키는 방향의 재시도는 하지 않습니다. 반복을 중단하고 실패로 보고합니다.
- LP와 CX가 충돌하면, 즉 LP가 전역 지시를 적절한 자리로 지목했으나 CX의 길이 상한을 넘게 되면, 전역 지시를 추가하지 않고 문서 또는 결정론적 검증으로 자리를 바꿉니다.
- GC가 다른 규칙이 근거로 삼는 문서를 삭제 대상으로 지목하면, 삭제보다 해당 규칙의 갱신이 먼저입니다.

## 규칙의 수명

규칙은 영구 자산이 아닙니다. 모든 규칙은 다음을 갖추어야 합니다.

- **소유자(owner)**: 규칙의 유효성을 판단할 책임자 한 명 또는 한 역할입니다. 소유자가 없는 규칙은 추가하지 않습니다.
- **만료 또는 재검토 조건(expires)**: `YYYY-MM-DD` 날짜이거나, 날짜 대신 재검토를 촉발하는 조건입니다. 조건은 검증 가능해야 합니다. 예를 들어 "해당 모듈이 제거되면", "이 lint rule이 6개월간 한 번도 위반되지 않으면" 처럼 씁니다. 만료를 두지 않으려면 `none` 을 명시하고 그 이유를 남깁니다.
- **근거(evidence)**: 규칙을 만들게 한 실패 사례입니다. improvement log의 항목 ID로 가리킵니다.

소유자와 만료 조건은 규칙 문서의 각 ID 행에 직접 쓰지 않고 improvement log 항목의 `owner`, `expires` 키에 둡니다. 규칙 ID와 improvement log 항목은 1:N으로 연결됩니다.

재검토를 실제로 수행하는 주체는 GC 규칙입니다. 규칙 소유자는 판단의 책임자이고, 만료·중복·모순을 주기적으로 찾아내 소유자에게 판단을 요구하는 절차는 [harness-gc.rule.md](harness-gc.rule.md) 가 정의합니다. 따라서 규칙을 추가하는 사람은 그 규칙이 언젠가 GC의 검토 대상이 된다는 전제로 만료 조건을 적습니다.

## 관련 문서

- [../references/lesson-placement.md](../references/lesson-placement.md)
- [../references/harness-elements.md](../references/harness-elements.md)
- [../improvement-log/schema.md](../improvement-log/schema.md)
- [../HARNESS.md](../HARNESS.md)
