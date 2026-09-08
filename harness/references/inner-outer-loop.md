# Inner Loop와 Outer Loop

이 문서는 하네스를 설계하거나 점검할 때, 지금 돌고 있는 반복이 "현재 작업을 끝내는 반복"인지 "다음 작업을 더 잘하게 만드는 반복"인지 판별해야 하는 시점에 읽습니다. 두 반복의 단계·진입 조건·종료 조건·산출 증거를 고정하고, 둘 사이에 넘지 말아야 할 경계를 규정합니다. 반복 예산의 구체적 수치는 [../rules/loop-budget.rule.md](../rules/loop-budget.rule.md), 성숙도 대응은 [maturity-levels.md](maturity-levels.md)를 함께 읽습니다.

## 1. Agent Loop / Ralph Loop / Self-Improving Loop 구분

세 가지는 모두 반복이지만 개선 대상이 다릅니다. 반복 횟수는 개선의 증거가 아닙니다.

| 구분 | 무엇을 반복하는가 | 무엇이 개선되는가 | 종료 조건 | 다음 실행의 시작 상태가 나아지는가 |
| --- | --- | --- | --- | --- |
| Agent Loop | Read → Implement → Test → Analyze → Fix | 현재 작업의 코드 | 테스트가 통과하거나 에이전트가 스스로 완료를 선언할 때 | 나아지지 않습니다. 어제의 시행착오가 오늘의 에이전트에 남지 않습니다 |
| Ralph Loop | 목표가 만족될 때까지 에이전트 실행 자체를 반복 | 현재 작업의 완주율. 사람이 매번 다음 명령을 내리는 비용이 제거됩니다 | 목표 만족 판정이 참이 될 때. 예산·최대 반복 수를 함께 두지 않으면 종료하지 않습니다 | 나아지지 않습니다. 101번째 실행은 1번째 실행과 같은 상태에서 시작합니다 |
| Self-Improving Loop | Inner Loop 1회분 + 작업 종료 후의 Outer Loop | 작업 시스템(하네스) 자체. 테스트·규칙·문서·skill·tool이 남습니다 | Inner Loop는 verify 통과 또는 예산 소진, Outer Loop는 candidate가 promoted 또는 rejected로 확정될 때 | 나아집니다. 승격된 개선이 다음 작업의 시작 상태를 바꿉니다 |

핵심 구분은 다음 한 줄입니다. Agent Loop와 Ralph Loop는 **현재 작업**을 개선하고, Self-Improving Loop는 **작업 시스템**을 개선합니다. 하네스에 Outer Loop가 없다면, 아무리 정교한 Ralph Loop를 갖추었더라도 그 프로젝트는 Self-Improving Loop를 갖춘 것이 아닙니다.

## 2. Inner Loop 정의

현재 작업을 성공시키기 위한 반복입니다.

### 2.1 단계

| ID | 단계 | 수행 내용 |
| --- | --- | --- |
| IL-1 | Scope | 작업 목표를 하나로 좁히고, 통과 기준을 verify 단계 집합으로 확정합니다 |
| IL-2 | Implement | 목표를 향한 변경을 적용합니다 |
| IL-3 | Verify | `scripts/verify.sh` 를 실행하고 `.harness/verify.json` 을 생성합니다 |
| IL-4 | Judge | `verify.json` 의 `status` 가 `pass` 면 Inner Loop를 종료합니다 |
| IL-5 | Evidence | 실패한 step의 `log` 경로에서 실제 출력을 읽습니다. 추측으로 원인을 정하지 않습니다 |
| IL-6 | Select | 실패 중 가장 큰 문제 하나를 선택합니다. 여러 실패를 동시에 고치지 않습니다 |
| IL-7 | Focused Change | 선택한 문제 하나만 겨냥해 수정합니다 |
| IL-8 | Budget Check | `.harness/loop-state.json` 을 갱신하고 종료 조건을 점검한 뒤 IL-3 으로 돌아갑니다 |

### 2.2 진입 조건

- 작업 목표가 하나로 정해져 있습니다.
- 통합 verify 명령이 존재하고 단독 실행으로 종료 코드를 돌려줍니다.
- 변경 대상 작업 트리가 깨끗하거나, 진행 중 변경이 이번 작업 범위로 한정되어 있습니다.

### 2.3 종료 조건

`status` 가 `pass` 인 경우 성공 종료입니다. 그 외에는 [../rules/loop-budget.rule.md](../rules/loop-budget.rule.md)의 종료 조건에 따라 중단합니다.

- Maximum Iterations = 8
- 동일 실패 3회 → 중단
- 2라운드 연속 개선 없음 → 중단
- 보안 민감 변경 → 사람 검토로 에스컬레이션
- 예산 초과 → 중단

중단 종료도 정상적인 종료입니다. 중단은 실패가 아니라 Outer Loop의 입력입니다.

### 2.4 산출 증거

| 경로 | 내용 |
| --- | --- |
| `.harness/verify.json` | 단계별 `status`, `exit_code`, `duration_ms`, `log` 경로 |
| `.harness/logs/<step-id>.log` | 각 단계의 원본 출력 |
| `.harness/loop-state.json` | 반복 횟수, 동일 실패 누적 횟수, 개선 없는 라운드 수 |

증거 없이 "고쳤습니다"라고 선언하지 않습니다. 판단의 근거는 위 세 파일에 남아 있어야 합니다.

### 2.5 담당 산출물

- [../skills/harness-verify/SKILL.md](../skills/harness-verify/SKILL.md) — IL-3 ~ IL-7 의 절차
- [../scripts/verify.sh](../scripts/verify.sh) — 통합 검증 명령
- [../scripts/loop.sh](../scripts/loop.sh) — IL-8 의 반복 상태 관리와 종료 조건 집행

## 3. Outer Loop 정의

미래의 작업을 더 잘하기 위한 반복입니다. Self-Improving Loop의 핵심은 이쪽입니다.

### 3.1 단계

| ID | 단계 | 수행 내용 |
| --- | --- | --- |
| OL-1 | Enter | 작업이 끝난 시점에 진입합니다. 성공 종료와 예산 소진 중단 모두 진입 대상입니다 |
| OL-2 | Retrospective | 이번 작업에서 비쌌던 실패를 열거하고 `symptom` 과 `evidence` 를 확정합니다 |
| OL-3 | Diagnose | 표면 증상이 아니라 그 실수를 만들어낸 시스템의 결손을 `root_cause` 로 적습니다 |
| OL-4 | Assess | `recurrence_risk` 를 `low` / `medium` / `high` 로 판정합니다. `low` 는 기록하고 종료합니다 |
| OL-5 | Draft | improvement candidate YAML을 `improvement-log/` 에 `status: candidate` 로 생성합니다 |
| OL-6 | Place | `harness_element` 와 `preferred_enforcement` 를 정합니다. 배치 판단은 [lesson-placement.md](lesson-placement.md)를 따릅니다 |
| OL-7 | Regression | `regression_check` 를 정의합니다. 개선 전에 실패하고 개선 후에 통과하는 검증이어야 합니다 |
| OL-8 | Promote | 승격 게이트를 통과하면 `promoted`, 실패하면 `rejected` 로 확정합니다 |

### 3.2 진입 조건

Outer Loop는 작업 완료 시점에 진입합니다. 다음 중 하나라도 해당하면 진입합니다.

- Inner Loop가 `pass` 로 종료했습니다.
- Inner Loop가 종료 조건에 걸려 중단했습니다.
- 사람이 에이전트의 결과를 되돌리거나 크게 손봤습니다.
- 같은 지적을 이번 작업에서 두 번 이상 반복했습니다.

작업 중간에는 진입하지 않습니다. 진입 시점을 흐리면 4장의 경계 규칙을 지킬 수 없습니다.

### 3.3 산출물

Outer Loop의 산출물은 코드가 아니라 **improvement candidate** 입니다. 스키마는 [../improvement-log/schema.md](../improvement-log/schema.md)에 고정되어 있으며, 필수 키 순서는 다음과 같습니다.

```yaml
id: 2026-08-09-001
date: 2026-08-09
status: candidate
symptom: ""
evidence: ""
root_cause: ""
fix: ""
recurrence_risk: medium
harness_element: HE-5
proposed_harness_change: ""
preferred_enforcement: test
trust: untrusted
regression_check: ""
owner: ""
expires: none
```

새로 만들어진 candidate의 `trust` 는 항상 `untrusted` 입니다. 검증을 통과하기 전의 경험은 학습 결과가 아닙니다. 자세한 근거는 [../rules/untrusted-experience.rule.md](../rules/untrusted-experience.rule.md)에 있습니다.

### 3.4 담당 산출물

- [../skills/harness-retro/SKILL.md](../skills/harness-retro/SKILL.md) — OL-2 ~ OL-7 의 절차
- [../skills/harness-promote/SKILL.md](../skills/harness-promote/SKILL.md) — OL-8 의 승격 판정
- [../rules/promotion-gate.rule.md](../rules/promotion-gate.rule.md) — 승격 게이트 조건
- [../improvement-log/README.md](../improvement-log/README.md) — candidate 저장 규약

## 4. 경계 규칙

| ID | 규칙 |
| --- | --- |
| IOB-1 | Inner Loop 안에서는 하네스를 바꾸지 않습니다. 변경 대상은 작업 코드뿐입니다 |
| IOB-2 | 하네스 변경은 Outer Loop에서만 합니다. AGENTS.md, CLAUDE.md, rules, skills, hooks, verify 단계 정의, 평가 가중치, 임계값이 모두 하네스입니다 |
| IOB-3 | Inner Loop 중 하네스 결손을 발견하면 고치지 말고 관찰만 기록합니다. 기록은 Outer Loop의 `evidence` 로 넘깁니다 |
| IOB-4 | Outer Loop에서는 하네스만 바꿉니다. 작업 코드 수정과 하네스 개선을 같은 변경에 섞지 않습니다 |
| IOB-5 | 한 번의 Outer Loop는 하나의 하네스 변경만 승격합니다. 근거는 [../rules/harness-change-control.rule.md](../rules/harness-change-control.rule.md)입니다 |

### 4.1 이유

verify가 실패했을 때 실패한 검증 자체를 고치면 통과는 즉시 만들어집니다. 그러나 그 통과는 코드가 좋아져서 생긴 것이 아니라 기준이 낮아져서 생긴 것입니다. Inner Loop는 통과를 목표로 최적화되는 구간이므로, 이 구간에 하네스 편집 권한을 함께 주면 기준을 낮추는 쪽이 언제나 더 싼 해결책이 됩니다. 평가 조작의 구체적 유형은 [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md)에 있습니다.

또한 코드 변경과 하네스 변경이 한 반복 안에 섞이면 개선의 귀속이 사라집니다. 점수가 올랐을 때 코드가 좋아진 것인지, 기준이 헐거워진 것인지, 새 규칙이 효과를 낸 것인지 구분할 수 없습니다.

### 4.2 위반 시 증상

| 증상 | 관찰되는 형태 |
| --- | --- |
| 귀속 소실 | 무엇 때문에 좋아졌는지 설명할 수 없습니다. 개선을 되돌릴 수도, 다른 프로젝트로 옮길 수도 없습니다 |
| 기준 침식 | verify는 늘 통과하는데 실제 결함은 줄지 않습니다. `HARNESS_THRESHOLD` 나 `required` 플래그가 조용히 낮아져 있습니다 |
| 회귀 검증 무력화 | `regression_check` 가 개선 전에도 통과합니다. 검증이 개선을 증명하지 못합니다 |
| 잘못된 학습의 고착 | 한 번의 우연한 성공이 규칙으로 굳어 다음 작업 전체를 잘못된 방향으로 끌고 갑니다 |

위반이 확인되면 해당 하네스 변경을 되돌리고, 같은 내용을 improvement candidate로 다시 제출해 Outer Loop를 거치게 합니다.

## 5. 흐름도

```text
                         ┌──────────────────────────────────────────┐
                         │              INNER LOOP                  │
                         │      (현재 작업을 성공시킨다)              │
                         │                                          │
   Task ─────────────────┼──→ IL-1 Scope                            │
                         │        ↓                                 │
                         │     IL-2 Implement                       │
                         │        ↓                                 │
                         │     IL-3 Verify ──→ .harness/verify.json │
                         │        ↓                                 │
                         │     IL-4 Judge                           │
                         │        ├── pass ─────────────────────────┼──→ 작업 종료
                         │        │                                 │        │
                         │        └── fail                          │        │
                         │             ↓                            │        │
                         │          IL-5 Evidence                   │        │
                         │             ↓                            │        │
                         │          IL-6 Select (문제 1개)           │        │
                         │             ↓                            │        │
                         │          IL-7 Focused Change             │        │
                         │             ↓                            │        │
                         │          IL-8 Budget Check               │        │
                         │             ├── 예산 남음 ──→ IL-3        │        │
                         │             └── 종료 조건 ────────────────┼──→ 중단 종료
                         │                                          │        │
                         │  ※ 이 상자 안에서 하네스를 바꾸지 않습니다   │        │
                         └──────────────────────────────────────────┘        │
                                                                             │
                              [접점 A] 작업 완료 시점 + 증거 인계              │
                              verify.json / logs / loop-state.json  ←─────────┘
                                             │
                         ┌───────────────────┼──────────────────────┐
                         │              OUTER LOOP                  │
                         │      (다음 작업을 더 잘하게 만든다)         │
                         │                   ↓                      │
                         │            OL-1 Enter                    │
                         │                   ↓                      │
                         │            OL-2 Retrospective            │
                         │                   ↓                      │
                         │            OL-3 Diagnose (root cause)    │
                         │                   ↓                      │
                         │            OL-4 Assess (recurrence_risk) │
                         │              ├── low ──→ 기록만 하고 종료  │
                         │              └── medium / high           │
                         │                   ↓                      │
                         │            OL-5 Draft candidate          │
                         │                   ↓      improvement-log/│
                         │            OL-6 Place (element/enforce)  │
                         │                   ↓                      │
                         │            OL-7 Regression check         │
                         │                   ↓                      │
                         │            OL-8 Promote / Reject         │
                         │                   │                      │
                         │  ※ 이 상자 안에서 작업 코드를 바꾸지 않습니다 │
                         └───────────────────┼──────────────────────┘
                                             │
                              [접점 B] 승격된 변경이 하네스에 반영됨
                              rules / skills / tests / hooks / docs
                                             │
                                             ↓
                                     다음 Task 의 시작 상태
```

접점은 두 곳뿐입니다. 접점 A에서는 증거만 넘어가고, 접점 B에서는 승격된 하네스 변경만 넘어옵니다. 그 외의 경로로 두 루프가 서로에게 영향을 주지 않습니다.

## 6. 판정 질문

Outer Loop가 실제로 존재하는지는 다음 한 문장으로 판정합니다.

> 오늘 Agent가 저지른 실수 때문에, 내일 같은 종류의 작업을 하는 Agent가 실제로 더 잘하게 되는가.

이 질문에 다음 세 가지를 모두 제시할 수 있어야 "그렇다"입니다.

| 요건 | 확인 방법 |
| --- | --- |
| 실수가 기록으로 남았는가 | `improvement-log/` 에 해당 실수에 대응하는 `id` 를 가진 파일이 있습니다 |
| 기록이 집행 가능한 형태로 바뀌었는가 | `preferred_enforcement` 가 `test` / `lint` / `arch-rule` / `hook` / `script` / `skill` / `subagent` 중 하나이고 실제 산출물이 존재합니다. `doc` 또는 `instruction` 만 있는 경우 집행되지 않을 수 있으므로 근거를 별도로 밝힙니다 |
| 좋아졌다는 것이 증명되었는가 | `regression_check` 가 개선 전에는 실패하고 개선 후에는 통과합니다 |

세 가지 중 하나라도 제시할 수 없으면 그 프로젝트에는 Inner Loop만 있는 것으로 판정합니다. 이 경우 다음 행동은 하네스를 더 정교하게 만드는 것이 아니라, [harness-adoption.md](harness-adoption.md)의 Day 1 단계로 돌아가 통합 verify와 improvement log부터 세우는 것입니다.

판정 주기는 작업 단위가 아니라 회고 단위입니다. 개별 작업마다 하네스가 바뀔 필요는 없습니다. `recurrence_risk` 가 `low` 인 실수는 기록만 남기고 종료하는 것이 정상입니다.

## 관련 문서

- [maturity-levels.md](maturity-levels.md) — L0~L5 중 Inner Loop는 L1, Outer Loop는 L4 이상에 대응합니다
- [harness-adoption.md](harness-adoption.md) — 두 루프를 언제 도입하는지의 순서
- [agent-observability.md](agent-observability.md) — Inner Loop의 IL-5 증거가 부족할 때 무엇을 보강하는지
- [evaluation-layers.md](evaluation-layers.md) — verify 단계와 평가 계층의 대응
- [lesson-placement.md](lesson-placement.md) — OL-6 배치 판단
- [../rules/loop-budget.rule.md](../rules/loop-budget.rule.md) — Inner Loop 종료 조건
- [../rules/harness-change-control.rule.md](../rules/harness-change-control.rule.md) — IOB-5 의 근거
- [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) — IOB-1 위반의 대표 사례
