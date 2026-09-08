# 하네스 변경 관리 규칙 (CC)

하네스 자체를 바꾸려 할 때 이 문서를 읽습니다. `templates/AGENTS.md`, `rules/`, `skills/`, `hooks/`, `scripts/`, `evaluation/` 중 무엇이든 수정하기 직전, 그리고 회고에서 나온 개선안을 실제로 적용하는 Outer Loop 라운드를 시작할 때가 해당 시점입니다. 이 문서는 변경의 **적용 단위와 판정 방식**을 정하고, 그 변경을 영구 자산으로 올릴지는 [promotion-gate.rule.md](promotion-gate.rule.md) 가 정합니다.

## 규칙

| ID | 규칙 |
| --- | --- |
| **CC-1** | 하네스 변경은 한 번에 하나만 적용하고, 변경 사이에 반드시 평가를 실행합니다. 여러 변경을 묶어 적용하면 어떤 변경이 점수를 움직였는지 판정할 수 없으므로 그 라운드의 결과는 근거로 쓰지 않습니다. |
| **CC-2** | 평가 프롬프트·rubric·task 목록·임계값과 하네스 변경을 같은 라운드에 함께 바꾸지 않습니다. 평가 기준을 바꾼 라운드는 기준선 재측정 전용 라운드로 취급합니다. |
| **CC-3** | 점수가 나빠지면 되돌립니다. 각 라운드는 `keep` 또는 `reject` 로 판정하며, `reject` 인 변경은 다음 라운드 시작 전에 원상 복구합니다. 판정 없이 다음 변경으로 넘어가지 않습니다. |
| **CC-4** | 변경 전후의 종합 점수와 계층별 점수를 함께 기록합니다. 종합 점수가 올라도 어느 layer 가 내려갔는지 기록하지 않은 라운드는 `keep` 으로 판정하지 않습니다. |
| **CC-5** | 하네스 변경은 제품 코드 변경과 같은 커밋에 섞지 않습니다. 하네스 변경만 담은 커밋으로 분리해야 되돌리기가 한 번의 되돌리기로 끝납니다. |
| **CC-6** | Inner Loop 안에서 하네스를 바꾸지 않습니다. 현재 task 를 통과시키기 위한 반복 중에 규칙·skill·평가 설정을 수정하면 통과 원인이 구현인지 하네스인지 구분되지 않습니다. 하네스 변경은 Outer Loop 라운드에서만 합니다. |

## 판정 절차

한 라운드는 다음 순서로 진행합니다.

1. 기준선을 측정합니다. 하네스를 손대지 않은 상태에서 평가를 실행하고 `.harness/latest-eval.json` 의 `score` 와 `layers[].score` 를 기준선으로 기록합니다.
2. 변경 후보 하나를 고릅니다. 후보가 여러 개면 `recurrence_risk` 가 높은 것부터 처리합니다.
3. 변경 하나만 적용합니다. 이때 `evaluation/` 은 건드리지 않습니다(CC-2).
4. 같은 task 집합으로 평가를 다시 실행합니다.
5. 아래 판정 기준으로 `keep` 또는 `reject` 를 정합니다.
6. `keep` 이면 새 점수를 다음 라운드의 기준선으로 삼고, `reject` 이면 변경을 되돌린 뒤 기준선을 유지합니다.
7. 라운드 결과를 improvement log 항목의 `regression_check` 에 기록합니다.

판정 기준은 다음과 같습니다.

- 종합 `score` 가 기준선보다 높고, 어느 layer 도 기준선보다 낮지 않으면 `keep` 입니다.
- 종합 `score` 가 올랐더라도 어떤 layer 가 내려갔다면 그 layer 의 하락 원인을 규명하기 전까지 `reject` 입니다.
- 종합 `score` 가 같거나 내려가면 `reject` 입니다. 변경이 없는 것과 같은 결과에 하네스 복잡도만 늘리지 않습니다.

### 라운드 진행표

기준선 72 에서 세 개의 변경 후보를 처리하는 진행을 일반화하면 다음과 같습니다.

| 라운드 | 적용한 변경 | 진입 기준선 | 측정 score | 판정 | 라운드 종료 후 기준선 | 후속 조치 |
| --- | --- | --- | --- | --- | --- | --- |
| R0 | 없음(기준선 측정) | — | 72 | — | 72 | 계층별 점수를 함께 저장합니다. |
| R1 | Change A | 72 | 75 | `keep` | 75 | 변경을 유지하고 improvement log 를 `validating` 으로 올립니다. |
| R2 | Change B | 75 | 73 | `reject` | 75 | 변경을 되돌리고 improvement log 를 `rejected` 로 종결합니다. |
| R3 | Change C | 75 | 81 | `keep` | 81 | 변경을 유지하고 held-out 회귀 검증으로 넘깁니다. |

이 진행은 Hill Climbing 입니다. 개선안을 제안하고, 실제로 평가하고, 좋아졌을 때만 남깁니다. R2 의 `reject` 를 생략하고 점수가 내려간 변경을 그대로 둔 채 다음 변경을 쌓으면, 하네스는 개선되는 것이 아니라 **Self-Drift** 로 흘러갑니다. Self-Drift 는 각 변경이 개별적으로는 그럴듯하지만 누적 결과가 검증되지 않아, 하네스가 실제 목표가 아닌 방향으로 서서히 이동하는 상태를 말합니다. 되돌리기 규칙(CC-3)과 변경 단위 격리(CC-1, CC-5)가 Self-Drift 를 막는 최소 장치입니다.

## 위반 예시와 교정

### 예시 1 — 한 라운드에 여러 변경을 묶은 경우

한 라운드에서 `templates/AGENTS.md`, skill, 아키텍처 규칙, 도구, 평가 프롬프트를 모두 바꾸었고 점수가 72 에서 80 으로 올랐습니다. CC-1 과 CC-2 위반입니다. 점수는 올랐지만 무엇이 기여했는지 알 수 없고, 평가 프롬프트가 함께 바뀌었으므로 72 와 80 은 같은 기준의 값도 아닙니다.

교정: 변경을 모두 되돌리고 평가 프롬프트 변경만 먼저 적용해 기준선을 재측정합니다. 그 다음 나머지 변경을 한 라운드에 하나씩 적용하며 라운드 진행표를 채웁니다.

### 예시 2 — Inner Loop 안에서 규칙을 바꾼 경우

구현 → 테스트 → 분석 → 수정 반복 중 테스트가 계속 실패하자 에이전트가 실패하는 아키텍처 규칙 자체를 완화하고 테스트를 통과시켰습니다. CC-6 위반이며, 동시에 평가 대상을 변경 대상으로 삼은 것이므로 [evaluation-integrity.rule.md](evaluation-integrity.rule.md) 의 문제이기도 합니다.

교정: 규칙 완화를 되돌리고 Inner Loop 는 구현 수정만으로 종료합니다. 규칙이 실제로 과도했다면 그 판단을 improvement log 후보로 남기고, 다음 Outer Loop 라운드에서 단일 변경으로 적용해 평가합니다.

### 예시 3 — 하네스 변경과 제품 코드를 같은 커밋에 섞은 경우

기능 구현과 hook 추가를 한 커밋에 담았고, 이후 점수가 내려가 되돌리려 했지만 기능까지 함께 사라졌습니다. CC-5 위반입니다.

교정: 커밋을 분리합니다. 제품 코드 커밋과 하네스 커밋을 나누고, 라운드 판정이 `reject` 일 때 하네스 커밋만 되돌립니다.

```bash
# 하네스 변경만 담긴 커밋을 되돌립니다.
git revert <harness-only-commit>
harness/scripts/eval.sh
```

## 관련 문서

- [promotion-gate.rule.md](promotion-gate.rule.md)
- [evaluation-integrity.rule.md](evaluation-integrity.rule.md)
- [loop-budget.rule.md](loop-budget.rule.md)
- [harness-gc.rule.md](harness-gc.rule.md)
- [RULES.md](RULES.md)
- [../references/inner-outer-loop.md](../references/inner-outer-loop.md)
- [../evaluation/rubric.md](../evaluation/rubric.md)
- [../evaluation/tasks/held-out.md](../evaluation/tasks/held-out.md)
