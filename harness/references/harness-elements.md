# 하네스 요소 카탈로그 (HE-1~HE-15)

이 문서는 하네스를 구성하는 15개 요소의 정본 카탈로그입니다. lesson을 어디에 남길지 정할 때, improvement log의 `harness_element` 값을 채울 때, 하네스에 새 산출물을 추가하거나 제거할 때 먼저 읽습니다. 요소 ID(`HE-*`)와 강제력 등급(`EL-*`)은 이 번들의 다른 모든 문서가 공유하는 어휘이므로, 이 문서 밖에서 새 요소 ID를 발급하지 않습니다.

## 1. 인벤토리 요약

| ID | 요소 | 강제력 등급 | 산출물 위치 |
| --- | --- | --- | --- |
| HE-1 | AGENTS.md | EL-1 instruction | `templates/AGENTS.md` |
| HE-2 | CLAUDE.md | EL-1 instruction | `templates/CLAUDE.md` |
| HE-3 | documentation | EL-2 doc | `references/` 전체, `language/<언어>/<kind>/examples.md` |
| HE-4 | architecture rules | EL-6 lint·arch-rule | `rules/` 전체 |
| HE-5 | tests | EL-5 test | `evaluation/tasks/`, `scripts/verify.sh` 의 test 단계, `language/<언어>/lang.sh` |
| HE-6 | lint rules | EL-6 lint·arch-rule | `scripts/verify.sh` 의 lint 단계, `language/<언어>/lang.sh` |
| HE-7 | static analysis | EL-6 lint·arch-rule | `scripts/verify.sh` 의 static 단계, `language/<언어>/lang.sh` |
| HE-8 | skills | EL-3 skill | `skills/` 5종 |
| HE-9 | subagents | EL-3 skill | `subagents/` 2종 |
| HE-10 | hooks | EL-7 hook | `hooks/`, `language/<언어>/lang.sh` 의 보호 패턴 |
| HE-11 | scripts | EL-4 script | `scripts/`, `language/<언어>/lang.sh` 의 감지 |
| HE-12 | tools | EL-4 script | `scripts/improvement-log.sh` 등 CLI |
| HE-13 | memory | 등급 외 (보관소) | `improvement-log/` (승격된 lesson만) |
| HE-14 | evaluation | EL-5 test | `evaluation/`, `scripts/eval.sh` |
| HE-15 | workflow | EL-4 script | `scripts/loop.sh`, `skills/` 의 절차 |

이 15개가 하네스의 전부입니다. 개선안이 이 표의 어느 행에도 배치되지 않는다면 그것은 하네스 개선이 아니라 제품 코드 변경이며, improvement log에 올리지 않습니다.

요소 ID 는 언어와 무관하지만 몇몇 요소의 **내용**은 언어에 따라 달라집니다. HE-5·HE-6·HE-7 의 verify 기본 단계, HE-10 의 언어별 보호 패턴, HE-11 의 스택 감지, HE-3 의 언어별 예시 문서가 그것이며, 이 부분은 `language/<언어>/` 팩이 소유합니다. 팩은 새 요소 ID 를 발급하지 않습니다. 규약은 [../language/README.md](../language/README.md) 에 있습니다.

## 2. 강제력 사다리

강제력은 "이 lesson을 다음 에이전트가 놓쳤을 때 실패로 드러나는가"로 정의합니다. 읽히지 않아도 무방한 장치는 낮은 등급이고, 놓치는 순간 명령이 0이 아닌 종료 코드를 내는 장치는 높은 등급입니다.

| 등급 | enforcement 값 | 놓쳤을 때 무슨 일이 일어나는가 | 판정 근거 |
| --- | --- | --- | --- |
| EL-1 | `instruction` | 아무 일도 일어나지 않습니다. 에이전트가 문장을 읽지 않았을 수 있고, 읽고도 다르게 해석할 수 있습니다. | 사람이 다음 리뷰에서 발견 |
| EL-2 | `doc` | 아무 일도 일어나지 않습니다. 다만 지시가 아니라 근거를 제공하므로 재발 시 진단이 빨라집니다. | 사람이 다음 리뷰에서 발견 |
| EL-3 | `skill`, `subagent` | 해당 절차를 호출한 작업에서만 드러납니다. 호출하지 않으면 드러나지 않습니다. | 절차를 실행한 세션의 산출물 |
| EL-4 | `script` | 스크립트를 실행한 경우에만 드러납니다. 실행 자체는 강제되지 않습니다. | 명령 종료 코드 |
| EL-5 | `test` | 해당 테스트를 실행하면 반드시 드러납니다. `verify` 또는 `eval` 단계에 포함되면 회피가 어렵습니다. | `.harness/verify.json` 의 step 결과 |
| EL-6 | `lint`, `arch-rule` | 코드 형태 자체가 규칙을 위반하면 실행 없이도 드러납니다. 대상 코드 전체에 일괄 적용됩니다. | `verify.sh` 의 lint·static 단계 |
| EL-7 | `hook` | 에이전트가 실행 여부를 선택할 수 없습니다. 정해진 시점에 항상 실행되고 실패 시 진행이 차단됩니다. | hook 종료 코드 |

원칙은 하나입니다. **가능하다면 instruction을 verification으로 승격시킵니다.** 같은 lesson을 남길 수 있는 자리가 여럿이면 실패로 드러나는 가장 높은 등급을 고릅니다.

다만 높은 등급이 항상 옳은 것은 아닙니다. 다음 세 조건 중 하나라도 어긋나면 한 등급 내려서 남깁니다.

- 규칙을 기계적으로 판정할 수 없습니다(판정에 맥락 해석이 필요합니다).
- 위반 판정에 오탐이 섞이고, 오탐을 억제할 예외 경로가 없습니다.
- 규칙이 아직 1회 관측이며 일반화 근거가 없습니다. 이 경우 EL-1~EL-2에서 관측을 더 모읍니다.

`memory`(HE-13)는 사다리에 올리지 않습니다. memory는 강제 장치가 아니라 승격 대기 중인 후보를 보관하는 자리이며, 그 자체로는 다음 실행의 행동을 바꾸지 않기 때문입니다. memory에 남긴 것은 반드시 EL-1 이상의 자리로 승격되거나 만료되어야 합니다.

### 2.1 승격 경로 예시: Controller → Repository 직접 의존

원문의 계층 규칙 사례(Controller 가 Repository 를 직접 의존한 사건)를 사다리에 대입하면 다음과 같습니다. 같은 lesson이지만 남기는 자리에 따라 강제력이 달라집니다. 아래 표는 언어에 관계없이 같고, 3·4단계의 실제 도구와 규칙 코드는 언어 팩의 예시 문서가 보여 줍니다.

| 단계 | 등급 | 남기는 형태 | 다음 작업에서의 효과 |
| --- | --- | --- | --- |
| 0 | 등급 외 | 세션 안에서 "Service를 통하도록 고쳐"라고 말하고 끝냅니다. | 없습니다. 내일 같은 실수가 반복됩니다. |
| 1 | EL-1 | AGENTS.md에 "Controller에서 Repository를 직접 호출하지 않는다"를 한 줄 추가합니다. | 에이전트가 읽으면 지켜집니다. 읽지 않으면 그대로입니다. |
| 2 | EL-2 | `docs/architecture` 에 계층 의존 방향과 이유를 문서화하고 AGENTS.md가 그 문서를 가리키게 합니다. | 판단 근거가 생깁니다. 여전히 놓칠 수 있습니다. |
| 3 | EL-6 | 아키텍처 규칙 도구에 규칙을 추가합니다. | 위반하면 검사가 실패합니다. 놓칠 수 없습니다. |
| 4 | EL-6+ | 규칙의 실패 메시지에 올바른 대안 경로(use-case 계층을 경유)를 적어 넣습니다. | 실패가 곧 수정 방법을 알려줍니다. 재시도 비용이 줄어듭니다. |
| 5 | EL-7 | 해당 검증을 `verify.sh` 에 포함시키고, 작업 종료 시 `verify` 를 강제하는 hook을 겁니다. | 검증을 건너뛴 채로 작업을 끝낼 수 없습니다. |

3단계의 규칙을 어떤 도구로 쓰는지는 언어와 kind 에 따라 다릅니다.

| 스택 | 아키텍처 규칙 도구 | 규칙 코드와 4단계 실패 메시지 예시 |
| --- | --- | --- |
| Java 백엔드 | ArchUnit | [../language/java/backend/examples.md](../language/java/backend/examples.md) 1절 |
| TypeScript 프론트엔드 | dependency-cruiser, eslint-plugin-boundaries | [../language/typescript/frontend/examples.md](../language/typescript/frontend/examples.md) 1절 |
| TypeScript 백엔드 | dependency-cruiser | [../language/typescript/backend/examples.md](../language/typescript/backend/examples.md) 1절 |
| Python 백엔드 | import-linter | [../language/python/backend/examples.md](../language/python/backend/examples.md) 1절 |

표에서 **감지된 스택의 행 하나만** 읽습니다. 스택과 kind 는 `harness/scripts/verify.sh --list` 로 확정합니다. 다른 팩의 예시는 이 프로젝트와 무관하므로 열지 않습니다.

승격은 낮은 등급을 지우는 것이 아닙니다. 3단계에 도달했다면 1단계에서 추가했던 AGENTS.md 한 줄은 **제거합니다**. 기계가 판정하는 규칙을 사람 대상 지시문으로 중복 보관하면 HE-1이 비대해지기만 하고 강제력은 늘지 않습니다. 승격의 결과는 "지시문 + 규칙"이 아니라 "규칙 + 그 규칙을 설명하는 문서"입니다.

### 2.2 승격 경로를 기록하는 방법

improvement log 항목의 `preferred_enforcement` 에는 도달하려는 목표 등급의 enforcement 값을 적고, `harness_element` 에는 그 등급이 놓이는 요소 ID를 적습니다. 위 예시는 다음과 같이 기록됩니다.

```yaml
harness_element: HE-4
preferred_enforcement: arch-rule
```

스키마 전체와 필수 키 순서는 `improvement-log/schema.md` 를 따릅니다.

## 3. 요소별 정본 정의

각 항목은 정의, 이 요소가 답하는 질문, 강제력 등급, 대표 실패 모드, 산출물 위치 순으로 기술합니다.

### HE-1 AGENTS.md

- **정의**: 에이전트가 작업을 시작할 때 항상 읽는 프로젝트 최상위 지침입니다. 지식의 저장소가 아니라 프로젝트를 탐색하기 위한 지도입니다.
- **답하는 질문**: 이 저장소에서 일할 때 반드시 알아야 할 최소한의 것은 무엇이며, 나머지는 어디에 있는가?
- **강제력 등급**: EL-1 instruction.
- **대표 실패 모드**: 사건이 생길 때마다 한 줄씩 추가되어 수백 줄이 됩니다. 모든 규칙이 중요해지고 결국 아무 규칙도 중요하지 않게 됩니다. 낡은 규칙과 서로 모순되는 규칙이 남아 context를 오염시킵니다.
- **산출물 위치**: `templates/AGENTS.md`. 비대화 방지 규칙은 `rules/context-hygiene.rule.md`.

### HE-2 CLAUDE.md

- **정의**: Claude Code 계열 도구가 읽는 지침 파일입니다. 역할은 HE-1과 같고 도구별 표기만 다릅니다.
- **답하는 질문**: 이 도구로 이 저장소를 열었을 때 무엇을 먼저 읽고, 무엇으로 완료를 판정하는가?
- **강제력 등급**: EL-1 instruction.
- **대표 실패 모드**: HE-1과 같은 비대화. 여기에 더해 AGENTS.md와 내용이 갈라져 두 파일이 서로 다른 규칙을 말하게 됩니다.
- **산출물 위치**: `templates/CLAUDE.md`.

### HE-3 documentation

- **정의**: 아키텍처, 설계 결정, 도메인 지식처럼 분량이 크고 자주 바뀌지 않는 지식을 담는 문서입니다.
- **답하는 질문**: 이 구조는 왜 이렇게 되어 있는가? 지시문에 담기에는 긴 배경을 어디서 읽는가?
- **강제력 등급**: EL-2 doc.
- **대표 실패 모드**: 문서가 존재하지만 에이전트가 찾지 못합니다. HE-1에서 링크하지 않으면 없는 것과 같습니다. 또한 코드가 바뀌어도 문서가 따라가지 않아 잘못된 지식을 제공합니다.
- **산출물 위치**: `references/` 전체. 언어별 구체 예시는 `language/<언어>/<kind>/examples.md`.

### HE-4 architecture rules

- **정의**: 계층 의존 방향, 패키지 경계, 금지된 참조처럼 코드 구조에 대한 기계 판정 가능한 규칙입니다.
- **답하는 질문**: 이 코드가 구조적으로 허용되는가?
- **강제력 등급**: EL-6 lint·arch-rule.
- **대표 실패 모드**: 규칙은 있으나 실패 메시지가 "규칙 위반"만 알려주고 올바른 대안을 알려주지 않습니다. 에이전트가 규칙을 우회하는 방향(예: 패키지 이름 변경)으로 수정합니다.
- **산출물 위치**: `rules/` 전체.

### HE-5 tests

- **정의**: 실행해서 통과·실패가 결정되는 검증입니다. 회귀 테스트, 통합 테스트, 시나리오 테스트를 포함합니다.
- **답하는 질문**: 이 동작이 지금도 의도대로 작동하는가?
- **강제력 등급**: EL-5 test.
- **대표 실패 모드**: 통과시키기 위해 테스트를 약화시킵니다(단언 삭제, skip 처리, 임계값 하향). 이것은 개선이 아니라 평가 조작이며 `rules/evaluation-integrity.rule.md` 위반입니다.
- **산출물 위치**: `evaluation/tasks/`, `scripts/verify.sh` 의 test 단계.

### HE-6 lint rules

- **정의**: 코드 형태와 관용에 대한 자동 판정 규칙입니다.
- **답하는 질문**: 반복되는 표면적 실수를 사람이 매번 지적하지 않고 잡을 수 있는가?
- **강제력 등급**: EL-6 lint·arch-rule.
- **대표 실패 모드**: "Lint Errors = 0"이라는 목표만 주면 가장 쉬운 해결책이 규칙을 끄는 것이 됩니다. 규칙 비활성화는 lint 통과가 아니라 lint 삭제입니다.
- **산출물 위치**: `scripts/verify.sh` 의 lint 단계.

### HE-7 static analysis

- **정의**: 실행하지 않고 코드에서 결함 가능성을 찾아내는 분석입니다. 타입 검사, 취약점 스캔, 복잡도 분석을 포함합니다.
- **답하는 질문**: 실행하지 않고도 알 수 있는 문제가 남아 있는가?
- **강제력 등급**: EL-6 lint·arch-rule.
- **대표 실패 모드**: 경고가 수백 건 쌓인 채 아무도 보지 않습니다. 판정 기준이 없으면 신호가 되지 않습니다.
- **산출물 위치**: `scripts/verify.sh` 의 static 단계.

### HE-8 skills

- **정의**: 반복되는 작업 절차를 재현 가능한 형태로 묶은 것입니다. 지식이 아니라 순서입니다.
- **답하는 질문**: 이 종류의 작업은 어떤 순서로 하는가?
- **강제력 등급**: EL-3 skill.
- **대표 실패 모드**: skill이 서로 겹쳐 어느 것을 불러야 할지 모호해집니다. 또한 호출되지 않으면 아무 효과가 없으므로, 반드시 실행되어야 하는 검사를 skill에만 넣으면 강제력이 없습니다.
- **산출물 위치**: `skills/` 5종.

### HE-9 subagents

- **정의**: 특정 분야의 판단을 전담하는 별도 에이전트입니다. 제품 코드를 만드는 역할과 평가·개선안을 만드는 역할을 분리합니다.
- **답하는 질문**: 이 판단을 구현자와 같은 맥락에서 내려도 되는가, 분리해야 하는가?
- **강제력 등급**: EL-3 skill. 판단을 생산할 뿐 강제하지는 않습니다.
- **대표 실패 모드**: 구현한 에이전트가 자기 결과를 평가하여 통과시킵니다. 역할 분리가 없으면 평가가 구현의 연장이 됩니다.
- **산출물 위치**: `subagents/` 2종.

### HE-10 hooks

- **정의**: 정해진 시점에 에이전트의 선택과 무관하게 실행되는 장치입니다.
- **답하는 질문**: 절대 건너뛰면 안 되는 검사는 무엇인가?
- **강제력 등급**: EL-7 hook. 사다리의 최상단입니다.
- **대표 실패 모드**: hook에 무거운 작업을 넣어 매 시점마다 수 분이 소모되고, 결국 사람이 hook을 끕니다. hook은 짧고 결정적이어야 합니다.
- **산출물 위치**: `hooks/`. 언어별 보호 패턴은 `language/<언어>/lang.sh`.

### HE-11 scripts

- **정의**: 검증, 평가, 반복 실행처럼 에이전트와 사람이 같은 방식으로 실행하는 명령입니다.
- **답하는 질문**: 이 작업을 매번 다르게 설명하지 않고 한 줄로 실행할 수 있는가?
- **강제력 등급**: EL-4 script.
- **대표 실패 모드**: 검증 명령이 여러 개로 흩어져 있어 에이전트가 일부만 실행하고 완료를 선언합니다. 통합된 진입점이 하나 있어야 합니다.
- **산출물 위치**: `scripts/`. 스택 감지와 기본 단계는 `language/<언어>/lang.sh`.

### HE-12 tools

- **정의**: 에이전트가 반복적으로 수행하기 어렵거나 비싼 조작을 대신하는 CLI입니다.
- **답하는 질문**: 이 조작을 에이전트가 매번 직접 하는 것이 맞는가, 도구로 만들어야 하는가?
- **강제력 등급**: EL-4 script.
- **대표 실패 모드**: 도구가 없어서 에이전트가 매번 즉석 명령을 조합하고, 조합할 때마다 조금씩 다른 결과가 나옵니다.
- **산출물 위치**: `scripts/improvement-log.sh` 등 CLI.

### HE-13 memory

- **정의**: 과거 작업에서 얻은 경험 중 검증을 거친 것만 보존하는 자리입니다. 학습 자체가 아니라 검증된 학습 결과의 보관소입니다.
- **답하는 질문**: 이 경험은 아직 후보인가, 이미 검증되어 하네스에 반영되었는가?
- **강제력 등급**: 등급 외. memory는 다음 실행의 행동을 직접 바꾸지 않습니다.
- **대표 실패 모드**: 평가 없이 memory부터 만들면 잘못 판단했던 경험까지 정확히 기억합니다. 또한 외부 입력(issue, 로그, 웹 문서)이 그대로 permanent memory가 되면 오염된 학습이 남습니다.
- **산출물 위치**: `improvement-log/` (승격된 lesson만). 신뢰 경계는 `rules/untrusted-experience.rule.md`.

### HE-14 evaluation

- **정의**: 결과가 좋아졌는지를 판정하는 계층적 평가입니다. `correctness`, `architecture`, `quality`, `behavior`, `performance`, `subjective` 6개 layer를 사용합니다.
- **답하는 질문**: 이 변경으로 실제로 좋아졌는가, 아니면 좋아 보이기만 하는가?
- **강제력 등급**: EL-5 test. 임계값 판정이 붙으면 EL-6에 준합니다.
- **대표 실패 모드**: 평가를 하나의 숫자로만 만들면 에이전트가 그 숫자를 최적화합니다. 의미 없는 테스트로 커버리지를 올리거나 lint 규칙을 꺼서 오류를 0으로 만듭니다.
- **산출물 위치**: `evaluation/`, `scripts/eval.sh`.

### HE-15 workflow

- **정의**: 언제 다시 실행하고 어떻게 상태를 이어갈지에 대한 절차입니다. inner loop와 outer loop, 예산과 종료 조건을 포함합니다.
- **답하는 질문**: 이 반복은 언제 끝나는가? 끝났을 때 시스템에 무엇이 남는가?
- **강제력 등급**: EL-4 script.
- **대표 실패 모드**: 종료 조건 없이 반복시키면 에이전트가 같은 자리를 맴돌거나 평가 자체를 공략하기 시작합니다. 반복은 개선과 다릅니다.
- **산출물 위치**: `scripts/loop.sh`, `skills/` 의 절차.

## 4. 카탈로그 사용 규칙

- 새 개선안은 반드시 하나의 `HE-*` 에 배치합니다. 두 요소에 걸치면 두 개의 후보로 나눕니다.
- 요소 ID는 추가하지 않습니다. 15개는 고정 인벤토리입니다.
- 등급을 올리는 변경(승격)과 자리를 옮기는 변경(이동)은 서로 다른 후보로 기록합니다.
- 등급이 올라간 뒤 남는 하위 등급 중복은 제거합니다. 제거 판단은 `rules/harness-gc.rule.md` 를 따릅니다.

## 관련 문서

- [maturity-levels.md](maturity-levels.md) — 어떤 요소를 지금 단계에서 추가해야 하는지 판단합니다.
- [lesson-placement.md](lesson-placement.md) — 발견한 문제 유형별로 어느 요소에 남길지 결정합니다.
- [source-mapping.md](source-mapping.md) — 각 요소가 원문의 어느 근거에서 왔는지 추적합니다.
- [inner-outer-loop.md](inner-outer-loop.md) — HE-15의 두 루프 구분입니다.
- [evaluation-layers.md](evaluation-layers.md) — HE-14의 6개 layer 정의입니다.
