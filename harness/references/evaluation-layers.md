# 평가 계층 (Evaluation Layers)

이 문서는 하네스의 평가면을 설계하거나 수정할 때 읽습니다. `scripts/eval.sh` 의 계층 구성, `.harness/latest-eval.json` 의 해석, promote 판정에 어떤 점수를 근거로 쓸 것인가를 결정하기 전에 이 문서를 먼저 읽습니다. 평가 조작을 금지하는 규범 ID는 여기서 발급하지 않고 [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) 가 소유합니다.

## 1. Evaluation이 Memory보다 먼저인 이유

Self-Improving Agent를 만들 때 Memory부터 붙이려는 시도가 흔합니다. 평가 없이 Memory를 먼저 만들면 잘못된 판단까지 그대로 보존됩니다. 보존된 오답은 다음 실행에서 더 빠르게 재현되므로, 평가 없는 Memory는 개선이 아니라 오류의 가속입니다.

따라서 이 번들은 다음 순서를 규범으로 고정합니다. 이 순서는 뒤에서 앞으로 건너뛸 수 없습니다.

```text
Execution
 ↓
Evaluation      ← 계층별 점수와 근거 파일을 만든다
 ↓
Evidence        ← .harness/logs/*, .harness/verify.json, .harness/latest-eval.json
 ↓
Diagnosis       ← 증상이 아니라 원인을 찾는다
 ↓
Lesson          ← improvement-log/ 의 candidate
 ↓
Memory          ← 검증을 통과한 lesson만 하네스에 승격된다
```

| 단계 | 산출물 | 이 단계 없이 다음으로 갈 때 생기는 일 |
| --- | --- | --- |
| Execution | 변경된 작업 트리 | 평가 대상이 없습니다. |
| Evaluation | `.harness/latest-eval.json` | 무엇이 나빠졌는지 모른 채 기억만 쌓입니다. |
| Evidence | `.harness/logs/*` | 주장은 있으나 재현 절차가 없어 검증이 불가능합니다. |
| Diagnosis | root_cause | 증상만 고치고 같은 실패가 다시 납니다. |
| Lesson | improvement-log candidate | 원인을 알고도 시스템에 아무것도 남지 않습니다. |
| Memory | 승격된 하네스 요소 | 후보가 검증 없이 영구 규칙이 됩니다. |

Memory는 학습 그 자체가 아니라 **검증된 학습 결과를 보존하는 장치**입니다. 그러므로 하네스에서 가장 먼저 만들어야 하는 것은 Memory 저장소가 아니라 평가면입니다.

## 2. 6계층 정의

평가는 하나의 숫자가 아니라 6개 계층으로 나누어 측정합니다. layer 식별자는 고정 계약이며 다른 이름을 쓰지 않습니다.

| layer 식별자 | 한국어 이름 | 측정 대상 | 대표 수단 | deterministic | 기본 가중치 | 조작 위험 |
| --- | --- | --- | --- | --- | --- | --- |
| `correctness` | 정확성 | 요구된 동작이 실제로 성립하는가 | Unit / Integration / E2E 테스트 | 예 | 0.30 | 의미 없는 테스트를 대량 추가해 통과 수와 coverage만 올립니다. 실패 테스트를 skip 처리합니다. |
| `architecture` | 구조 | 의존 방향과 경계가 지켜지는가 | 아키텍처 규칙 도구의 의존 방향·import 경계 검사 (언어별 도구는 `language/` 팩) | 예 | 0.15 | 규칙에서 위반 패키지를 예외 목록에 추가합니다. 규칙 파일 자체를 완화합니다. |
| `quality` | 품질 | 정적으로 발견 가능한 결함이 없는가 | Lint, 타입 검사, 정적 분석 | 예 | 0.15 | lint rule을 끄거나 `disable` 주석을 뿌립니다. 검사 대상 경로를 좁힙니다. |
| `behavior` | 실동작 | 실행 중인 시스템이 사용자 관점에서 동작하는가 | 브라우저 조작, DOM/스크린샷, console/network 확인, API 시나리오, curl | 예 | 0.20 | 실행하지 않고 통과로 보고합니다. 시나리오에서 실패 경로를 삭제합니다. |
| `performance` | 성능 | 응답 시간·자원 사용이 기준 안에 있는가 | 벤치마크, 부하 테스트, 지표·트레이스 | 예 | 0.10 | 측정 부하를 낮추거나 기준값을 올립니다. 워밍업만 측정합니다. |
| `subjective` | 주관 품질 | 사람이 볼 때 납득 가능한 설계·가독성인가 | LLM Review, Human Review | 아니오 | 0.10 | 스스로에게 높은 점수를 부여합니다. 근거 없이 서술만으로 점수를 만듭니다. |

가중치 합계는 항상 `1.00` 입니다. 프로젝트가 가중치를 재정의하면 `harness.config` 의 `HARNESS_EVAL_WEIGHTS` 에 `"layer|weight"` 형식으로 6개 계층을 모두 적고, 합계가 `1.00` 인지 `scripts/eval.sh` 가 검사합니다.

계층을 삭제하지 않습니다. 프로젝트에 해당 수단이 아직 없으면 계층을 지우는 대신 가중치를 `0.00` 으로 두고 `notes` 에 미구현 사유와 도입 예정 시점을 적습니다. 계층 자체가 사라지면 그 축의 회귀를 아무도 보지 않게 됩니다.

## 3. Deterministic 우선 원칙

측정 가능한 것은 측정합니다. LLM에게 "테스트가 통과했는지 판단해줘"라고 요청할 이유는 없습니다. 테스트는 실행하면 되고, 실행 결과는 exit code로 남습니다.

- `correctness`, `architecture`, `quality`, `behavior`, `performance` 다섯 계층은 **deterministic 계층**입니다. 점수는 명령 실행 결과에서만 산출하며 LLM 판단을 개입시키지 않습니다.
- `behavior` 는 브라우저·API 같은 실제 관측 채널을 쓰지만, 판정은 "console error 0건", "HTTP 200", "지정한 요소가 보이는가" 처럼 기계가 판정 가능한 명제로 환원해야 합니다. 스크린샷을 보고 LLM이 "좋아 보인다"고 말하는 것은 `behavior` 가 아니라 `subjective` 입니다.
- LLM 판정을 허용하는 유일한 계층은 `subjective` 입니다.
- `subjective` 의 결과는 **단독으로 gate가 되지 못합니다.** `subjective` 점수만으로 promote를 허용하거나 차단하지 않습니다. `subjective` 는 사람 검토를 부르는 신호이며, 다른 계층이 이미 통과한 변경의 우선순위를 조정하는 데만 씁니다.
- deterministic 계층의 `deterministic` 필드를 `false` 로 낮추는 변경은 평가면 약화입니다. 근거 없이 수행하지 않습니다.

각 계층은 `evidence` 로 재현 가능한 파일 경로를 반드시 남깁니다. 근거 파일이 없는 점수는 점수가 아닙니다.

## 4. 단일 점수의 위험

에이전트는 사람이 의도한 목적이 아니라 **주어진 평가 함수**를 최적화합니다. `Test Coverage > 90%` 를 주면 의미 없는 테스트 수백 개가 생기고, `Lint Errors = 0` 을 주면 lint rule을 끄는 것이 가장 값싼 해답이 됩니다. 전형적인 Goodhart's Law 상황입니다.

그래서 다음을 규범으로 둡니다.

1. 보고는 항상 **계층별 점수와 함께** 합니다. 총점만 출력하는 보고는 불완전한 보고입니다.
2. 총점만으로 promote 판정을 하지 않습니다. 총점은 필요조건이며 충분조건이 아닙니다.
3. `largest_failure` 를 항상 1개 지목합니다. 값은 **가중 손실**, 즉 `weight × (100 - score)` 가 가장 큰 계층입니다. 동률이면 표의 위쪽 계층을 택합니다.
4. 총점이 올랐더라도 어떤 deterministic 계층의 점수가 직전 실행보다 내려갔다면 그 실행은 개선으로 보고하지 않습니다. 계층별 회귀는 총점 상승으로 상쇄되지 않습니다.
5. 가중치 조정이나 계층 제외로 총점을 올리는 것은 개선이 아니라 평가 조작입니다. 판정과 제재는 [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) 를 따릅니다.

## 5. sample latest-eval.json

다음은 `.harness/latest-eval.json` 의 완전한 예시입니다. 스키마는 고정 계약이며 키를 추가하거나 이름을 바꾸지 않습니다.

```json
{
  "schema": "harness.eval/1",
  "layers": [
    {"layer": "correctness", "weight": 0.30, "score": 100, "deterministic": true, "evidence": ".harness/logs/unit.log", "notes": "unit 412 pass / integration 38 pass"},
    {"layer": "architecture", "weight": 0.15, "score": 100, "deterministic": true, "evidence": ".harness/logs/archrule.log", "notes": "dependency rule 위반 0건"},
    {"layer": "quality", "weight": 0.15, "score": 92, "deterministic": true, "evidence": ".harness/logs/lint.log", "notes": "warning 4건, error 0건"},
    {"layer": "behavior", "weight": 0.20, "score": 75, "deterministic": true, "evidence": ".harness/logs/behavior.log", "notes": "checkout 시나리오에서 console error 1건"},
    {"layer": "performance", "weight": 0.10, "score": 88, "deterministic": true, "evidence": ".harness/logs/bench.log", "notes": "p95 412ms / 목표 400ms"},
    {"layer": "subjective", "weight": 0.10, "score": 70, "deterministic": false, "evidence": ".harness/logs/review.md", "notes": "LLM Review. 단독 gate로 사용하지 않음"}
  ],
  "score": 90,
  "threshold": 80,
  "pass": true,
  "largest_failure": {"layer": "behavior", "detail": "checkout 결제 버튼 클릭 후 console TypeError 1건. 재현: scripts/eval.sh --only behavior, 근거 .harness/logs/behavior.log:118"}
}
```

- `score` 는 가중 평균을 반올림한 0~100 정수입니다. 위 예시의 계산은 `100×0.30 + 100×0.15 + 92×0.15 + 75×0.20 + 88×0.10 + 70×0.10 = 89.6` 이므로 `90` 입니다.
- `pass` 는 `score >= threshold` 이고 `failed_required` 가 0 일 때만 `true` 입니다. 필수 단계가 하나라도 실패하면 총점과 무관하게 `false` 입니다([../subagents/harness-evaluator.md](../subagents/harness-evaluator.md) EV-5). `pass` 가 `true` 여도 `largest_failure` 는 항상 채웁니다. 위 예시처럼 총점이 통과해도 `behavior` 가 열려 있을 수 있고, 그 사실이 보고에서 사라지면 안 됩니다.
- `pass` 는 promote 허가가 아닙니다. 승격 판정은 `../rules/promotion-gate.rule.md` 가 소유하며, 그 게이트는 `pass` 외에 계층별 회귀 여부를 함께 봅니다.

## 6. 계층 가중치 조정 규칙

가중치는 평가면의 모양 그 자체입니다. 가중치를 바꾸는 것은 코드를 바꾸는 것보다 영향이 큽니다.

| 항목 | 규범 |
| --- | --- |
| 누가 | 사람 소유자만 변경합니다. 에이전트는 제안만 하고 직접 수정하지 않습니다. |
| 언제 | 평가 대상 자체가 바뀌었을 때만 변경합니다. 예: 프로젝트에 부하 테스트가 신설되어 `performance` 를 처음 측정하게 된 경우. |
| 무엇을 근거로 | 실패 사례 최소 1건과 improvement-log 항목을 근거로 제시합니다. |
| 어떻게 | `harness.config` 의 `HARNESS_EVAL_WEIGHTS` 만 수정합니다. `scripts/eval.sh` 내부의 기본값을 직접 고치지 않습니다. |
| 언제 하면 안 되는가 | 현재 실행이 threshold에 미달한 상태에서는 변경하지 않습니다. 실패를 통과로 바꾸기 위한 조정은 금지합니다. |
| 검증 | 변경 후 직전 커밋 기준으로 `scripts/eval.sh` 를 다시 실행해 총점 변화가 설명 가능한지 확인합니다. |

에이전트가 스스로 가중치, threshold, 계층 목록, `deterministic` 값을 수정하는 것은 금지합니다. 이 금지의 규범 ID와 위반 판정 절차는 [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) 에 있습니다. 하네스 구성 파일에 대한 변경 통제 절차는 [../rules/harness-change-control.rule.md](../rules/harness-change-control.rule.md) 를 따릅니다.

## 관련 문서

- [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) — 평가 조작 금지, 가중치 자가 수정 금지
- [../rules/promotion-gate.rule.md](../rules/promotion-gate.rule.md) — 총점과 계층 점수를 승격 판정에 쓰는 방법
- [generator-evaluator.md](generator-evaluator.md) — 평가를 별도 역할로 분리하는 구조
- [agent-observability.md](agent-observability.md) — `behavior` 계층이 사용하는 관측 채널
- [inner-outer-loop.md](inner-outer-loop.md) — 평가 결과가 어느 loop로 흘러가는가
- [../evaluation/rubric.md](../evaluation/rubric.md) — 계층별 점수 산출 기준
- [../subagents/harness-evaluator.md](../subagents/harness-evaluator.md) — 평가 실행 주체
