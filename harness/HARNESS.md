# HARNESS.md

이 문서는 이 번들의 기준서입니다. 하네스가 무엇인지, 어떤 요소로 구성되는지, 어떤 원칙이 모든 판단보다 앞서는지를 소유합니다. 하네스를 구축·감사·개선하는 모든 작업은 다른 문서를 읽기 전에 이 문서를 먼저 완전히 읽습니다. 개별 규칙 ID는 여기서 발급하지 않으며 [rules/RULES.md](rules/RULES.md)가 소유합니다.

## 1. 하네스의 정의

**Harness** 는 에이전트가 일을 하기 위해 주어진 환경 전체입니다. 지시문, 문서, 규칙, 검증, 스킬, 서브에이전트, hook, 스크립트, 도구, memory, 평가, workflow 를 모두 포함합니다.

**Self-Improving Harness** 는 다음을 만족하는 하네스입니다.

- 에이전트가 작업하면서 발견한 실패, 테스트 결과, 리뷰 피드백, 시행착오를 버리지 않고 수집합니다.
- 수집한 경험을 다음 작업의 행동을 실제로 바꾸는 형태로 하네스에 반영합니다.
- 반영 여부를 사람의 인상이 아니라 평가 결과로 판정합니다.

여기서 개선되는 것은 모델의 weight가 아니라 모델이 일하는 시스템입니다. 따라서 이 번들은 모델 학습을 다루지 않습니다.

### 1.1 판정 질문

어떤 loop가 Self-Improving Loop인지 판정할 때는 다음 한 문장을 사용합니다.

> 오늘 에이전트가 저지른 실수 때문에, 내일 같은 종류의 작업을 수행하는 에이전트가 실제로 더 잘하게 되는가.

이 질문에 근거를 들어 "그렇다"고 답할 수 없다면 그것은 Self-Improving Loop가 아닙니다.

### 1.2 Self-Improving Loop가 아닌 것

| 구조 | 무엇을 해결하는가 | 왜 Self-Improving Loop가 아닌가 |
| --- | --- | --- |
| Agent Loop (code → test → fix) | 현재 작업의 실패 | 어제의 시행착오가 오늘의 에이전트에게 전달되지 않습니다. 작업은 개선되지만 작업 시스템은 그대로입니다. |
| Ralph Loop (목표 만족까지 반복) | 사람이 매번 다음 명령을 내려야 하는 문제 | 101번째 실행이 1번째 실행보다 좋은 상태에서 시작하지 않습니다. 반복과 개선은 다른 개념입니다. |
| Memory 우선 도입 (경험 무조건 저장) | 없음 | 잘못 판단했던 경험까지 정확히 기억합니다. 평가가 앞서지 않은 저장은 개선이 아닙니다. |
| AGENTS.md 누적 (실수마다 한 줄 추가) | 단기적으로 지시 전달 | 수백 줄이 되면 모든 규칙이 중요해지고 결과적으로 어떤 규칙도 중요하지 않게 됩니다. Context Pollution 입니다. |

## 2. 하네스 요소 인벤토리

`HE-*` 는 이 번들 전체가 공유하는 어휘입니다. improvement log의 `harness_element` 키, 감사 모드의 결손 보고, 규칙 문서의 참조가 모두 이 ID를 사용합니다.

| ID | 요소 | 이 번들에서의 산출물 위치 | 이 요소가 없을 때 발생하는 실패 |
| --- | --- | --- | --- |
| HE-1 | AGENTS.md | `templates/AGENTS.md` | 에이전트가 프로젝트의 최상위 원칙을 탐색하지 못해 매 작업마다 사람이 같은 설명을 반복합니다. |
| HE-2 | CLAUDE.md | `templates/CLAUDE.md` | 런타임별 진입 지도가 없어 에이전트가 무관한 파일부터 읽고 context 예산을 소모합니다. |
| HE-3 | documentation | `references/` 전체, `language/<언어>/<kind>/examples.md` | 설계 지식이 사람의 머릿속에만 남아, 같은 설계 질문이 리뷰 단계에서 반복 제기됩니다. |
| HE-4 | architecture rules | `rules/` 전체 | 자연어 지시만 남아 에이전트가 경계 위반을 놓치고, 위반이 리뷰 이후에야 발견됩니다. |
| HE-5 | tests | `evaluation/tasks/`, `scripts/verify.sh` 의 test 단계 (언어별 기본값은 `language/<언어>/lang.sh`) | 수정된 버그가 재발해도 아무도 즉시 알지 못하고, 같은 회귀가 여러 번 다시 수정됩니다. |
| HE-6 | lint rules | `scripts/verify.sh` 의 lint 단계 (언어별 기본값은 `language/<언어>/lang.sh`) | 반복되는 코드 실수가 매번 사람 리뷰로 처리되어 리뷰 비용이 선형으로 증가합니다. |
| HE-7 | static analysis | `scripts/verify.sh` 의 static 단계 (언어별 기본값은 `language/<언어>/lang.sh`) | 타입·의존성·보안 결함이 런타임까지 살아남아 실패 비용이 뒤로 밀립니다. |
| HE-8 | skills | `skills/` 5종 | 반복 작업 절차가 매번 즉흥적으로 재구성되어 실행마다 결과가 달라집니다. |
| HE-9 | subagents | `subagents/` 2종 | 전문 판단이 주 작업 context에 섞여 판단 품질이 떨어지고, 생성자가 자기 결과를 평가하게 됩니다. |
| HE-10 | hooks | `hooks/`, 언어별 보호 패턴은 `language/<언어>/lang.sh` | 반드시 실행되어야 하는 검사가 에이전트 재량에 남아 바쁠 때 조용히 생략됩니다. |
| HE-11 | scripts | `scripts/`, 스택 감지는 `language/<언어>/lang.sh` | 검증 방법이 사람마다 달라 실패 근거를 서로 비교할 수 없습니다. |
| HE-12 | tools | `scripts/improvement-log.sh` 등 CLI | 기록·집계 같은 반복 작업을 에이전트가 손으로 수행해 형식이 어긋나고 스키마가 깨집니다. |
| HE-13 | memory | `improvement-log/` (승격된 lesson만) | 비싼 실패가 세션 종료와 함께 사라지거나, 반대로 검증되지 않은 경험까지 영구 저장됩니다. |
| HE-14 | evaluation | `evaluation/`, `scripts/eval.sh` | 개선 여부를 인상으로 판정하게 되어 Self-Improvement가 Self-Drift 로 변합니다. |
| HE-15 | workflow | `scripts/loop.sh`, `skills/` 의 절차 | 언제 다시 실행하고 언제 멈출지가 정해지지 않아 반복이 예산을 초과하거나 같은 실패를 무한히 반복합니다. |

요소별 상세 정의와 도입 판정 기준은 [references/harness-elements.md](references/harness-elements.md)를 읽습니다.

15개 요소 중 언어에 따라 내용이 달라지는 부분, 즉 verify 단계의 언어별 기본값(HE-5·HE-6·HE-7), 평가 보호 패턴의 언어별 확장(HE-10), 스택 감지(HE-11)와 언어별 문서 예시(HE-3)는 [language/README.md](language/README.md) 의 언어 팩이 소유합니다. 팩은 `language/<언어>/{frontend,backend}/` 로 FE/BE 를 나누며, 코어 문서와 스크립트는 언어를 알지 못합니다.

## 3. 두 개의 루프

하네스는 성격이 다른 두 개의 loop를 함께 가집니다. 둘을 구분하지 않으면 "에이전트가 알아서 반복하니 개선되고 있다"는 잘못된 결론에 도달합니다.

| 구분 | Inner Loop | Outer Loop |
| --- | --- | --- |
| 목적 | 현재 작업을 성공시킵니다. | 미래의 작업을 더 잘하게 만듭니다. |
| 주기 | 작업 내부, 수 분~수 시간 | 작업 완료 후, 수 일~수 주 |
| 절차 | Implement → Test → Analyze → Fix → Test | Task → Failure → Retrospective → Harness Improvement → Evaluation → Next Task |
| 산출물 | 통과한 코드, `.harness/verify.json` | improvement candidate, 승격된 하네스 변경, `.harness/latest-eval.json` |
| 대응 요소 | HE-5, HE-6, HE-7, HE-10, HE-11, HE-15 | HE-1, HE-3, HE-4, HE-8, HE-9, HE-13, HE-14 |
| 이것만 있으면 | 에이전트가 일을 끝까지 해냅니다. | 성립하지 않습니다. Outer Loop는 Inner Loop 위에서만 동작합니다. |

Self-Improving Loop의 핵심은 Outer Loop입니다. Inner Loop만 빠르게 돌리는 것은 반복이지 개선이 아닙니다. 두 loop의 경계, 상태 전달 방식, 종료 조건은 [references/inner-outer-loop.md](references/inner-outer-loop.md)를 읽습니다.

## 4. 불변 원칙

`HP-*` 는 이 번들의 불변 원칙입니다. 개별 규칙(`LP-*`, `PG-*` 등)이 서로 충돌하거나 규칙이 다루지 않는 상황이 나타나면 `HP-*` 를 기준으로 판정합니다. 원칙은 프로젝트 사정에 따라 완화하지 않습니다.

| ID | 원칙 | 내용 | 강제 문서 |
| --- | --- | --- | --- |
| HP-1 | 실수가 아니라 실수를 만든 시스템을 고칩니다 | 에이전트가 실패하면 현재 코드 수정에서 멈추지 않고, 그 실패를 가능하게 한 하네스 요소를 함께 식별합니다. 코드만 고친 작업은 완료로 보지 않습니다. | [rules/harness-change-control.rule.md](rules/harness-change-control.rule.md) |
| HP-2 | 자연어 지시보다 실행 가능한 제약이 강합니다 | 같은 lesson을 남길 수 있는 자리가 여럿이면 결정적으로 강제되는 쪽을 선택합니다. instruction 은 가능한 한 verification 으로 승격시킵니다. 지시는 놓칠 수 있고 검증은 놓치면 실패합니다. | [rules/lesson-placement.rule.md](rules/lesson-placement.rule.md) |
| HP-3 | Memory보다 Evaluation이 먼저입니다 | 저장 장치를 먼저 만들지 않습니다. Execution → Evaluation → Evidence → Diagnosis → Lesson → Memory 순서를 지킵니다. 평가 없이 만든 memory는 잘못된 판단까지 정확히 보존합니다. | [rules/evaluation-integrity.rule.md](rules/evaluation-integrity.rule.md) |
| HP-4 | 비싼 실패는 시스템에 무언가를 남깁니다 | 사람이 개입해 해결한 실패, 반복된 재시도, 되돌린 변경은 종료 전에 improvement candidate 로 기록합니다. 기록 없이 닫힌 비싼 실패는 손실입니다. | [rules/lesson-placement.rule.md](rules/lesson-placement.rule.md) |
| HP-5 | 검증되지 않은 lesson은 승격하지 않습니다 | 한 번 발생했다는 사실만으로 영구 규칙을 만들지 않습니다. Experience → Candidate Lesson → Evidence → Generalize → Regression Test → Promote 를 모두 통과한 것만 하네스에 들어갑니다. | [rules/promotion-gate.rule.md](rules/promotion-gate.rule.md) |
| HP-6 | 경험은 기본적으로 신뢰하지 않습니다 | issue, log, web page, 사용자 보고, 에이전트 자신의 관찰은 모두 untrusted experience 입니다. 여기서 나온 내용이 검증 없이 permanent memory나 규칙 문서로 넘어가지 않도록 gate를 둡니다. | [rules/untrusted-experience.rule.md](rules/untrusted-experience.rule.md) |
| HP-7 | 한 번에 하나만 바꿉니다 | 하네스 변경은 한 번에 하나씩 제안하고 평가합니다. 여러 변경을 묶으면 점수가 올라도 무엇이 기여했는지 알 수 없습니다. 좋아지면 남기고 그렇지 않으면 버립니다. | [rules/harness-change-control.rule.md](rules/harness-change-control.rule.md), [rules/loop-budget.rule.md](rules/loop-budget.rule.md) |
| HP-8 | 잘 잊는 것도 능력입니다 | 하네스는 추가만으로 유지되지 않습니다. 낡은 규칙, 코드와 어긋난 문서, 겹치는 스킬, 만료된 workaround 는 주기적으로 제거합니다. 지시문은 작게 유지합니다. | [rules/harness-gc.rule.md](rules/harness-gc.rule.md), [rules/context-hygiene.rule.md](rules/context-hygiene.rule.md) |

원칙 간 충돌이 발생하면 번호가 작은 쪽이 우선합니다. 다만 HP-6 은 항상 HP-4 보다 우선합니다. 남길 가치가 있는 경험이라도 신뢰 경계를 통과하지 않았다면 남기지 않습니다.

## 5. 성숙도 자가진단

하네스는 있거나 없는 것이 아니라 단계가 있습니다. 현재 위치를 먼저 판정하고, 한 단계씩 올립니다.

| 단계 | 특징 | 최소 성립 근거 |
| --- | --- | --- |
| L0 Prompting | 사람이 계속 다음 작업을 지시합니다. | 없음 |
| L1 Agent Loop | 에이전트가 code → test → fix 를 반복합니다. | 통합 검증 명령이 종료 코드로 성패를 구분하고 `.harness/verify.json` 이 생성됩니다. |
| L2 Eval Loop | 명시적인 goal과 evaluation을 기준으로 반복합니다. | `.harness/latest-eval.json` 이 생성되고 임계값 판정이 사람의 해석 없이 결정됩니다. |
| L3 Persistent Learning | 실패가 test, docs, skill, tool 로 남습니다. | 특정 실패에서 유래한 회귀 검증이 저장소에 존재합니다. |
| L4 Harness Loop | 작업 기록을 분석해 하네스 개선안을 만듭니다. | improvement log에 `candidate` 이상의 항목이 축적됩니다. |
| L5 Self-Evolving Harness | candidate 하네스를 평가하고 자동으로 promote/reject 합니다. | 승격 판정이 `scripts/eval.sh` 결과로 자동 산출됩니다. |

L5부터 만들지 않습니다. 실제 개발 팀에게는 L3와 L4를 제대로 만드는 것이 훨씬 중요합니다. 단계별 판정 체크리스트와 다음 단계로 올라가는 최소 작업은 [references/maturity-levels.md](references/maturity-levels.md)를 읽습니다.

## 6. 적합성 판정

이 번들을 적용하기 전에 다음 전제를 확인합니다. 하나라도 성립하지 않으면 해당 항목을 먼저 갖춘 뒤 적용합니다. 전제 없이 적용하면 하네스가 아니라 문서 더미가 생깁니다.

| 전제 | 확인 방법 | 성립하지 않을 때 |
| --- | --- | --- |
| 결정적으로 실패를 알려주는 검증 수단이 최소 하나 있습니다. | 테스트, 타입 검사, lint, 빌드 중 하나가 종료 코드로 성패를 구분하는지 확인합니다. | 먼저 [scripts/verify.sh](scripts/verify.sh) 의 단계 하나를 성립시킵니다. HP-3 에 따라 평가가 memory보다 앞섭니다. |
| 하네스 변경을 되돌릴 수 있습니다. | 하네스 파일이 버전 관리 대상인지 확인합니다. | 버전 관리에 넣기 전에는 승격을 수행하지 않습니다. 잘못된 승격을 되돌릴 수 없습니다. |
| 검증을 실행할 수 있는 실행 환경이 있습니다. | `bash` 와 coreutils 가 있고 프로젝트 빌드 명령이 로컬 또는 CI에서 실행되는지 확인합니다. | 실행 환경을 먼저 확보합니다. 실행되지 않는 검증은 근거가 아닙니다. |
| 하네스 변경을 승인할 사람이 있습니다. | improvement log의 `owner` 를 지정할 수 있는지 확인합니다. | 소유자 없이 승격하지 않습니다. 소유자 없는 규칙은 만료되지 않습니다. |
| 대표 과제를 최소 3건 정의할 수 있습니다. | 이 프로젝트에서 반복되는 작업 유형을 열거합니다. | [evaluation/tasks/representative.md](evaluation/tasks/representative.md) 를 먼저 채웁니다. 회귀 검증 대상이 없으면 HP-5 를 만족할 수 없습니다. |
| 평가 기준을 에이전트가 스스로 고치지 못하게 막을 수 있습니다. | 평가 파일에 대한 변경이 리뷰 또는 hook으로 감시되는지 확인합니다. | [hooks/guard-evaluation-tampering.sh](hooks/guard-evaluation-tampering.sh) 를 먼저 도입합니다. |

다음 경우에는 이 번들을 적용하지 않습니다.

- 일회성 프로토타입이거나, 같은 종류의 작업이 반복되지 않는 저장소입니다. 반복이 없으면 하네스 개선의 회수 대상이 없습니다.
- 검증을 실행할 수 없는 환경입니다. 이때는 문서만 늘어나고 HP-2 를 만족할 수 없습니다.
- 하네스 변경을 사람이 검토할 여력이 전혀 없습니다. HP-5 의 승격 게이트가 형식만 남습니다.

## 관련 문서

- [README.md](README.md) — 번들 지도와 도입 순서
- [SKILL.md](SKILL.md) — 구축·감사·개선 모드 진입점
- [rules/RULES.md](rules/RULES.md) — 규칙 ID 전체 목록
- [references/harness-elements.md](references/harness-elements.md) — `HE-*` 상세
- [references/inner-outer-loop.md](references/inner-outer-loop.md) — 두 loop의 경계
- [references/maturity-levels.md](references/maturity-levels.md) — L0~L5 판정
- [references/evaluation-layers.md](references/evaluation-layers.md) — 평가 계층 6종
- [references/source-mapping.md](references/source-mapping.md) — 원문과 산출물의 대응
