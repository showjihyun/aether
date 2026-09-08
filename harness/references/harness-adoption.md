# 하네스 도입 순서

이 문서는 하네스가 없는 프로젝트에 Self-Improving Loop를 처음 세울 때, 그리고 이미 시작한 도입이 정체되어 다음에 무엇을 해야 할지 정해야 할 때 읽습니다. Day 1 / Week 1 / Month 1 / 분기의 네 단계로 도입 순서를 고정하고, 각 단계의 산출물·완료 판정 기준·금지 행동과 [maturity-levels.md](maturity-levels.md)의 L0~L5 대응을 규정합니다.

## 1. 도입 원칙

처음부터 거창하게 만들지 않습니다. Self-Improving Loop라는 이름 때문에 복잡한 구조를 먼저 떠올리기 쉽지만, 실제로 필요한 것은 다음 세 가지에서 시작합니다.

```text
1. 통합된 Verify 명령
2. Improvement Log
3. Harness Retrospective
```

| ID | 원칙 |
| --- | --- |
| AD-P1 | 단계를 건너뛰지 않습니다. 앞 단계의 완료 판정 기준을 만족하기 전에 다음 단계의 산출물을 만들지 않습니다 |
| AD-P2 | 각 단계는 그 단계만으로 이미 쓸모가 있어야 합니다. 다음 단계가 와야 비로소 쓸모가 생기는 산출물은 그 단계의 산출물이 아닙니다 |
| AD-P3 | 산출물은 Git에 넣고, 리뷰하고, 검증하고, 필요 없어지면 제거합니다. 제거 규약은 [../rules/harness-gc.rule.md](../rules/harness-gc.rule.md)를 따릅니다 |
| AD-P4 | 도입 자체를 하나씩 합니다. 한 번에 여러 하네스 요소를 도입하면 무엇이 효과를 냈는지 귀속할 수 없습니다 |
| AD-P5 | 최종 목표는 L5가 아닙니다. L3와 L4를 제대로 세우는 것이 L5를 흉내 내는 것보다 우선합니다 |

## 2. 단계 개요

| 단계 | 기간 | 한 줄 목표 | 진입 성숙도 | 도달 성숙도 |
| --- | --- | --- | --- | --- |
| AD-1 | Day 1 | 통합 verify 명령 하나를 만듭니다 | L0 Prompting | L1 Agent Loop |
| AD-2 | Week 1 | 명시적 평가 기준과 반복 예산을 붙입니다 | L1 Agent Loop | L2 Eval Loop |
| AD-3 | Month 1 | 실패가 산출물로 남고 승격 게이트를 거치게 합니다 | L2 Eval Loop | L3 Persistent Learning → L4 Harness Loop |
| AD-4 | 분기 | 하네스를 정리하고 승격 판정을 자동화합니다 | L4 Harness Loop | L4 유지 + L5 Self-Evolving Harness 부분 도입 |

## 3. AD-1 — Day 1

Day 1에 도입하는 것은 **통합 verify 명령 하나**입니다. 다른 것을 먼저 만들지 않습니다.

사람에게는 IDE를 열면 즉시 보이는 것이 에이전트에게는 전혀 보이지 않습니다. Day 1의 목적은 에이전트에게 명확한 피드백 채널 하나를 주는 것입니다.

### 3.1 도입 산출물

| 산출물 | 내용 |
| --- | --- |
| [../scripts/verify.sh](../scripts/verify.sh) | 컴파일·테스트·lint·정적 분석을 한 명령으로 실행하고 결과를 집계합니다 |
| [../scripts/lib/detect-stack.sh](../scripts/lib/detect-stack.sh) | 언어 팩을 로드해 스택과 kind(frontend/backend)를 감지하고 기본 단계 집합을 정합니다 |
| [../language/README.md](../language/README.md) 의 `language/<언어>/lang.sh` | 언어별 감지 조건, 기본 단계, 보호 패턴. 대상 프로젝트의 언어 팩이 없으면 `language/_template` 로 먼저 만듭니다 |
| [../scripts/harness.config.example](../scripts/harness.config.example) | `HARNESS_STEPS` 로 프로젝트 고유 단계를 재정의합니다 |
| [../templates/AGENTS.md](../templates/AGENTS.md) 최소본 | 검증 명령이 무엇인지, 완료 선언 전에 무엇을 실행해야 하는지 한 절로 적습니다 |

verify가 실행하는 단계의 최소 구성입니다.

```text
Compile
 ↓
Unit Tests
 ↓
Integration Tests
 ↓
Architecture Tests
 ↓
Lint
 ↓
Static Analysis
```

프론트엔드 프로젝트라면 여기에 Type Check와 E2E Test를 더합니다. 어떤 채널부터 붙일지는 [agent-observability.md](agent-observability.md)의 우선순위표를 따르고, 언어·kind 별로 실제 명령이 채워진 단계 목록은 `language/<언어>/<kind>/harness.config.example` 을 씁니다.

### 3.2 완료 판정 기준

- 새로 합류한 사람이나 에이전트가 저장소 정보만으로 검증 명령 하나를 찾아 실행할 수 있습니다.
- 명령이 성공하면 종료 코드 0, 하나라도 필수 단계가 실패하면 0이 아닌 값을 돌려줍니다.
- 실행 후 `.harness/verify.json` 이 `harness.verify/1` 스키마로 생성되고, 실패한 단계의 `log` 경로에 원본 출력이 남습니다.
- `HARNESS_STEPS` 를 비운 상태에서도 스택 감지만으로 동작합니다.

```bash
./harness/scripts/verify.sh
echo "exit=$?"
cat .harness/verify.json
```

### 3.3 이 단계에서 하지 말아야 할 것

- 평가 점수, 가중치, 임계값을 도입하지 않습니다. 아직 채점할 증거가 축적되지 않았습니다.
- improvement log를 만들지 않습니다. 남길 실패의 근거가 되는 검증이 먼저 있어야 합니다.
- 검증 단계를 열 개 넘게 늘리지 않습니다. 실행 시간이 길어져 반복 자체가 죽습니다.
- 통과시키기 위해 기존 테스트나 lint 규칙을 약화하지 않습니다. 현재 실패는 그대로 두고 `required` 여부만 조정합니다.

## 4. AD-2 — Week 1

verify가 자리를 잡은 뒤, 명시적인 목표와 평가 기준으로 반복하게 만듭니다.

### 4.1 도입 산출물

| 산출물 | 내용 |
| --- | --- |
| [../scripts/eval.sh](../scripts/eval.sh) | 계층별 점수를 집계해 `.harness/latest-eval.json` 을 생성합니다 |
| [../scripts/pass-threshold.sh](../scripts/pass-threshold.sh) | `HARNESS_THRESHOLD` 기준으로 통과 여부를 판정합니다 |
| [../evaluation/rubric.md](../evaluation/rubric.md) | 6개 계층의 채점 기준을 고정합니다 |
| [../evaluation/tasks/representative.md](../evaluation/tasks/representative.md) | 대표 과제 집합을 만듭니다 |
| [../scripts/loop.sh](../scripts/loop.sh) | 반복 상태를 `.harness/loop-state.json` 에 남기고 종료 조건을 집행합니다 |
| [../skills/harness-verify/SKILL.md](../skills/harness-verify/SKILL.md) | Inner Loop 절차를 skill로 고정합니다 |
| [../rules/loop-budget.rule.md](../rules/loop-budget.rule.md) | 예산과 종료 조건을 규칙으로 명시합니다 |

이 단계에서 도입하는 평가 계층은 `correctness`, `quality` 중심입니다. `behavior` 가중치를 0이 아닌 값으로 두려면 해당 관측 채널을 먼저 확보해야 합니다.

반복 예산은 다음 값으로 시작합니다.

```bash
HARNESS_THRESHOLD=80
HARNESS_MAX_ITERATIONS=8
HARNESS_MAX_SAME_FAILURE=3
HARNESS_NO_IMPROVEMENT_ROUNDS=2
```

### 4.2 완료 판정 기준

- 하나의 목표를 주면 에이전트가 사람의 추가 지시 없이 verify 통과 또는 예산 소진까지 반복합니다.
- `.harness/latest-eval.json` 이 `harness.eval/1` 스키마로 생성되고 `score`, `threshold`, `pass`, `largest_failure` 가 채워집니다.
- 종료 조건 네 가지(최대 반복 8, 동일 실패 3회, 개선 없음 2라운드, 예산 초과)가 실제로 발동하는 것을 최소 한 번 관찰했습니다.
- 각 계층 점수가 `evidence` 로 파일 경로를 가집니다.

### 4.3 이 단계에서 하지 말아야 할 것

- 점수를 올리기 위해 가중치나 임계값을 조정하지 않습니다. 조정이 필요하다면 근거를 남기고 별도 변경으로 처리합니다.
- held-out 과제를 이 단계에서 노출하지 않습니다. 대표 과제만 사용합니다.
- 하네스 개선을 반복 안에서 하지 않습니다. 경계는 [inner-outer-loop.md](inner-outer-loop.md)의 IOB-1 ~ IOB-5 를 따릅니다.
- 종료 조건 없는 무한 반복을 허용하지 않습니다.

## 5. AD-3 — Month 1

실패가 시스템에 남게 만듭니다. 여기서부터 Outer Loop가 생기고, Self-Improving Loop라고 부를 수 있게 됩니다.

### 5.1 도입 산출물

| 산출물 | 내용 |
| --- | --- |
| [../improvement-log/README.md](../improvement-log/README.md), [../improvement-log/schema.md](../improvement-log/schema.md), [../improvement-log/_template.yaml](../improvement-log/_template.yaml) | improvement candidate 저장소와 스키마 |
| [../scripts/improvement-log.sh](../scripts/improvement-log.sh) | candidate 생성·조회·상태 전이 CLI |
| [../skills/harness-retro/SKILL.md](../skills/harness-retro/SKILL.md) | 작업 종료 후 회고 절차 |
| [../skills/harness-promote/SKILL.md](../skills/harness-promote/SKILL.md) | candidate 승격 절차 |
| [../rules/lesson-placement.rule.md](../rules/lesson-placement.rule.md), [../rules/promotion-gate.rule.md](../rules/promotion-gate.rule.md), [../rules/untrusted-experience.rule.md](../rules/untrusted-experience.rule.md), [../rules/harness-change-control.rule.md](../rules/harness-change-control.rule.md) | 배치·승격·신뢰 경계·변경 통제 규칙 |
| [../hooks/settings.hooks.json](../hooks/settings.hooks.json), [../hooks/stop-verify-gate.sh](../hooks/stop-verify-gate.sh) | 완료 선언 전 verify 강제 |
| [../evaluation/tasks/held-out.md](../evaluation/tasks/held-out.md) | 회귀 확인용 비공개 과제 집합 |
| [../subagents/harness-reviewer.md](../subagents/harness-reviewer.md), [../subagents/harness-evaluator.md](../subagents/harness-evaluator.md) | 생성과 평가를 분리합니다 |

작업이 끝날 때마다 다음 한 가지 질문을 추가합니다.

> 이번 작업에서 Agent가 겪은 문제 중 다음 작업을 위해 시스템에 남겨야 할 것은 무엇인가.

반복될 가능성이 높다면 다음 중 하나로 바꿉니다.

```text
Test
Rule
Documentation
Skill
Tool
```

### 5.2 완료 판정 기준

- 최근 한 달의 비싼 실패 각각에 대해 `improvement-log/` 에 대응하는 `id` 가 존재합니다.
- 최소 한 건이 `candidate` → `validating` → `promoted` 전이를 마쳤고, 그 건의 `regression_check` 가 개선 전에는 실패하고 개선 후에는 통과했음을 증거로 제시할 수 있습니다.
- 최소 한 건이 `rejected` 로 확정되었습니다. 전부 승격된다면 게이트가 동작하지 않는 것입니다.
- 승격된 규칙이 held-out 과제에서 회귀를 일으키지 않았습니다.
- 같은 지적을 사람이 두 번 이상 반복하는 빈도가 감소했습니다.

### 5.3 이 단계에서 하지 말아야 할 것

- 한 번의 회고에서 여러 하네스 변경을 동시에 승격하지 않습니다.
- 검증되지 않은 경험을 `trust: validated` 로 기록하지 않습니다.
- 모든 lesson을 AGENTS.md에 몰아 적지 않습니다. 배치 판단은 [lesson-placement.md](lesson-placement.md)를 따릅니다.
- held-out 과제를 개선 대상으로 삼지 않습니다. 그 순간 회귀 확인 수단이 사라집니다.
- `expires` 를 비워두지 않습니다. 만료 없는 규칙은 다음 단계에서 정리 대상이 됩니다.

## 6. AD-4 — 분기 단위

하네스가 쌓이면 하네스 자체가 비대해집니다. 분기마다 정리하고, 승격 판정의 일부를 자동화합니다.

### 6.1 도입 산출물

| 산출물 | 내용 |
| --- | --- |
| [../skills/harness-gardener/SKILL.md](../skills/harness-gardener/SKILL.md) | 낡은 규칙·문서·skill을 주기적으로 제거하는 절차 |
| [../rules/harness-gc.rule.md](../rules/harness-gc.rule.md) | 제거 판정 기준 |
| [../rules/context-hygiene.rule.md](../rules/context-hygiene.rule.md) | AGENTS.md / CLAUDE.md 비대화 방지 |
| [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) | 평가 조작 탐지 |
| [../hooks/guard-evaluation-tampering.sh](../hooks/guard-evaluation-tampering.sh) | 평가 산출물 무단 변경 차단 |
| [generator-evaluator.md](generator-evaluator.md) 기반 분리 운영 | 개선안 생성자와 평가자를 다른 주체로 고정 |
| [source-mapping.md](source-mapping.md) 갱신 | 하네스 요소와 근거의 대응 유지 |

### 6.2 완료 판정 기준

- 분기마다 만료된 규칙·문서·skill이 실제로 제거되었고, 제거 근거가 기록에 남아 있습니다.
- AGENTS.md와 CLAUDE.md의 분량이 지난 분기 대비 증가하지 않았거나, 증가분에 대한 근거가 있습니다.
- candidate의 승격·기각 판정 중 일정 비율이 사람의 개입 없이 게이트만으로 확정됩니다.
- 평가 조작 시도(테스트 약화, 임계값 하향, 판정 우회)가 자동으로 차단되거나 최소한 탐지됩니다.
- 하네스 요소 중 지난 분기에 한 번도 참조되지 않은 항목 목록을 제시할 수 있습니다.

### 6.3 이 단계에서 하지 말아야 할 것

- 자동 승격 범위를 한 번에 넓히지 않습니다. 저위험 유형부터 좁게 허용합니다.
- 생성자와 평가자를 같은 주체로 되돌리지 않습니다.
- 정리를 이유로 아직 만료되지 않은 규칙을 일괄 삭제하지 않습니다.
- L5 자동화를 이유로 L3의 회귀 검증을 건너뛰지 않습니다.

## 7. 안티패턴

다음 세 가지를 초기에 도입하는 것은 안티패턴으로 규정합니다. 어느 것도 AD-1 ~ AD-2 단계의 산출물이 될 수 없습니다.

| ID | 안티패턴 | 왜 안티패턴인가 | 대신 무엇을 하는가 |
| --- | --- | --- | --- |
| AD-A1 | Vector DB를 붙여 이전 경험을 기억하게 만들기 | 평가 없이 Memory부터 만들면 에이전트가 잘못 판단했던 경험까지 정확히 기억합니다. 그것은 개선이 아닙니다. 순서는 Execution → Evaluation → Evidence → Diagnosis → Lesson → Memory 입니다 | AD-1의 verify와 AD-2의 eval을 먼저 세웁니다. Memory는 AD-3의 `improvement-log/` 로 시작하며, 그것도 승격된 lesson만 담습니다 |
| AD-A2 | 자동 Skill Generator 도입 | 무엇이 반복되는 작업인지에 대한 근거가 아직 없습니다. 근거 없이 생성된 skill은 검증되지 않은 지침이 되어 컨텍스트만 오염시키고, 제거 기준도 없습니다 | AD-3까지 회고 기록을 쌓아 반복 패턴을 실제 데이터로 확인한 뒤, 사람이 승격 게이트를 거쳐 skill을 만듭니다 |
| AD-A3 | 멀티에이전트 시스템 구축 | 단일 에이전트조차 자기 결과를 관측하지 못하는 상태에서 에이전트를 늘리면 관측 불가능한 실패가 배수로 늘어납니다. 협업 구조가 아니라 관측 결손이 병목입니다 | AD-1 ~ AD-3을 마친 뒤, AD-4에서 생성자·평가자 분리라는 최소한의 역할 분리부터 도입합니다 |

세 안티패턴의 공통 오류는 동일합니다. **평가와 관측이 없는 상태에서 기억과 자동화를 먼저 만드는 것**입니다. Self-Improving Loop의 중심은 Memory가 아니라 Evaluation입니다.

## 8. 성숙도 대응

| 단계 | 대응 성숙도 | 그 단계에서 성립하는 것 |
| --- | --- | --- |
| AD-1 Day 1 | L0 Prompting → L1 Agent Loop | 에이전트가 Code → Test → Fix를 스스로 반복합니다. 사람이 매번 다음 작업을 지시하지 않습니다 |
| AD-2 Week 1 | L1 Agent Loop → L2 Eval Loop | 명시적인 Goal과 Evaluation을 기준으로 반복합니다. 종료 조건이 규칙으로 존재합니다 |
| AD-3 Month 1 | L2 Eval Loop → L3 Persistent Learning → L4 Harness Loop | 실패가 Test, Docs, Skill, Tool로 남고(L3), 작업 기록을 분석해 하네스 개선안을 만듭니다(L4) |
| AD-4 분기 | L4 Harness Loop 유지 + L5 Self-Evolving Harness 부분 도입 | Candidate Harness를 평가해 자동으로 Promote/Reject 합니다. 전면 자동화가 아니라 저위험 유형부터 좁게 적용합니다 |

L5부터 만들 필요는 없습니다. L3와 L4를 제대로 만드는 것이 훨씬 중요합니다. 계층별 정의는 [maturity-levels.md](maturity-levels.md)를 참조합니다.

## 9. 도입 후 확인

각 단계를 마칠 때마다 다음 질문으로 확인합니다.

> 오늘 Agent가 저지른 실수 때문에, 내일 같은 종류의 작업을 하는 Agent가 실제로 더 잘하게 되는가.

AD-1과 AD-2에서는 이 질문의 답이 "아니오"인 것이 정상입니다. 그 단계의 목표는 현재 작업을 끝까지 해내는 것이기 때문입니다. AD-3부터는 "그렇다"여야 하며, 근거는 [inner-outer-loop.md](inner-outer-loop.md) 6장의 세 가지 요건으로 제시합니다.

이 습관이 쌓이면 모델이 같아도 몇 달 뒤의 개발 환경은 처음과 상당히 달라집니다. 에이전트가 프로젝트를 더 잘 이해하고, 실수하기 쉬운 곳에 자동화된 guardrail이 생기고, 반복되던 작업에는 skill과 tool이 생기고, 실패하기 쉬운 곳에는 test가 생깁니다. 그리고 사람이 같은 설명을 반복하지 않게 됩니다.

## 관련 문서

- [maturity-levels.md](maturity-levels.md) — L0~L5 정의
- [inner-outer-loop.md](inner-outer-loop.md) — 각 단계에서 세워지는 두 루프의 경계
- [agent-observability.md](agent-observability.md) — AD-1의 채널 확보 우선순위
- [evaluation-layers.md](evaluation-layers.md) — AD-2의 평가 계층
- [lesson-placement.md](lesson-placement.md) — AD-3의 배치 판단
- [generator-evaluator.md](generator-evaluator.md) — AD-4의 역할 분리
- [harness-elements.md](harness-elements.md) — HE-1 ~ HE-15 인벤토리
- [../rules/RULES.md](../rules/RULES.md) — 도입 단계별로 활성화되는 규칙 목록
