# 평가 세트 (Evaluation)

이 문서는 하네스 변경을 판정하기 직전에 읽습니다. improvement candidate 를 승격할지 결정할 때, 새 규칙·스킬·훅을 하네스에 반영한 뒤 회귀를 확인할 때, 그리고 평가 task 를 추가하거나 교체하려 할 때가 그 시점입니다. 평가 계층의 정의와 가중치는 [../references/evaluation-layers.md](../references/evaluation-layers.md) 가 소유하고, 이 문서는 **그 계층을 무엇으로 측정할 것인가**, 즉 task 세트의 구성과 운용을 정합니다.

## 1. 평가 세트가 하는 일

Self-Improving Loop 의 중심은 memory 가 아니라 evaluation 입니다. 평가면이 없으면 하네스 변경의 결과를 인상으로 판정하게 되고, 그 순간 Self-Improvement 는 Self-Drift 로 바뀝니다.

평가 세트는 두 가지 질문에 답합니다.

| 질문 | 답하는 수단 |
| --- | --- |
| 이번 하네스 변경이 목표한 문제를 실제로 해결했는가 | 대표 task([tasks/representative.md](tasks/representative.md)) |
| 그 변경이 다른 작업을 나쁘게 만들지 않았는가 | held-out task([tasks/held-out.md](tasks/held-out.md)) |

두 질문 모두 통과할 때만 승격합니다. 판정 규범은 [../rules/promotion-gate.rule.md](../rules/promotion-gate.rule.md) 가 소유합니다.

## 2. 6계층을 다시 확인합니다

평가는 하나의 숫자가 아닙니다. 단일 지표는 반드시 최적화 대상이 되고, 에이전트는 사람이 의도한 목적이 아니라 주어진 평가 함수를 최적화합니다. 그래서 점수는 항상 6개 계층으로 나누어 봅니다. layer 식별자는 고정 계약이며 다른 이름을 쓰지 않습니다.

| layer | 측정 대상 | 이 세트에서의 관측 수단 |
| --- | --- | --- |
| `correctness` | 요구된 동작이 성립하는가 | Unit / Integration / E2E 테스트 |
| `architecture` | 의존 방향과 경계가 지켜지는가 | 아키텍처·의존성 규칙 검사 |
| `quality` | 정적으로 발견 가능한 결함이 없는가 | Lint, 타입 검사, 정적 분석 |
| `behavior` | 실행 중인 시스템이 실제로 동작하는가 | 브라우저·DOM·console·network, API 시나리오 |
| `performance` | 응답 시간·자원 사용이 기준 안인가 | 벤치마크, 부하 측정 |
| `subjective` | 사람이 볼 때 납득 가능한가 | LLM Review, Human Review |

각 계층의 가중치, `.harness/latest-eval.json` 의 해석, deterministic 우선 원칙은 [../references/evaluation-layers.md](../references/evaluation-layers.md) 를 읽습니다. 계층별 점수 산출 방식과 채점 절차는 [rubric.md](rubric.md) 에 있습니다.

`subjective` 는 어떤 경우에도 단독 gate 가 되지 못합니다. `subjective` 점수만으로 승격을 허용하거나 차단하지 않습니다.

## 3. 이 디렉터리의 구성

| 파일 | 내용 | 개선 작업 중 읽어도 되는가 |
| --- | --- | --- |
| [rubric.md](rubric.md) | 계층별 채점 기준, 점수 산출식, LLM 리뷰 루브릭, 결과 기록 형식 | 예 |
| [tasks/representative.md](tasks/representative.md) | 대표 task 6~8건. 회귀 확인의 기준선 | 예 |
| [tasks/held-out.md](tasks/held-out.md) | held-out task 4~6건. 과적합 검출용 | **아니오** |

## 4. 왜 둘로 나누는가

새 규칙이나 스킬은 현재 문제를 잘 해결합니다. 그것만으로는 적용 근거가 되지 않습니다. **현재 task 하나에 지나치게 최적화된 변경**일 수 있기 때문입니다.

장애 하나 때문에 다음 규칙을 만들었다고 합시다.

```text
Never use asynchronous processing.
```

이번 장애는 막힙니다. 그리고 프로젝트 전체는 나빠집니다. 대표 task 만 보면 이 변경은 개선으로 보입니다. 대표 task 는 그 문제를 겨냥해 만들어졌기 때문입니다.

그래서 하네스 변경도 회귀 검증을 거칩니다.

```text
Candidate Harness
 ↓
Current Problem      ← 이번에 고치려던 문제
 ↓
Representative Tasks ← 평소 작업에서 회귀가 없는가
 ↓
Held-out Tasks       ← 후보를 만들 때 보지 않은 작업에서도 회귀가 없는가
 ↓
Regression?          ← 있으면 기각, 없으면 승격
```

대표 task 는 **하네스를 만들 때 보면서 만든** 작업입니다. 따라서 대표 task 점수는 "의도한 개선이 일어났는가"만 증명할 수 있습니다. held-out task 는 후보 설계 시점에 보지 않은 작업이므로, 그 위에서의 점수만이 "일반화되었는가"를 증명합니다. 둘을 합쳐 하나의 세트로 쓰면 두 증명이 섞여 어느 쪽도 성립하지 않습니다.

## 5. held-out 운용 규칙

held-out 세트는 오염되면 즉시 가치를 잃습니다. 다음 규칙을 지킵니다. 상세와 오염 시 교체 절차는 [tasks/held-out.md](tasks/held-out.md) 가 소유합니다.

| 규칙 | 내용 |
| --- | --- |
| 읽지 않습니다 | 개선 작업(후보 설계, 규칙·스킬 작성, 프롬프트 수정) 중에는 held-out 파일을 열지 않습니다. |
| 맞추지 않습니다 | held-out 에서 점수가 낮다는 이유로 하네스를 그 task 에 맞춰 고치지 않습니다. 그것은 개선이 아니라 정답 외우기입니다. |
| 한 번만 실행합니다 | 승격 판정 시점에 1회 실행합니다. 통과할 때까지 반복 실행하지 않습니다. |
| 수정하지 않습니다 | 점수를 올리기 위해 task 의 입력·기대 동작·합격 기준을 바꾸지 않습니다. |
| 오염되면 교체합니다 | 위 규칙이 깨졌다면 그 task 는 폐기하고 새 task 로 교체합니다. 복구하지 않습니다. |

이 규칙을 우회하는 행위는 평가 조작이며 [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) 위반입니다.

## 6. 실행 방법

```bash
# 전체 계층 평가. 결과는 .harness/latest-eval.json 으로 남습니다.
harness/scripts/eval.sh

# 승격 판정 전 기준선을 먼저 고정합니다.
cp .harness/latest-eval.json .harness/baseline-eval.json

# 임계값 통과 여부 판정.
harness/scripts/pass-threshold.sh
```

판정에서는 총점만 보지 않습니다. `score` 와 함께 `layers[].score` 여섯 개를 모두 기록하고, 총점이 올라도 어느 계층이 기준선보다 낮으면 회귀로 판정합니다. 기록 형식은 [rubric.md](rubric.md) 5절을 따릅니다.

## 7. task 추가·교체 절차

평가 세트도 하네스의 일부이므로 변경에 통제가 필요합니다. 한 번에 하나씩 바꿉니다([../rules/harness-change-control.rule.md](../rules/harness-change-control.rule.md)).

### 7.1 대표 task 추가

1. 근거가 되는 improvement log 항목 `id` 를 확인합니다. 근거 없는 task 는 추가하지 않습니다.
2. 기존 대표 task 와 겹치는 실패 모드인지 확인합니다. 겹치면 새로 만들지 않고 기존 task 의 합격 기준을 조입니다.
3. 관측할 계층과 합격 기준을 **기계가 판정 가능한 명제**로 씁니다. "잘 동작한다"는 합격 기준이 아닙니다.
4. 하네스를 바꾸지 않은 상태에서 먼저 실행합니다. 이 시점에 통과해 버리는 task 는 회귀를 검출하지 못하므로 기준을 다시 잡습니다.
5. 다음 연번(`REP-N`)을 부여하고 [tasks/representative.md](tasks/representative.md) 에 추가합니다. 기존 ID 를 재사용하지 않습니다.

### 7.2 held-out task 추가·교체

1. 추가·교체는 **승격 판정 밖에서** 수행합니다. 판정 중에 held-out 을 손대지 않습니다.
2. 새 task 는 대표 task 와 겹치지 않는 실패 모드를 겨냥해야 합니다. 겹치면 held-out 이 아니라 대표 task 입니다.
3. 오염된 task 는 수정하지 않고 폐기합니다. 폐기 사실과 사유를 improvement log 에 남깁니다.
4. 다음 연번(`HLD-N`)을 부여합니다. 폐기한 ID 는 재사용하지 않습니다.
5. 세트 크기는 4~6건을 유지합니다. 크기가 커지면 실행되지 않고, 작아지면 과적합을 잡지 못합니다.

### 7.3 task 삭제

task 를 삭제하는 유일한 정당한 사유는 **대상 기능이 코드에서 사라진 경우**입니다. 점수가 낮다는 이유, 실행이 오래 걸린다는 이유, 자주 실패한다는 이유로 삭제하지 않습니다. 자주 실패하는 task 는 삭제 대상이 아니라 개선 대상입니다.

## 관련 문서

- [rubric.md](rubric.md)
- [tasks/representative.md](tasks/representative.md)
- [tasks/held-out.md](tasks/held-out.md)
- [../references/evaluation-layers.md](../references/evaluation-layers.md)
- [../references/generator-evaluator.md](../references/generator-evaluator.md)
- [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md)
- [../rules/promotion-gate.rule.md](../rules/promotion-gate.rule.md)
- [../rules/harness-change-control.rule.md](../rules/harness-change-control.rule.md)
- [../improvement-log/schema.md](../improvement-log/schema.md)
