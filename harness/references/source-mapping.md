# 원문-산출물 매핑

이 문서는 이 하네스 번들의 각 산출물이 원문의 어느 대목에서 도출되었는지를 기록한 추적표입니다. 하네스를 바꾸려는 사람이 "이 규칙은 왜 여기에 있는가"를 되짚을 때, 원문에 없는 요구사항이 슬며시 추가되지 않았는지 검토할 때, 그리고 원문 근거가 사라진 산출물을 정리할 때 읽습니다.

## 1. 출처

| 항목 | 값 |
| --- | --- |
| 제목 | AI Agentic Coding의 Self-Improving Loop란 무엇인가 |
| 매체 | Toby's Codex |
| 사이트 | codex.epril.com |
| 발행일 | 2026-08-08 |
| 원문 | https://codex.epril.com 의 해당 글 |

이 번들은 원문의 요약이 아닙니다. 원문에서 도출한 요구사항을 규칙 ID, 절차, 스크립트, 스키마로 승격시킨 결과물입니다. 따라서 산출물의 문장과 원문의 문장은 일대일로 대응하지 않으며, 대응하는 것은 **요구사항**입니다.

## 2. 이 표의 사용법

- **하네스를 변경할 때**: 바꾸려는 산출물이 표의 어느 행에 있는지 먼저 확인합니다. 행이 없다면 그 산출물은 원문 근거 없이 추가된 것이므로, 근거를 새로 밝히거나 제거 대상으로 분류합니다.
- **산출물을 추가할 때**: 새 산출물은 반드시 하나 이상의 원문 섹션에 연결합니다. 연결되지 않는 요구사항은 이 번들의 범위 밖입니다.
- **산출물을 제거할 때**: 같은 행을 근거로 삼는 다른 산출물이 남아 있는지 확인합니다. 한 행의 요구사항이 어느 산출물에도 남지 않게 되면 요구사항이 유실된 것입니다.
- **요소 ID 열**: `HE-*` 는 `harness-elements.md` 의 요소 ID이고, 두 글자 대문자 prefix는 `rules/` 의 규칙 ID 네임스페이스(LP, PG, UT, LB, EI, CC, CX, GC)입니다.

표의 행 순서는 원문의 섹션 순서와 같습니다. 원문에서 섹션 위치를 다시 찾을 때는 표의 "원문 섹션 제목" 열을 원문에서 검색합니다. 이 번들은 원문 사본을 포함하지 않으므로, 대조가 필요하면 위 URL 에서 원문을 먼저 확보하십시오.

검색창, 댓글, 구독 안내 같은 사이트 UI 영역(`#H2 검색`, 댓글 영역, `#H3 새 글을 이메일로 받아보세요`)은 본문이 아니므로 표에서 제외했습니다. 그 외의 모든 본문 섹션은 빠짐없이 행으로 포함되어 있습니다.

## 3. 매핑 표

| 원문 섹션 제목 | 도출한 요구사항 | 산출물 경로 | 요소 ID / 규칙 prefix |
| --- | --- | --- | --- |
| (도입부, 제목 없음) | 개선 대상은 모델 weight가 아니라 에이전트가 일하는 시스템입니다. 번들은 self-improving model이 아니라 self-improving harness를 만듭니다. | `README.md`, `HARNESS.md` | HE-1~HE-15 |
| Agent가 반복한다고 Self-Improving Loop인 것은 아니다 | 현재 작업의 개선과 작업 시스템의 개선을 구분하고, 어제의 시행착오가 오늘의 실행에 반영되는지를 판정 기준으로 삼습니다. | `references/inner-outer-loop.md`, `references/maturity-levels.md` | HE-15 |
| Ralph Loop와도 조금 다르다 | 반복과 개선은 다른 개념입니다. 반복 횟수 자체를 성과로 보지 않고, 반복에는 종료 조건을 둡니다. | `references/inner-outer-loop.md`, `rules/loop-budget.rule.md`, `scripts/loop.sh` | LB, HE-15 |
| 그렇다면 무엇이 개선되어야 할까? | 하네스 구성 요소 15개를 정본 인벤토리로 고정하고, 모든 개선안을 그중 하나에 배치합니다. | `references/harness-elements.md` | HE-1~HE-15 |
| 실수를 고치지 말고 실수를 만들어낸 시스템을 고쳐보자 | 실패를 만나면 코드뿐 아니라 그 실패를 허용한 하네스 결함까지 진단합니다. 진단 질문 목록을 절차로 고정합니다. | `skills/harness-retro/SKILL.md`, `subagents/harness-reviewer.md` | HE-8, HE-9 |
| 좋은 실패는 시스템에 무언가를 남긴다 | 비싼 실패는 다음 실행의 행동을 바꾸는 형태로 저장소에 남깁니다. 남길 형태의 후보는 test, lint rule, documentation, skill, hook, tool, architecture rule입니다. | `rules/lesson-placement.rule.md`, `improvement-log/schema.md` | LP, HE-13 |
| 모든 것을 AGENTS.md에 적으면 되지 않을까? | 지시문 파일의 무한 증식을 막습니다. 규칙 추가는 context pollution 비용을 함께 판정해야 합니다. | `rules/context-hygiene.rule.md`, `templates/AGENTS.md`, `templates/CLAUDE.md` | CX, HE-1, HE-2 |
| Lesson에는 가장 적절한 자리가 있다 | 문제 유형별 배치표를 정본으로 두고, instruction을 verification으로 승격시키는 강제력 사다리를 규범으로 삼습니다. | `references/lesson-placement.md`, `references/harness-elements.md`, `rules/lesson-placement.rule.md` | LP, HE-3~HE-13 |
| Self-Improving Loop의 중심에는 Evaluation이 있다 | Execution → Evaluation → Evidence → Diagnosis → Lesson → Memory 순서를 강제합니다. 평가 없이 memory를 먼저 만들지 않습니다. | `references/evaluation-layers.md`, `rules/promotion-gate.rule.md` | PG, HE-14, HE-13 |
| 가장 먼저 verify를 만들자 | 통합된 검증 진입점 하나를 최우선 산출물로 둡니다. 스택은 자동 감지하고 `harness.config` 로 재정의합니다. | `scripts/verify.sh`, `scripts/lib/detect-stack.sh`, `scripts/harness.config.example`, `language/README.md`, `language/*/lang.sh` | HE-11, HE-5, HE-6, HE-7 |
| Agent에게 눈과 귀를 만들어주자 | 에이전트가 자기 결과를 관찰할 수 있는 채널(browser, DOM, console, network, 로그, 메트릭 등)을 하네스 요구사항으로 명시합니다. | `references/agent-observability.md`, `evaluation/rubric.md` | HE-14, HE-12 |
| 가장 단순한 Self-Improving Loop | 최소 구조는 inner loop(검증 기반 수정)와 outer loop(회고 기반 개선) 두 개입니다. 이 이상을 처음부터 만들지 않습니다. | `scripts/loop.sh`, `references/inner-outer-loop.md`, `references/harness-adoption.md` | HE-15 |
| Inner Loop와 Outer Loop를 구분해보자 | 두 루프의 목적, 입력, 산출물, 종료 조건을 분리해 정의합니다. | `references/inner-outer-loop.md` | HE-15 |
| Inner Loop | 현재 작업을 성공시키는 반복입니다. 근거는 검증 결과이며 산출물은 통과한 작업입니다. | `scripts/loop.sh`, `scripts/verify.sh` | HE-15, LB |
| Outer Loop | 미래의 작업을 더 잘하기 위한 반복입니다. 근거는 작업 기록이며 산출물은 하네스 변경입니다. | `skills/harness-retro/SKILL.md`, `skills/harness-promote/SKILL.md` | HE-8, HE-14 |
| 한 번에 하나씩 개선하자 | 하네스 변경은 한 번에 하나만 적용하고 변경 전후 평가 점수를 비교합니다. 좋아지면 남기고 아니면 버립니다. | `rules/harness-change-control.rule.md`, `scripts/eval.sh` | CC, HE-14 |
| 새로운 규칙도 테스트 대상이다 | 새 규칙·skill은 representative task와 held-out task로 회귀 검증한 뒤에만 적용합니다. 검증 없는 적용은 self-drift입니다. | `evaluation/tasks/representative.md`, `evaluation/tasks/held-out.md`, `rules/harness-change-control.rule.md` | CC, HE-14 |
| Improvement Log를 만들어보자 | 후보 lesson을 고정 스키마로 기록하고 `status` 전이(candidate → validating → promoted / rejected / expired)를 강제합니다. | `improvement-log/schema.md`, `improvement-log/_template.yaml`, `scripts/improvement-log.sh` | HE-13, HE-12, PG |
| Claude Code에서는 어떻게 구현할 수 있을까? | CLAUDE.md는 백과사전이 아니라 지도로 유지하고, 반복 전문 작업은 skill로, 하네스 분석은 subagent로 분리합니다. | `templates/CLAUDE.md`, `skills/`, `subagents/harness-reviewer.md` | HE-2, HE-8, HE-9 |
| Codex에서도 구조는 거의 같다 | 도구에 종속되지 않는 이식 가능한 구조를 유지합니다. monorepo에서는 지침을 scope별로 분할하고, 평가 파일과 임계값 판정을 별도 명령으로 둡니다. | `agents/openai.yaml`, `templates/AGENTS.md`, `scripts/eval.sh`, `scripts/pass-threshold.sh` | HE-1, HE-8, HE-15 |
| Loop에는 Budget과 Stop Condition이 필요하다 | 최대 반복 8회, 동일 실패 3회, 2라운드 연속 개선 없음, 보안 민감 변경의 사람 검토, 예산 초과를 종료 조건으로 고정합니다. | `rules/loop-budget.rule.md`, `scripts/loop.sh`, `scripts/harness.config.example` | LB, HE-15 |
| Evaluation을 속이는 Agent | 평가를 단일 숫자로 만들지 않고 6개 layer로 나눕니다. 가능한 부분은 결정적 평가로 만들고, 평가 기준 자체의 수정을 차단합니다. | `references/evaluation-layers.md`, `rules/evaluation-integrity.rule.md`, `hooks/guard-evaluation-tampering.sh` | EI, HE-14, HE-10 |
| Generator와 Evaluator를 분리할 수도 있다 | 구현 역할과 평가 역할을 분리하고, 평가자는 근거와 함께 점수·비평을 반환합니다. | `references/generator-evaluator.md`, `subagents/harness-evaluator.md` | HE-9, HE-14 |
| Self-Improving Loop의 가장 큰 위험은 잘못된 학습이다 | issue, 로그, 웹 문서, 사용자 보고, 에이전트 관찰은 기본적으로 untrusted입니다. 검증 게이트를 통과해야 trusted 영역으로 넘어갑니다. | `rules/untrusted-experience.rule.md`, `improvement-log/schema.md` | UT, HE-13 |
| 주기적으로 Harness를 청소하는 Agent도 필요하다 | 낡은 규칙, 어긋난 문서, 겹치는 skill, 영구화된 workaround를 주기적으로 제거합니다. 잘 잊는 능력을 절차로 만듭니다. | `rules/harness-gc.rule.md`, `skills/harness-gardener/SKILL.md` | GC, HE-8 |
| Agentic Coding의 성숙도를 단계로 생각해보자 | L0~L5 단계표를 정본으로 싣고 관측 가능한 판정 기준을 붙입니다. L5보다 L3·L4를 우선합니다. | `references/maturity-levels.md` | HE-1~HE-15 |
| Stop Being the Loop에서 Improve the Loop로 | 작업 종료 시 "무엇이 부족했는가, 어떤 tool이나 rule이 있었으면 쉬웠는가"를 묻고 그 답을 하네스에 추가합니다. | `skills/harness-retro/SKILL.md`, `SKILL.md` | HE-15, HE-8 |
| Prompt Engineering에서 Harness Engineering으로 | 이 번들의 위치를 harness engineering과 loop engineering 계층으로 규정하고, prompt 개선으로 대체하지 않습니다. | `HARNESS.md`, `README.md` | HE-1~HE-15 |
| 처음부터 거창하게 만들 필요는 없다 | 최소 도입 경로는 통합 verify, improvement log, harness retrospective 세 가지입니다. multi-agent, vector DB, 자동 skill generator부터 만들지 않습니다. | `references/harness-adoption.md`, `SKILL.md`, `README.md` | HE-11, HE-13, HE-8 |
| 실패할 때마다 시스템이 조금 더 좋아지게 만들자 | 번들의 최상위 원칙: 비싼 실패는 시스템에 실행 가능한 형태로 남겨야 합니다. 남긴 것은 git에 넣고, 리뷰하고, 검증하고, 필요 없어지면 제거합니다. | `README.md`, `HARNESS.md`, `rules/RULES.md` | HE-1~HE-15, GC |
| 참고 자료 | 원문이 근거로 제시한 외부 자료 목록을 변경 없이 보존합니다. | `references/source-mapping.md` 4절 | — |

## 4. 원문 참고 자료

아래 목록은 원문의 "참고 자료" 절을 그대로 옮긴 것입니다. URL을 바꾸거나 항목을 추가하지 않습니다.

- OpenAI, Harness engineering: leveraging Codex in an agent-first world
  https://openai.com/index/harness-engineering/
- OpenAI Codex, Iterate on difficult problems with evals
  https://learn.chatgpt.com/codex/use-cases/iterate-on-difficult-problems
- OpenAI Codex, AGENTS.md
  https://learn.chatgpt.com/codex/agent-configuration/agents-md
- OpenAI Codex, Agent Skills
  https://learn.chatgpt.com/codex/build-skills
- Anthropic Claude Code, Run Claude until a goal is met
  https://code.claude.com/docs/en/goal
- Anthropic Claude Code, Subagents
  https://code.claude.com/docs/en/sub-agents
- Anthropic, Effective harnesses for long-running agents
  https://www.anthropic.com/engineering/harness-design-long-running-apps
- Agentic Harness Engineering, arXiv:2604.25850
  https://arxiv.org/abs/2604.25850
- Bad Memory: Persistent Memory Risks in Coding Agents, arXiv:2607.14611
  https://arxiv.org/abs/2607.14611

## 관련 문서

- [harness-elements.md](harness-elements.md) — 표의 `HE-*` 열이 가리키는 요소 정의입니다.
- [maturity-levels.md](maturity-levels.md) — 원문 성숙도 표의 정본과 판정 기준입니다.
