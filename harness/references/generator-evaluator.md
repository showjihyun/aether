# Generator와 Evaluator 분리

이 문서는 구현과 평가를 한 에이전트가 함께 수행하고 있고 그 결과가 신뢰되지 않을 때 읽습니다. 두 역할을 나눌지 판단하는 기준, 나눴을 때 각 역할이 지켜야 할 계약, Evaluator가 Generator에게 돌려주는 피드백의 형식을 정의합니다. 계층 정의와 점수 스키마는 [evaluation-layers.md](evaluation-layers.md) 가 소유하므로 여기서 다시 정의하지 않습니다.

## 1. 자기 평가의 실패 모드

구현자가 자기 결과를 평가하면 다음이 반복적으로 나타납니다.

| 실패 모드 | 어떻게 드러나는가 | 왜 생기는가 |
| --- | --- | --- |
| 확인 편향 | 성공 경로만 실행하고 실패 경로를 시도하지 않습니다. | 방금 만든 설계를 성립시키는 관측을 우선 찾습니다. |
| 근거 없는 통과 선언 | 명령을 실행하지 않고 "테스트 통과"라고 보고합니다. | 결과가 이미 예측되므로 실행이 불필요하게 느껴집니다. |
| 기준 완화 | 실패한 검사를 고치는 대신 검사 범위나 임계값을 줄입니다. | 평가 함수와 구현이 같은 손에 있으면 어느 쪽을 고쳐도 점수가 오릅니다. |
| 맥락 오염 | 구현 중 세운 가정이 평가 시 그대로 전제로 쓰입니다. | 같은 대화 컨텍스트에 설계 의도와 판정이 섞여 있습니다. |
| 큰 실패의 희석 | 사소한 개선 여러 개를 나열하고 치명적 실패 1개를 묻습니다. | 자기 산출물에 대한 총평은 평균으로 수렴합니다. |

핵심은 **평가 함수와 구현이 같은 소유자에게 있으면 평가가 최적화 대상이 된다**는 점입니다. 사람이 개발할 때 구현자와 리뷰어를 나누는 이유와 같습니다.

## 2. 역할 계약

### Generator

| 구분 | 내용 |
| --- | --- |
| 하는 일 | 요구사항을 구현합니다. 자신이 만든 변경에 대한 테스트를 작성합니다. `scripts/verify.sh` 를 실행해 스스로 1차 확인합니다. Evaluator 피드백을 받아 수정합니다. 재현 절차를 그대로 실행해 수정 결과를 확인합니다. |
| 하지 않는 일 | 평가 기준을 고치지 않습니다. `harness.config` 의 `HARNESS_EVAL_WEIGHTS` / `HARNESS_THRESHOLD` / `HARNESS_STEPS` 를 수정하지 않습니다. lint rule, arch rule, 테스트 assertion을 완화하거나 skip 처리하지 않습니다. `.harness/latest-eval.json` 을 직접 쓰지 않습니다. 자신의 점수를 스스로 매기지 않습니다. |

### Evaluator

| 구분 | 내용 |
| --- | --- |
| 하는 일 | 정해진 계층대로 검사를 실행합니다. 실제 관측 채널로 결과를 확인합니다. `.harness/logs/*` 에 근거를 남깁니다. `.harness/latest-eval.json` 을 산출합니다. `largest_failure` 를 1개 지목합니다. 재현 절차를 제공합니다. |
| 하지 않는 일 | 코드를 고치지 않습니다. 실패를 대신 수정해 통과시키지 않습니다. 평가 기준을 자기 판단으로 바꾸지 않습니다. 실행하지 않은 검사를 통과로 기록하지 않습니다. 근거 파일 없는 점수를 만들지 않습니다. 수정 방향을 설계로 지시하지 않고 관측된 사실과 기대값만 전달합니다. |

두 문장으로 요약하면 다음과 같습니다.

- **Evaluator는 코드를 고치지 않습니다.**
- **Generator는 평가 기준을 고치지 않습니다.**

이 두 금지가 깨지면 분리의 효과는 사라집니다. 위반 판정은 [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) 를 따릅니다.

## 3. 인터페이스

Evaluator가 Generator에게 돌려주는 피드백은 다음 필드를 모두 갖춰야 합니다. 하나라도 빠지면 Generator는 수정에 착수하지 않고 재평가를 요청합니다.

| 필드 | 필수 | 내용 | 값 규칙 |
| --- | --- | --- | --- |
| `layer` | 예 | 어느 평가 계층에서 발견되었는가 | `correctness` `architecture` `quality` `behavior` `performance` `subjective` 중 하나 |
| `evidence` | 예 | 근거 파일 경로와 위치 | 프로젝트 루트 기준 상대 경로. 가능하면 `파일:줄` 까지. 예: `.harness/logs/behavior.log:118` |
| `repro` | 예 | 재현 절차 | 사람이 그대로 붙여 실행할 수 있는 명령 나열. 자연어 서술만으로는 부족합니다. |
| `severity` | 예 | 심각도 | `blocker` `major` `minor` 중 하나. `blocker` 는 promote를 차단합니다. |
| `largest_failure` | 예 | 이번 회차의 가장 큰 실패 **1개** | 가중 손실 `weight × (100 - score)` 가 가장 큰 계층 1개. 목록이 아니라 단수입니다. |
| `expected` / `actual` | 예 | 기대값과 관측값 | 판정 가능한 명제로 씁니다. "이상해 보임" 은 관측값이 아닙니다. |
| `suggested_enforcement` | 아니오 | 이 실패를 앞으로 막을 수단의 후보 | `test` `lint` `arch-rule` `hook` `script` `doc` `skill` `subagent` `instruction` 중 하나. 제안이며 지시가 아닙니다. |

계층별 점수와 총점은 새 형식을 만들지 않고 `.harness/latest-eval.json` (스키마 `harness.eval/1`) 에 그대로 담습니다. `layer` 와 `largest_failure` 는 그 파일의 동일 필드에 대응하고, `evidence` 는 `layers[].evidence` 에, `repro` 와 `expected`/`actual` 은 `largest_failure.detail` 및 `layers[].notes` 에 기록합니다.

Generator에게 전달하는 본문은 다음 형식을 씁니다.

```text
LARGEST FAILURE
  layer     : behavior
  severity  : blocker
  expected  : checkout 결제 버튼 클릭 후 console error 0건, 주문 완료 화면 표시
  actual    : console TypeError 1건, 화면 전환 없음
  evidence  : .harness/logs/behavior.log:118, .harness/logs/behavior-03.png
  repro     : 1) scripts/eval.sh --only behavior
              2) .harness/logs/behavior.log 에서 "checkout" 검색

OTHER FINDINGS
  [major] quality   lint warning 4건            .harness/logs/lint.log:12
  [minor] performance p95 412ms / 목표 400ms    .harness/logs/bench.log:5

NOT EVALUATED
  performance 계층의 부하 시나리오 미구현. weight 0.10, score는 직전 값 유지
```

`NOT EVALUATED` 를 비워두지 않습니다. 실행하지 못한 검사를 침묵으로 처리하면 Generator는 그 축이 통과한 것으로 오인합니다.

## 4. 분리가 필요한 경우와 과한 경우

분리는 비용이 있습니다. 왕복 1회마다 컨텍스트 전달과 실행 시간이 추가됩니다. 다음 기준으로 판단합니다.

| 신호 | 판정 |
| --- | --- |
| 자기 보고 통과와 실제 실행 결과가 어긋난 사례가 2회 이상 있었다 | 분리합니다 |
| `behavior` 계층이 필요한데 구현 에이전트가 브라우저·API를 실행하지 않고 있다 | 분리합니다 |
| 실패를 만나면 검사 기준을 완화하는 패턴이 관측된다 | 분리합니다 |
| 변경 범위가 크거나 보안·데이터 이관 등 되돌리기 어려운 영역이다 | 분리합니다 |
| loop 반복 중 동일 실패가 3회 반복된다 | 분리합니다. 종료 조건은 [../rules/loop-budget.rule.md](../rules/loop-budget.rule.md) 를 따릅니다 |
| 변경이 한 파일 수준이고 `scripts/verify.sh` 가 결과를 완전히 판정한다 | 과합니다. deterministic 검사만으로 충분합니다 |
| 평가면이 아직 없다 | 과합니다. 먼저 `scripts/verify.sh` 를 만듭니다. 분리는 평가면을 대체하지 못합니다 |
| 매 편집마다 분리를 적용하고 있다 | 과합니다. inner loop는 verify로 돌리고 분리는 회차 경계에서만 적용합니다 |
| Evaluator가 실행 없이 코드만 읽고 있다 | 과합니다. 그 분리는 비용만 늘리고 새 정보를 만들지 않습니다 |

원칙은 **분리는 평가면을 강화하는 수단이지 평가면의 대체물이 아니다** 입니다. deterministic 검사로 판정되는 것을 사람 형태의 왕복으로 바꾸지 않습니다.

## 5. 실행 주체와 관측 채널

이 구조의 Evaluator 역할은 [../subagents/harness-evaluator.md](../subagents/harness-evaluator.md) 가 수행합니다. 해당 subagent는 코드 수정 권한을 갖지 않고 `scripts/eval.sh` 실행과 `.harness/latest-eval.json` 산출만 담당합니다. 코드 변경에 대한 구조 리뷰는 [../subagents/harness-reviewer.md](../subagents/harness-reviewer.md) 가 별도로 맡습니다.

Evaluator는 코드를 읽는 데 그치지 않습니다. 웹 애플리케이션이라면 실제 브라우저를 실행하고, 버튼을 누르고, 화면을 확인하고, console error와 network request를 봅니다. 백엔드라면 통합 테스트, curl, DB 조회, 애플리케이션 로그, 지표와 트레이스를 봅니다. 이 관측 채널의 목록과 최소 요구사항은 [agent-observability.md](agent-observability.md) 에 있으며, 채널이 없으면 `behavior` 계층은 점수를 만들 수 없고 `NOT EVALUATED` 로 보고해야 합니다.

관측된 사실은 반드시 파일로 남깁니다. 화면에만 나타났다가 사라진 관측은 근거가 아닙니다.

## 6. 흐름도

```text
        요구사항 / 직전 회차의 피드백
                    │
                    ▼
            ┌───────────────┐
            │   Generator   │  코드 수정, 테스트 작성
            └───────┬───────┘
                    │  scripts/verify.sh (자체 1차 확인)
                    ▼
              Implementation
                    │
                    ▼
            ┌───────────────┐
            │   Evaluator   │  scripts/eval.sh
            │               │  browser / API / log / metric 관측
            └───────┬───────┘
                    │
                    ▼
   .harness/latest-eval.json  +  .harness/logs/*
   계층별 score / largest_failure / evidence / repro
                    │
        ┌───────────┴────────────┐
        │                        │
   pass = false             pass = true
        │                        │
        ▼                        ▼
  Generator 로 반송        promotion gate 판정
  (largest_failure 1개)    (계층 회귀 동시 확인)
        │                        │
        │                        ▼
        │                  improvement-log candidate
        │
        └── 반복. 종료 조건은 loop-budget 규칙이 소유
```

Generator와 Evaluator는 같은 계층 정의와 같은 산출 파일을 공유합니다. 두 역할이 서로 다른 기준으로 판정하기 시작하면 분리는 의미를 잃습니다.

## 관련 문서

- [evaluation-layers.md](evaluation-layers.md) — 계층 정의, 가중치, `latest-eval.json` 스키마
- [agent-observability.md](agent-observability.md) — Evaluator가 사용하는 실제 관측 채널
- [inner-outer-loop.md](inner-outer-loop.md) — 분리를 어느 loop 경계에서 적용하는가
- [../subagents/harness-evaluator.md](../subagents/harness-evaluator.md) — Evaluator 역할 정의
- [../subagents/harness-reviewer.md](../subagents/harness-reviewer.md) — 구조 리뷰 역할 정의
- [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) — 역할 계약 위반 판정
- [../rules/loop-budget.rule.md](../rules/loop-budget.rule.md) — 왕복 반복의 예산과 종료 조건
