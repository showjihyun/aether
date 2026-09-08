# 하네스 청소 규칙 (GC)

하네스에서 무언가를 **덜어낼지** 판단할 때 이 문서를 읽습니다. 정기 청소 라운드를 시작할 때, 규칙·문서·skill·hook 의 `expires` 가 도달했을 때, 그리고 새 요소를 추가하려다 이미 겹치는 요소를 발견했을 때가 해당 시점입니다. 추가 판정은 [promotion-gate.rule.md](promotion-gate.rule.md) 가, 변경 단위와 되돌리기는 [harness-change-control.rule.md](harness-change-control.rule.md) 가 정하고, 이 문서는 제거 판정만 다룹니다.

## 규칙

| ID | 규칙 |
| --- | --- |
| **GC-1** | 하네스는 추가만으로는 유지되지 않습니다. 규칙은 낡고, 문서는 코드와 어긋나고, skill 은 서로 겹칩니다. 청소는 선택 작업이 아니라 정기 라운드로 수행합니다. |
| **GC-2** | 모든 규칙·문서·skill·hook 은 재검토 주기를 가집니다. 각 요소에는 소유자와 재검토 시점이 있어야 하며, 재검토 시점이 없는 요소는 추가하지 않습니다. |
| **GC-3** | 만료된 workaround 와 코드와 어긋난 문서는 제거합니다. 근거가 된 조건이 코드에서 사라졌는데도 남아 있는 규칙은 유지 대상이 아니라 제거 대상입니다. |
| **GC-4** | 겹치는 skill 은 통합하거나 경계를 다시 긋습니다. 같은 상황에서 두 skill 이 함께 호출된다면 하나로 합치거나, 각 skill 의 진입 조건을 서로 배타적으로 다시 씁니다. |
| **GC-5** | 제거도 변경이므로 CC 규칙의 회귀 검증을 거칩니다. 제거는 한 번에 하나씩 적용하고, 대표 task 와 held-out task 에서 회귀가 없을 때만 확정합니다. |
| **GC-6** | 제거 판정 근거를 improvement log 에 남깁니다. 제거한 항목은 `status: expired` 로 종결하고, 제거 사유와 회귀 검증 결과를 함께 기록합니다. |
| **GC-7** | 제거 대신 강화가 맞는 경우에는 결정적 시행을 우선합니다. 반복해서 어겨지는 문서 지침은 삭제하거나 방치하지 말고 test, lint, arch-rule, hook 중 하나로 옮깁니다. |

## 판정 절차

1. 청소 라운드를 엽니다. 아래 탐지 신호 표의 여섯 가지 신호를 모두 수집합니다.
2. 신호에서 반복되는 문제를 식별합니다. 1회성 사건은 청소 대상이 아니라 새 improvement log 후보입니다.
3. 각 대상에 대해 제거·통합·강화·유지 중 하나를 판정합니다. 판정 기준은 표의 마지막 열을 따릅니다.
4. 판정이 제거 또는 통합이면 변경을 하나만 적용합니다(GC-5, [harness-change-control.rule.md](harness-change-control.rule.md)).
5. 평가를 실행해 대표 task 와 held-out task 에서 회귀가 없는지 확인합니다. 회귀가 있으면 제거를 되돌리고 유지로 판정합니다.
6. 확정된 제거는 improvement log 에 `status: expired` 로 기록합니다(GC-6).
7. 남긴 요소에는 다음 재검토 시점을 다시 채웁니다(GC-2).

### 탐지 신호와 판정 대상

| 신호 | 관찰 위치 | 판정 대상 | 이 신호에서 판정하는 내용 |
| --- | --- | --- | --- |
| 실패한 CI 실행 | CI 실행 이력, `.harness/verify.json` 의 `steps[].status` | 검증 단계, hook | 항상 실패하거나 항상 무시되는 단계인지 판정합니다. 무시되는 단계는 제거하거나 `required: true` 로 승격합니다. |
| 최근 사용자 교정 | 세션 기록, 리뷰 요청 사유 | 문서, 지침 | 사람이 반복해서 같은 방향을 다시 잡아 준다면 해당 문서가 코드와 어긋났거나 발견되지 않는 위치에 있다고 판정합니다. |
| 반복 테스트 실패 | 테스트 실행 로그, `.harness/logs/` | 테스트, 아키텍처 규칙 | 규칙이 과도해 정상 구현을 막는지, 아니면 규칙은 옳고 구현이 반복 위반하는지 판정합니다. 전자는 제거·완화, 후자는 오류 메시지 강화 대상입니다. |
| 에이전트 재시도 | `.harness/loop-state.json` 의 반복 기록 | skill, 지침 | 같은 지점에서 반복 재시도가 발생하면 지침이 모호하거나 skill 경계가 겹친다고 판정합니다. GC-4 의 통합·재분할 대상입니다. |
| 코드 리뷰 코멘트 | PR 리뷰 코멘트 | 규칙, 문서 | 사람이 매번 손으로 지적하는 항목을 판정합니다. 반복 지적은 문서 보강이 아니라 결정적 시행으로 옮길 후보입니다(GC-7). |
| improvement log | `improvement-log/` 의 항목 | 승격된 모든 요소 | `expires` 도달 항목, `promoted` 이후 한 번도 근거가 관측되지 않은 항목, 서로 중복된 항목을 판정합니다. 근거가 사라졌으면 `expired` 로 종결합니다. |

## 위반 예시와 교정

### 예시 1 — 만료된 workaround 가 영구 규칙으로 남은 경우

특정 라이브러리 버전의 결함을 피하려고 추가한 지침이 문서에 남아 있습니다. 해당 의존성은 이미 교체되었지만 지침은 그대로이고, 에이전트는 존재하지 않는 제약을 지키느라 우회 구현을 만듭니다. GC-3 위반입니다.

교정: 근거가 사라졌음을 확인하고 지침을 제거합니다. 제거 후 평가를 실행해 회귀가 없는지 확인하고, improvement log 를 종결합니다. 아래는 그 항목의 발췌이며, 실제 파일은 [../improvement-log/schema.md](../improvement-log/schema.md) 의 15개 키를 순서대로 모두 채웁니다.

```yaml
id: 2026-08-09-014
status: expired
symptom: 교체된 의존성의 결함을 피하는 지침이 남아 우회 구현이 생성되었습니다.
evidence: 해당 의존성은 현재 매니페스트에 존재하지 않습니다.
fix: 지침을 제거했습니다.
regression_check: 대표 task 와 held-out task 에서 계층별 점수 하락이 없었습니다.
expires: none
```

### 예시 2 — 겹치는 skill 을 방치한 경우

`harness-retro` 와 `harness-promote` 가 모두 improvement log 항목을 생성하도록 적혀 있어, 같은 사건에 대해 두 개의 후보가 서로 다른 `id` 로 만들어졌습니다. GC-4 위반입니다.

교정: 경계를 다시 긋습니다. 후보 생성은 한쪽에만 두고, 다른 쪽은 기존 항목의 `status` 전이만 담당하도록 진입 조건을 배타적으로 다시 씁니다. 통합·재분할도 변경이므로 한 번에 하나씩 적용하고 회귀를 확인합니다.

### 예시 3 — 회귀 검증 없이 한꺼번에 제거한 경우

청소 라운드에서 오래된 규칙 다섯 개를 한 커밋으로 모두 삭제했고, 이후 점수가 내려갔지만 어떤 삭제가 원인인지 알 수 없었습니다. GC-5 위반입니다.

교정: 삭제를 되돌리고 한 번에 하나씩 다시 판정합니다. 각 제거마다 평가를 실행하고 `keep`/`reject` 를 기록합니다. 검증 없이 덜어내는 청소는 개선이 아니라 Self-Drift 입니다.

## 관련 문서

- [harness-change-control.rule.md](harness-change-control.rule.md)
- [promotion-gate.rule.md](promotion-gate.rule.md)
- [context-hygiene.rule.md](context-hygiene.rule.md)
- [lesson-placement.rule.md](lesson-placement.rule.md)
- [RULES.md](RULES.md)
- [../skills/harness-gardener/SKILL.md](../skills/harness-gardener/SKILL.md)
- [../improvement-log/schema.md](../improvement-log/schema.md)
- [../references/harness-elements.md](../references/harness-elements.md)
