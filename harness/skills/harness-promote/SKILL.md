---
name: harness-promote
description: improvement candidate 하나를 일반화하고 후보 하네스로 적용한 뒤 대표 task 와 held-out task 로 평가해 승격 또는 기각을 판정하는 스킬입니다. improvement-log 에 candidate 가 쌓였을 때, 새 규칙·스킬·훅·테스트를 하네스에 반영할지 결정해야 할 때, 하네스 변경이 회귀를 일으키지 않는지 확인해야 할 때 사용합니다. 회고로 candidate 를 만드는 작업은 harness-retro 가, 지금 작업을 통과시키는 반복은 harness-verify 가 담당합니다.
metadata:
  short-description: candidate 검증과 승격·기각 판정
---

# Harness Promote

이 스킬은 검증되지 않은 후보 지식을 하네스의 신뢰 영역으로 들일지 결정할 때 읽습니다. candidate 는 사건 하나에서 나온 가설이며, 그대로 적용하면 이번 문제에만 과적합된 규칙이 남을 수 있습니다. 이 스킬은 그 가설을 규칙 형태로 일반화하고 실제 평가로 검증한 뒤에만 통과시킵니다. 승격 기준은 [../../rules/promotion-gate.rule.md](../../rules/promotion-gate.rule.md), 변경 통제는 [../../rules/harness-change-control.rule.md](../../rules/harness-change-control.rule.md) 를 따릅니다.

## 절차

### 1. candidate 선택

`improvement-log/` 에서 `status: candidate` 인 항목을 나열하고 하나만 고릅니다.

```bash
harness/scripts/improvement-log.sh --help
harness/scripts/improvement-log.sh list --status candidate
```

선택 우선순위는 다음과 같습니다.

1. `recurrence_risk: high`
2. `preferred_enforcement` 가 결정적 수단(`test`, `lint`, `arch-rule`, `hook`)인 것
3. `evidence` 가 실행 로그로 남아 있는 것

**이 절차 전체에서 다루는 candidate 는 하나입니다.** 여러 candidate 를 묶어 한 번에 적용하면 어떤 변경이 점수를 움직였는지 알 수 없게 되며, 이는 [../../rules/harness-change-control.rule.md](../../rules/harness-change-control.rule.md) 위반입니다.

선택한 candidate 의 `status` 를 `validating` 으로 바꾸고 시작합니다. 전이는 스크립트로 수행하고, 전이 후 검증을 다시 실행합니다. 다른 키는 이 단계에서 건드리지 않습니다.

```bash
harness/scripts/improvement-log.sh set-status 2026-08-09-001 validating
harness/scripts/improvement-log.sh validate improvement-log/2026-08-09-001.yaml
```

스크립트가 거부하는 전이를 다른 값으로 우회해 만들지 않습니다. 허용 전이는 [../../improvement-log/schema.md](../../improvement-log/schema.md) 6절이 정본입니다.

### 2. 일반화

단일 사건 서술을 규칙 형태로 바꿉니다. 사건 고유의 클래스명·파일명·티켓 번호는 규칙 문장에서 제거하고 `evidence` 에만 남깁니다.

| 사건 서술 | 규칙 형태 |
| --- | --- |
| "OrderController 가 OrderRepository 구현체를 직접 호출했습니다." | "controller 계층은 repository 계층에 의존하지 않습니다." |
| "이번 장애가 비동기 처리에서 발생했습니다." | 과잉 일반화입니다. "비동기 처리를 금지한다"로 확장하지 않습니다. |

일반화 검사 세 가지를 모두 통과해야 다음 단계로 갑니다.

- **적용 범위**: 이 규칙이 적용되는 경우를 두 건 이상 실제 코드에서 지목할 수 있습니까.
- **반례**: 이 규칙 때문에 정당한 구현이 막히는 경우를 찾아보았습니까. 찾았다면 예외 조건을 규칙에 포함시킵니다.
- **판정 가능성**: 위반 여부를 사람이 해석하지 않고 판별할 수 있습니까.

세 검사 중 하나라도 통과하지 못하면 규칙을 좁히거나 `preferred_enforcement` 를 `doc` 으로 낮춥니다.

### 3. 강제 수단 결정

`preferred_enforcement` 를 확정합니다. candidate 에 적힌 값은 제안이며, 일반화 결과에 따라 바꿀 수 있습니다. 결정적으로 강제할 수 있으면 항상 그쪽을 고릅니다. 자연어 지시(`instruction`)는 다른 수단이 모두 불가능할 때만 선택합니다.

바꾼 경우 그 이유를 `proposed_harness_change` 본문에 덧붙입니다.

### 4. 후보 하네스 적용

확정한 수단 하나만 적용합니다. 같은 회차에 문서와 규칙과 스킬을 동시에 바꾸지 않습니다.

적용 전에 기준선 점수를 먼저 기록합니다.

```bash
harness/scripts/eval.sh
cp .harness/latest-eval.json .harness/baseline-eval.json
```

기준선 `score` 와 `layers[].score` 를 계층별로 적어 둡니다. 기준선 없이 적용한 변경은 판정할 수 없습니다.

### 5. 대표 task 평가

이 단계의 근거는 **두 갈래**이고 서로 대체하지 않습니다. `eval.sh` 는 task 를 실행하지 않습니다.

#### 5.1 하네스 무결성 회귀

아래 명령이 답하는 질문은 "후보 하네스를 적용한 뒤에도 하네스 자신이 성립하는가" 하나입니다. 대표 task 의 합격 여부는 이 산출에 들어 있지 않습니다.

```bash
harness/scripts/eval.sh
cat .harness/latest-eval.json
```

결과에서 다음을 기록합니다.

| 항목 | 위치 |
| --- | --- |
| 총점 | `.harness/latest-eval.json` 의 `score` |
| 임계값 통과 | `threshold`, `pass`, `failed_required` |
| 계층별 점수 | `layers[].layer` 와 `layers[].score` |
| 가장 큰 실패 | `largest_failure` |

계층별 점수는 `correctness`, `architecture`, `quality`, `behavior`, `performance`, `subjective` 여섯 개를 모두 적습니다. 총점만 기록하지 않습니다. 총점이 올라도 특정 계층이 내려갔다면 그것이 판정 근거입니다.

#### 5.2 대표 task 실행

task 목록은 [../../evaluation/tasks/representative.md](../../evaluation/tasks/representative.md) 입니다. 각 task 는 **하네스를 처음 만나는 새 세션**에서 실행하고, 결과를 task 한 건당 한 파일로 [../../evaluation/runs/](../../evaluation/runs/) 에 남깁니다. 형식은 [../../evaluation/runs/_template.md](../../evaluation/runs/_template.md) 입니다.

실행하지 않은 task 는 `not-run` 으로 기록합니다. 5.1 의 점수로 대신하지 않습니다. 실행하지 않은 task 를 통과로 적는 것이 이 절차가 막으려는 실패입니다.

### 6. held-out task 평가

대표 task 만으로는 과적합을 걸러내지 못합니다. candidate 작성 시점에 보지 않은 task 로 다시 평가합니다. 목록은 [../../evaluation/tasks/held-out.md](../../evaluation/tasks/held-out.md) 를 따릅니다.

held-out task 를 candidate 에 맞춰 고르거나 수정하지 않습니다. held-out 을 조정하는 순간 이 게이트는 무효가 됩니다.

대표 task 와 같은 방식으로 실행하고 결과를 [../../evaluation/runs/](../../evaluation/runs/) 에 남깁니다. held-out 은 승격 판정 시점에 1회만 실행합니다.

임계값 통과 여부는 스크립트로 판정합니다.

```bash
harness/scripts/pass-threshold.sh
```

### 7. 회귀 판정

기준선(`.harness/baseline-eval.json`)과 비교해 회귀 여부를 판정합니다. 판정 신호표의 정본은 [../../evaluation/rubric.md](../../evaluation/rubric.md) 4절이며, 총점 하락·계층 점수 하락·held-out 총점 하락·기존 필수 단계 실패 중 하나라도 있으면 회귀이고, 점수 변화가 없으면 개선 근거가 없는 것으로 봅니다. 표의 각 행을 그대로 확인한 뒤 결과를 기록합니다.

기준선 72 에서 후보 A 가 75, 후보 B 가 73, 후보 C 가 81 이라면 B 는 기각하고 A 와 C 만 남기는 방식입니다. 개선은 이런 방식으로 한 번에 한 단계씩 쌓습니다.

### 8. promote 또는 reject

| 조건 | 판정 |
| --- | --- |
| 대표·held-out 양쪽에서 회귀 없음, 총점 상승 | `promoted` |
| 회귀 발생 | `rejected`, 적용한 변경을 되돌립니다 |
| 개선 근거 없음 | `rejected` 또는 `candidate` 로 되돌려 재설계 |
| 보안 민감 영역 변경 | 사람 검토 전까지 `validating` 유지 |
| 대표 또는 held-out task 에 `not-run` 이 남아 있음 | `validating` 유지. PG-3 미충족이며 `eval.sh` 점수로 대신하지 않습니다 |

기각한 변경은 반드시 되돌립니다. "점수는 안 올랐지만 나쁘지 않으니 남긴다"는 판정을 하지 않습니다. 그 축적이 Self-Drift 입니다.

### 9. improvement log status 갱신

선택한 candidate 의 `status` 를 판정 결과로 갱신합니다. 승격한 경우에만 `trust` 를 `validated` 로 올립니다. 기각한 경우 `trust` 는 `untrusted` 로 둡니다.

`expires` 를 다시 확인합니다. 승격했더라도 한시적으로만 유효한 규칙이면 만료일을 남깁니다. 만료된 규칙 처리는 harness-gardener 스킬이 담당합니다.

### 10. 근거 기록

판정을 뒷받침하는 수치를 candidate 파일의 `regression_check` 에 확정 결과로 적습니다.

```text
baseline score 72 (correctness 80 / architecture 60 / quality 75 / behavior 70 / performance 70 / subjective 70)
representative 81 (correctness 85 / architecture 95 / quality 75 / behavior 72 / performance 70 / subjective 72)
held-out 79 (회귀 없음)
task 실행 기록: evaluation/runs/2026-08-09-REP-1.md pass, evaluation/runs/2026-08-09-HLD-2.md pass
판정: promoted
```

수치를 남기지 않은 승격은 승격으로 인정하지 않습니다.

## 완료 조건

- 이 회차에서 적용한 하네스 변경이 정확히 하나임을 확인했습니다.
- 기준선, 대표 task, held-out task 세 시점의 총점과 여섯 계층 점수를 모두 기록했습니다.
- 실제로 실행한 명령어(`harness/scripts/eval.sh`, `harness/scripts/pass-threshold.sh`)와 `.harness/latest-eval.json` 값을 근거로 제시했습니다.
- 판정이 `promoted` 또는 `rejected` 로 확정되었고, 기각이면 변경을 되돌린 사실을 확인했습니다.
- 해당 candidate 의 `status` 와 `trust` 가 판정과 일치합니다.
- 일반화 검사 세 가지의 결과를 서술했습니다.

## 하지 않는 것

- 한 회차에 두 개 이상의 하네스 변경을 적용하지 않습니다.
- held-out task 를 후보에 맞춰 선택·수정·삭제하지 않습니다.
- 임계값을 낮추거나 계층 가중치를 조정해 통과시키지 않습니다.
- 총점 하나만 보고 승격하지 않습니다. 계층별 점수를 함께 판정합니다.
- 회귀가 확인된 변경을 남기지 않습니다.
- 사건 문장을 그대로 규칙으로 옮기지 않고, 반대로 사건 범위를 넘어서는 금지 규칙으로 확장하지도 않습니다.
- 기준선 측정 없이 적용하지 않습니다.

## 관련 문서

- [../../rules/promotion-gate.rule.md](../../rules/promotion-gate.rule.md)
- [../../rules/harness-change-control.rule.md](../../rules/harness-change-control.rule.md)
- [../../rules/evaluation-integrity.rule.md](../../rules/evaluation-integrity.rule.md)
- [../../evaluation/tasks/representative.md](../../evaluation/tasks/representative.md)
- [../../evaluation/tasks/held-out.md](../../evaluation/tasks/held-out.md)
- [../../evaluation/rubric.md](../../evaluation/rubric.md)
- [../../improvement-log/schema.md](../../improvement-log/schema.md)
