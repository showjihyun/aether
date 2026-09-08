# 채점 기준 (Rubric)

이 문서는 평가를 실제로 채점하기 직전에 읽습니다. `scripts/eval.sh` 가 산출한 결과를 해석할 때, 대표·held-out task 실행 결과에 점수를 매길 때, `subjective` 리뷰를 수행할 때, 그리고 판정 결과를 `.harness/latest-eval.json` 으로 기록할 때가 그 시점입니다. 계층의 정의와 가중치는 [../references/evaluation-layers.md](../references/evaluation-layers.md) 가, task 세트의 운용은 [README.md](README.md) 가 소유합니다.

## 1. 채점 원칙

| 원칙 | 내용 |
| --- | --- |
| 측정 가능한 것은 측정합니다 | 테스트 통과 여부를 LLM 에게 묻지 않습니다. 실행하고 exit code 를 읽습니다. |
| 점수에는 증거 파일이 따라붙습니다 | 모든 계층 점수는 `evidence` 에 실제 로그 경로를 가집니다. 경로 없는 점수는 채점되지 않은 것으로 봅니다. |
| 실행하지 않은 계층은 만점이 아닙니다 | 수단이 없는 계층은 100점으로 적지 않습니다. `harness.config` 에서 가중치를 `0.00` 으로 두거나 단계를 두지 않아 `score` 가 `null` 이 되게 하고, `notes` 에 미구현 사유를 남깁니다. |
| 부분 점수는 단계 단위로만 줍니다 | 인상으로 70점을 주지 않습니다. 통과한 판정 단위의 개수로만 산출합니다. |
| 채점 후 기준을 바꾸지 않습니다 | 점수가 낮다는 이유로 합격 기준·가중치·임계값을 사후에 조정하지 않습니다. |

## 2. deterministic 계층의 점수 산출

`correctness`, `architecture`, `quality`, `behavior`, `performance` 다섯 계층은 deterministic 계층입니다. 점수는 명령 실행 결과에서만 나옵니다.

### 2.1 산출식

각 계층의 점수는 **그 계층에 속한 판정 단계 중 통과한 비율에 100을 곱하고 반올림한 값**입니다.

```text
layer_score = round( passed_steps / total_steps * 100 )
```

- `total_steps` 는 그 계층에 속한 판정 단계의 총 개수입니다. 실행하지 못한 단계도 분모에 포함합니다.
- `passed_steps` 는 `status: pass` 인 단계의 개수입니다. `fail` 과 `error` 는 모두 미통과입니다.
- 판정 단계는 두 출처에서 오고, **서로 다른 파일이 소유합니다.**
  - `harness.config` 의 `HARNESS_STEPS` 항목(`"id|layer|required|command"`)은 `scripts/eval.sh` 가 실행하고 집계해 `.harness/latest-eval.json` 에 넣습니다. 이 산출이 답하는 질문은 "하네스 자신이 성립하는가" 하나입니다.
  - task 문서의 합격 기준 항목은 **`eval.sh` 가 실행하지도 집계하지도 않습니다.** 그 판정은 새 세션의 에이전트나 사람이 수행하고 [runs/](runs/) 의 실행 기록이 소유합니다.
  - 두 출처를 하나의 `score` 로 섞지 않습니다. 섞으면 실행하지 않은 task 가 통과로 계산됩니다.
- 하나의 단계는 통과 또는 미통과 둘 중 하나이며 중간값을 갖지 않습니다.
- `total_steps` 가 0인 계층은 점수를 0으로 두지 않습니다. `scripts/eval.sh` 는 그 계층의 `score` 를 `null` 로 두고 가중치를 나머지 계층에 비례 재분배합니다. 미구현 사유는 `notes` 에 남깁니다.

예: `correctness` 에 unit, integration, e2e 세 단계가 있고 e2e 만 실패하면 `round(2/3*100) = 67` 입니다.

### 2.2 총점

총점은 계층 점수의 가중 평균을 반올림한 0~100 정수입니다.

```text
score = round( Σ ( layer_weight × layer_score ) )
```

가중치 합계는 항상 `1.00` 입니다. 총점이 `threshold` 이상이고 **필수 단계 실패가 0건일 때만** `pass: true` 입니다. 필수 단계가 하나라도 실패하면 총점과 무관하게 `pass: false` 이며(EV-5), 그 사실은 `.harness/latest-eval.json` 의 `failed_required` 에 기록됩니다. 임계값 기본값은 `HARNESS_THRESHOLD=80` 이며, 판정은 `harness/scripts/pass-threshold.sh` 로 합니다.

**총점만으로 판정하지 않습니다.** 총점이 올라도 어느 계층 점수가 기준선보다 낮으면 회귀입니다.

### 2.3 계층별 채점표

| layer | 판정 단계의 예 | 증거 | 100점 조건 | 0점 조건 | 감점하지 않는 것 |
| --- | --- | --- | --- | --- | --- |
| `correctness` | unit, integration, e2e, 회귀 테스트 | `.harness/logs/unit.log`, `.harness/logs/e2e.log` | 모든 테스트 단계가 `pass` 이고 skip 된 필수 테스트가 없음 | 모든 테스트 단계 미통과, 또는 테스트가 실행되지 않음 | 테스트 개수가 적다는 사실 자체(개수는 점수가 아닙니다) |
| `architecture` | 의존 방향 검사, 레이어 경계 검사, 순환 참조 검사 | `.harness/logs/arch.log` | 모든 규칙 검사가 위반 0건 | 규칙 검사가 실행되지 않았거나 전부 위반 | 규칙이 없는 영역(대신 `notes` 에 미구현으로 남김) |
| `quality` | lint, 타입 검사, 정적 분석 | `.harness/logs/lint.log`, `.harness/logs/typecheck.log` | 각 검사가 오류 0건 | 검사가 비활성화되어 있거나 전부 실패 | 경고(warning) 개수. 오류만 셉니다 |
| `behavior` | 화면 진입, 조작 후 상태 변화, console error 0건, 주요 API 응답 코드 | `.harness/logs/behavior.log`, 스크린샷 경로 | 시나리오의 모든 관측 명제가 성립 | 시나리오가 실행되지 않음 | 시각적 취향(그것은 `subjective` 입니다) |
| `performance` | 응답 시간 기준, 처리량 기준, 자원 사용 기준 | `.harness/logs/perf.log` | 모든 기준 항목이 기준값 이내 | 측정이 실행되지 않음 | 절대값(기준값 대비로만 판정합니다) |

`behavior` 의 판정 명제는 기계가 판정 가능한 형태여야 합니다. "화면이 좋아 보인다"는 `behavior` 가 아니며, "console error 0건", "HTTP 200", "지정한 요소가 화면에 보임" 은 `behavior` 입니다.

## 3. subjective 계층의 LLM 리뷰 루브릭

`subjective` 는 LLM 판정을 허용하는 유일한 계층입니다. 리뷰어는 코드를 만든 주체와 분리합니다([../references/generator-evaluator.md](../references/generator-evaluator.md)).

### 3.1 채점 항목

다섯 항목을 각각 0~4점으로 채점합니다. 항목을 추가하거나 빼지 않습니다.

| # | 항목 | 무엇을 보는가 |
| --- | --- | --- |
| S1 | 설계 적합성 | 변경이 기존 구조의 의도와 맞는가. 우회·특수 처리로 문제를 덮지 않았는가. |
| S2 | 변경 국소성 | 변경 범위가 요구 사항에 비례하는가. 관련 없는 수정이 섞이지 않았는가. |
| S3 | 가독성과 명명 | 이름과 구조만으로 의도를 알 수 있는가. 주석 없이 읽히는가. |
| S4 | 테스트의 의도 | 테스트가 동작의 계약을 검증하는가. 통과를 목적으로 한 테스트가 아닌가. |
| S5 | 근거의 일치 | 변경 설명·커밋 메시지·문서가 실제 코드와 일치하는가. |

### 3.2 0~4점 척도

모든 항목에 같은 척도를 적용합니다. 점수마다 **근거로 인용한 파일과 줄 번호**를 함께 남깁니다.

| 점수 | 서술 기준 |
| --- | --- |
| 0 | 항목이 성립하지 않습니다. 해당 축에서 명백한 결함이 있고, 다음 작업자가 이 변경 위에 작업하면 추가 비용이 발생합니다. 근거를 두 곳 이상 지목할 수 있습니다. |
| 1 | 심각한 문제가 하나 있습니다. 변경을 되돌리거나 다시 작성해야 하는 수준이며, 리뷰에서 반드시 지적될 항목입니다. |
| 2 | 동작에는 문제가 없으나 개선 요구가 남습니다. 지적 사항이 있고 후속 작업이 필요하지만 지금 병합해도 시스템이 나빠지지 않습니다. |
| 3 | 관례를 따르며 지적 사항이 사소합니다. 지적이 취향 범위이거나 후속 작업 없이 넘어갈 수 있습니다. |
| 4 | 기존 코드의 기준을 유지하거나 개선합니다. 이 변경이 이후 작업의 참고 사례가 될 수 있습니다. |

판정이 애매하면 **낮은 쪽**을 고릅니다. 근거를 지목할 수 없으면 그 항목은 채점하지 않고 `notes` 에 "근거 없음"으로 남깁니다. 근거 없는 4점은 자기 보고이며 점수로 취급하지 않습니다.

### 3.3 100점 환산

```text
subjective_score = round( Σ S1..S5 / 20 * 100 )
```

채점하지 못한 항목이 있으면 그 항목을 분자·분모에서 함께 제외하고 `notes` 에 제외 항목을 적습니다.

### 3.4 subjective 의 제약

- **`subjective` 는 단독으로 gate 가 되지 못합니다.** `subjective` 점수만으로 승격을 허용하거나 차단하지 않습니다.
- `subjective` 가 높아도 deterministic 계층 중 하나라도 기준선보다 낮으면 회귀입니다.
- `subjective` 가 낮을 때의 정당한 용도는 두 가지입니다. 사람 검토를 부르는 신호로 쓰거나, 이미 다른 계층을 통과한 변경들 사이의 우선순위를 조정하는 데 쓰는 것입니다.
- `subjective` 점수를 올리기 위해 리뷰 프롬프트를 바꾸지 않습니다. 리뷰 프롬프트 변경은 그 자체로 하네스 변경이며 승격 절차를 거칩니다.
- 자기 자신이 만든 변경을 자기가 채점한 경우, 그 점수는 기록하되 판정 근거로 쓰지 않습니다.

## 4. 회귀 판정

기준선(`.harness/baseline-eval.json`)과 비교해 다음 중 하나라도 해당하면 회귀입니다.

| 신호 | 판정 |
| --- | --- |
| 총점이 기준선보다 낮음 | 회귀 |
| 총점은 올랐으나 어느 계층 점수가 기준선보다 낮음 | 회귀 |
| held-out 총점이 기준선보다 낮음 | 회귀 |
| 기존에 통과하던 필수 단계가 실패 | 회귀 |
| 점수 변화가 없음 | 개선 근거 없음(승격하지 않습니다) |
| deterministic 계층은 그대로이고 `subjective` 만 오름 | 개선 근거 없음 |

## 5. 채점 결과 기록

결과는 `.harness/latest-eval.json` 에 고정 스키마로 기록합니다. 키를 추가하거나 이름을 바꾸지 않습니다.

```json
{
  "schema": "harness.eval/1",
  "layers": [
    {"layer": "correctness", "weight": 0.30, "score": 100, "deterministic": true, "evidence": ".harness/logs/unit.log", "notes": ""},
    {"layer": "architecture", "weight": 0.15, "score": 100, "deterministic": true, "evidence": ".harness/logs/arch.log", "notes": ""},
    {"layer": "quality", "weight": 0.15, "score": 100, "deterministic": true, "evidence": ".harness/logs/lint.log", "notes": ""},
    {"layer": "behavior", "weight": 0.20, "score": 33, "deterministic": true, "evidence": ".harness/logs/behavior.log", "notes": "3개 시나리오 중 1개 통과"},
    {"layer": "performance", "weight": 0.10, "score": 100, "deterministic": true, "evidence": ".harness/logs/perf.log", "notes": ""},
    {"layer": "subjective", "weight": 0.10, "score": 75, "deterministic": false, "evidence": ".harness/logs/review.md", "notes": "S1=3 S2=4 S3=3 S4=3 S5=2"}
  ],
  "score": 84,
  "threshold": 80,
  "pass": true,
  "failed_required": 0,
  "largest_failure": {"layer": "behavior", "detail": "결제 버튼 클릭 후 console TypeError 1건. 재현: harness/scripts/verify.sh 후 harness/scripts/eval.sh --reuse, 근거 .harness/logs/behavior.log:118"}
}
```

기록 규약은 다음과 같습니다.

- `layers` 에는 6개 계층을 **모두** 씁니다. 실행하지 못한 계층도 배열에서 빼지 않고 `score: null` 또는 `weight: 0.00` 과 `notes` 로 남깁니다.
- 실제로 채점된 계층의 `weight` 합계는 `1.00` 입니다. `score` 는 2.2 의 식으로 산출한 0~100 정수이며, 단계가 없는 계층만 `null` 입니다.
- `deterministic` 은 `subjective` 만 `false` 입니다.
- `evidence` 는 실제로 존재하는 파일 경로입니다. 경로를 지어내지 않습니다.
- `subjective` 의 `notes` 에는 항목별 원점수(`S1..S5`)를 남깁니다. 환산 점수만 남기면 재검토가 불가능합니다.
- `failed_required` 는 `.harness/verify.json` 의 같은 키를 그대로 옮긴 값입니다. 0 이 아니면 `score` 와 무관하게 `pass` 는 `false` 입니다(EV-5).
- `largest_failure` 에는 가장 큰 실패 하나만 적고, `detail` 에 재현 명령과 근거 경로를 포함합니다. 실패가 없으면 `detail` 을 빈 문자열로 둡니다.

승격 판정에 쓸 때는 이 파일을 기준선과 함께 보관하고, 대표·held-out task ID 와 변경 전후 점수를 improvement log 항목의 `regression_check` 에 옮겨 적습니다([../improvement-log/schema.md](../improvement-log/schema.md)).

## 6. 채점에서 금지하는 것

| 금지 | 이유 |
| --- | --- |
| 실패한 단계를 분모에서 빼기 | 통과율이 실제와 달라집니다. |
| 검사를 비활성화하고 만점 처리 | lint 를 끄면 `quality` 는 측정되지 않은 것이지 100점이 아닙니다. |
| 의미 없는 테스트로 개수 늘리기 | `correctness` 는 개수가 아니라 단계 통과 비율입니다. |
| 실행 없이 통과로 기록 | `evidence` 없는 점수는 채점되지 않은 것으로 봅니다. |
| 점수가 낮아서 임계값을 낮추기 | 임계값 변경은 하네스 변경이며 별도 승격 절차 대상입니다. |
| held-out 을 통과할 때까지 반복 실행 | 승격 판정에서 held-out 은 1회만 실행합니다. |

이 목록의 위반은 [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) 가 규범으로 다룹니다.

## 관련 문서

- [README.md](README.md)
- [tasks/representative.md](tasks/representative.md)
- [tasks/held-out.md](tasks/held-out.md)
- [../references/evaluation-layers.md](../references/evaluation-layers.md)
- [../references/generator-evaluator.md](../references/generator-evaluator.md)
- [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md)
- [../subagents/harness-evaluator.md](../subagents/harness-evaluator.md)
