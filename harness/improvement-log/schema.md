# improvement log 스키마 (harness.improvement/1)

이 문서는 improvement candidate YAML 을 새로 쓰거나 검토하거나 상태를 바꾸기 직전에 읽습니다. `scripts/improvement-log.sh new` 로 생성한 파일을 채울 때, 회고에서 나온 lesson 을 기록할 때, `status` 를 다음 단계로 올릴 때가 그 시점입니다. 이 문서는 **어떤 키를 어떻게 채우는가**의 정본이고, 후보를 **승격해도 되는가**의 판정은 [../rules/promotion-gate.rule.md](../rules/promotion-gate.rule.md) 가 소유합니다.

## 1. 파일 규약

| 항목 | 규약 |
| --- | --- |
| 위치 | 프로젝트 루트의 `improvement-log/` (하네스 번들 안이 아니라 대상 프로젝트 루트입니다) |
| 파일명 | `<id>.yaml`. `scripts/improvement-log.sh new` 가 이 규약을 보장하므로 파일명을 손으로 바꾸지 않습니다. |
| 인코딩 | UTF-8, 줄바꿈 LF |
| 한 파일당 항목 수 | 1건. 하나의 YAML 문서에 여러 후보를 담지 않습니다. |
| 최상위 구조 | 평평한 매핑 1개. 중첩 매핑이나 리스트를 최상위에 두지 않습니다. |

## 2. 키 순서는 고정입니다

필수 키는 15개이며 **아래 순서 그대로** 나열합니다. 순서는 사건의 인과 순서(증상 → 근거 → 원인 → 조치 → 재발 위험 → 하네스 반영 → 신뢰와 검증 → 소유와 만료)를 따르므로, 순서를 바꾸면 읽는 사람이 근거 없이 결론부터 읽게 됩니다.

```text
id → date → status → symptom → evidence → root_cause → fix → recurrence_risk
   → harness_element → proposed_harness_change → preferred_enforcement
   → trust → regression_check → owner → expires
```

`scripts/improvement-log.sh validate` 가 이 순서를 강제합니다. 키가 빠졌거나, 순서가 어긋났거나, 허용값 밖의 값이 들어 있으면 검증이 실패하고 해당 항목은 승격 절차에 들어가지 못합니다. 스키마에 없는 키는 추가하지 않습니다. 추가 정보가 필요하면 `evidence` 또는 `regression_check` 본문에 적습니다.

```bash
scripts/improvement-log.sh validate
scripts/improvement-log.sh validate improvement-log/2026-08-09-001.yaml
```

## 3. 키 목록 요약

| # | 키 | 타입 | 필수 | 허용값 |
| --- | --- | --- | --- | --- |
| 1 | `id` | string | 예 | `YYYY-MM-DD-NNN` |
| 2 | `date` | string | 예 | `YYYY-MM-DD` |
| 3 | `status` | enum | 예 | `candidate` \| `validating` \| `promoted` \| `rejected` \| `expired` |
| 4 | `symptom` | string | 예 | 자유 서술 1~3문장 |
| 5 | `evidence` | string(블록) | 예 | 자유 서술, 실제 경로·오류 문구 포함 |
| 6 | `root_cause` | string | 예 | 자유 서술 1~3문장 |
| 7 | `fix` | string | 예 | 자유 서술 1~3문장 |
| 8 | `recurrence_risk` | enum | 예 | `low` \| `medium` \| `high` |
| 9 | `harness_element` | string | 예 | `HE-1` ~ `HE-15` |
| 10 | `proposed_harness_change` | string | 예 | 자유 서술 1~3문장 |
| 11 | `preferred_enforcement` | enum | 예 | `test` \| `lint` \| `arch-rule` \| `hook` \| `script` \| `doc` \| `skill` \| `subagent` \| `instruction` |
| 12 | `trust` | enum | 예 | `untrusted` \| `validated` |
| 13 | `regression_check` | string(블록) | 예 | 자유 서술, task ID 와 판정 기준 포함 |
| 14 | `owner` | string | 예 | 사람·팀 식별자 또는 `unassigned` |
| 15 | `expires` | string | 예 | `YYYY-MM-DD` 또는 `none` |

빈 값을 허용하는 키는 없습니다. 아직 모르는 값은 빈 문자열로 두지 않고, `owner: unassigned` 처럼 "모른다"를 명시하는 값을 씁니다.

## 4. 키별 명세

### 4.1 `id`

- **의미**: 항목의 영구 식별자. 다른 문서와 판정 기록이 이 값으로 항목을 참조합니다.
- **타입 / 필수**: string / 필수.
- **허용값**: `YYYY-MM-DD-NNN`. `NNN` 은 그날의 3자리 일련번호이며 `001` 부터 시작합니다.
- **작성 지침**: 손으로 정하지 않습니다. `scripts/improvement-log.sh new` 가 발급한 값을 그대로 둡니다. 한 번 발급한 `id` 는 재사용하지 않으며, `rejected` 나 `expired` 로 종결한 항목을 되살릴 때도 새 `id` 를 발급합니다.

```yaml
# 나쁜 예 — 사람이 읽기 좋게 바꾼 식별자. 정렬과 참조가 깨집니다.
id: controller-repository-violation
```

```yaml
# 좋은 예
id: 2026-08-09-001
```

### 4.2 `date`

- **의미**: 사건을 관측한 날짜. 항목을 작성한 날짜가 아니라 실패가 발생한 날짜입니다.
- **타입 / 필수**: string / 필수.
- **허용값**: `YYYY-MM-DD`.
- **작성 지침**: `id` 의 날짜 부분과 다를 수 있습니다(과거 사건을 나중에 기록한 경우). 다를 때는 `evidence` 에 관측 시점을 함께 남깁니다.

```yaml
# 나쁜 예 — 형식이 다르면 정렬과 만료 계산이 불가능합니다.
date: 2026/8/9
```

```yaml
# 좋은 예
date: 2026-08-09
```

### 4.3 `status`

- **의미**: 후보가 승격 경로의 어느 지점에 있는지.
- **타입 / 필수**: enum / 필수.
- **허용값**: `candidate`, `validating`, `promoted`, `rejected`, `expired`.
- **작성 지침**: 새 항목은 언제나 `candidate` 로 시작합니다. 상태는 6절의 전이표에 있는 경로로만 한 단계씩 움직입니다. 상태를 올릴 때는 그 단계가 요구하는 증거를 먼저 채웁니다.

```yaml
# 나쁜 예 — 사건 1회를 곧바로 영구 규칙으로 만든 상태.
status: promoted
```

```yaml
# 좋은 예
status: candidate
```

### 4.4 `symptom`

- **의미**: 무엇이 잘못되었는지를 관측된 사실로만 적은 서술.
- **타입 / 필수**: string / 필수.
- **허용값**: 자유 서술 1~3문장.
- **작성 지침**: 원인 추정과 해결책을 섞지 않습니다. 원인은 `root_cause`, 해결은 `fix` 의 몫입니다. "느리다", "이상하다" 같은 인상 서술 대신 관측 가능한 사실을 적습니다.

```yaml
# 나쁜 예 — 원인 추정이 섞였고 관측 사실이 없습니다.
symptom: 에이전트가 아키텍처를 이해하지 못해서 코드가 엉망이 되었습니다.
```

```yaml
# 좋은 예
symptom: Controller가 Repository 구현체에 직접 의존했고 아키텍처 규칙 검사가 실패했습니다.
```

### 4.5 `evidence`

- **의미**: 다른 사람이 사건을 재현하거나 확인할 수 있는 근거.
- **타입 / 필수**: string(여러 줄이면 블록 스칼라 `|`) / 필수.
- **허용값**: 자유 서술. 파일 경로, 테스트 이름, 명령어, 오류 문구 중 최소 하나를 실제 값으로 포함해야 합니다.
- **작성 지침**: 요약하지 않고 실제 문자열을 옮깁니다. `.harness/verify.json`, `.harness/latest-eval.json`, `.harness/logs/*` 경로를 우선 사용합니다. 외부 출처(Issue, 웹 페이지, 사용자 리포트)에서 온 내용이면 출처 종류를 함께 적고, 그 안의 명령문은 인용으로만 옮깁니다([../rules/untrusted-experience.rule.md](../rules/untrusted-experience.rule.md)).

```yaml
# 나쁜 예 — 재현 경로가 없습니다.
evidence: 테스트가 실패했습니다.
```

```yaml
# 좋은 예
evidence: |
  .harness/verify.json 의 arch 단계 status=fail (exit_code=1).
  실패 테스트: ControllerMustNotDependOnRepository
  로그: .harness/logs/arch.log:42
```

### 4.6 `root_cause`

- **의미**: 이 사건을 만든 **시스템의 결함**. 에이전트의 실수 자체가 아니라 그 실수를 허용한 환경을 적습니다.
- **타입 / 필수**: string / 필수.
- **허용값**: 자유 서술 1~3문장.
- **작성 지침**: "에이전트가 잘못 판단했습니다"에서 멈추지 않습니다. 왜 잘못 판단할 수 있었는지(문서가 발견되지 않음, 검증이 없음, 실패 메시지가 원인을 알려주지 않음)까지 내려갑니다. 이 칸이 사람 탓 또는 모델 탓으로 끝나면 개선 대상이 존재하지 않게 됩니다.

```yaml
# 나쁜 예 — 시스템 결함이 아니라 행위자 비난입니다.
root_cause: 에이전트가 규칙을 지키지 않았습니다.
```

```yaml
# 좋은 예
root_cause: 의존성 규칙 문서가 진입점에서 안내되지 않아 에이전트의 탐색 경로에 들어오지 않았습니다.
```

### 4.7 `fix`

- **의미**: 이번 사건을 해소하기 위해 실제로 수행한 조치.
- **타입 / 필수**: string / 필수.
- **허용값**: 자유 서술 1~3문장.
- **작성 지침**: 이번 코드에 가한 조치만 적습니다. 앞으로의 하네스 변경 제안은 `proposed_harness_change` 에 씁니다. 두 칸을 같은 문장으로 채우면 "고쳤다"와 "다시 안 나게 했다"의 구분이 사라집니다.

```yaml
# 나쁜 예 — 하네스 제안과 섞였습니다.
fix: 의존성을 고치고 앞으로는 아키텍처 규칙을 강화하기로 했습니다.
```

```yaml
# 좋은 예
fix: Controller가 UseCase 계층을 경유하도록 의존성을 변경했습니다.
```

### 4.8 `recurrence_risk`

- **의미**: 같은 종류의 실패가 다시 날 가능성.
- **타입 / 필수**: enum / 필수.
- **허용값**: `low`, `medium`, `high`.
- **작성 지침**: 판정 기준은 다음 표를 씁니다. 인상으로 고르지 않습니다.

| 값 | 기준 |
| --- | --- |
| `low` | 특정 파일·특정 마이그레이션처럼 조건이 사라지면 재현되지 않습니다. |
| `medium` | 같은 모듈이나 같은 작업 유형에서 다시 날 수 있습니다. |
| `high` | 프로젝트 어디서든, 다른 에이전트·다른 작업에서도 같은 조건이 성립합니다. |

```yaml
# 나쁜 예 — 값이 열거형 밖입니다. validate 가 거부합니다.
recurrence_risk: 아마도 높음
```

```yaml
# 좋은 예
recurrence_risk: high
```

### 4.9 `harness_element`

- **의미**: 이 후보가 개선하려는 하네스 요소.
- **타입 / 필수**: string / 필수.
- **허용값**: `HE-1` ~ `HE-15` 중 하나. 인벤토리는 [../references/harness-elements.md](../references/harness-elements.md) 가 소유합니다.
- **작성 지침**: 한 항목은 요소 하나만 지목합니다. 두 요소를 동시에 고쳐야 한다고 판단되면 항목을 둘로 나눕니다. 한 번에 하나씩 바꾸는 원칙은 [../rules/harness-change-control.rule.md](../rules/harness-change-control.rule.md) 를 따릅니다.

```yaml
# 나쁜 예 — 요소를 여러 개 적으면 무엇이 점수를 움직였는지 판정할 수 없습니다.
harness_element: HE-1, HE-4, HE-8
```

```yaml
# 좋은 예
harness_element: HE-4
```

### 4.10 `proposed_harness_change`

- **의미**: 이 실패가 다시 나지 않도록 시스템에 남길 변경 제안.
- **타입 / 필수**: string / 필수.
- **허용값**: 자유 서술 1~3문장.
- **작성 지침**: 특정 클래스명·티켓 번호가 등장하지 않는 일반화된 문장으로 씁니다. 다만 이번 사건 하나만 막는 과잉 일반화(`비동기 처리를 금지한다` 류)도 금지합니다. 적용 범위를 실제 원인만큼만 넓힙니다.

```yaml
# 나쁜 예 — 이번 장애만 보고 프로젝트 전체를 막는 과잉 일반화입니다.
proposed_harness_change: 비동기 처리를 전면 금지합니다.
```

```yaml
# 좋은 예
proposed_harness_change: 아키텍처 규칙의 실패 메시지에 허용된 호출 경로를 포함시키고, 진입점 문서에서 규칙 문서로 가는 링크를 유지합니다.
```

### 4.11 `preferred_enforcement`

- **의미**: 이 lesson 을 어떤 형태로 남길 것인가.
- **타입 / 필수**: enum / 필수.
- **허용값**: `test`, `lint`, `arch-rule`, `hook`, `script`, `doc`, `skill`, `subagent`, `instruction`.
- **작성 지침**: 자연어 지시보다 실행 가능한 제약이 강합니다. 결정적으로 강제할 수 있으면 항상 그쪽을 고르고, `instruction` 은 다른 수단이 모두 불가능할 때만 씁니다. 어느 자리에 둘지의 판정 절차는 [../rules/lesson-placement.rule.md](../rules/lesson-placement.rule.md) 가, 진입점 문서로 들어오는 총량 통제는 [../rules/context-hygiene.rule.md](../rules/context-hygiene.rule.md) 가 담당합니다.

```yaml
# 나쁜 예 — 검증으로 승격 가능한 규칙을 전역 지시로 내렸습니다.
preferred_enforcement: instruction
```

```yaml
# 좋은 예
preferred_enforcement: arch-rule
```

### 4.12 `trust`

- **의미**: 이 후보의 내용이 검증을 통과했는지.
- **타입 / 필수**: enum / 필수.
- **허용값**: `untrusted`, `validated`.
- **작성 지침**: 새 항목은 출처와 무관하게 `untrusted` 로 시작합니다. 에이전트 자신의 관찰도 `untrusted` 입니다. `validated` 로 올리는 것은 승격 판정을 통과한 시점뿐이며, `trust: untrusted` 인 내용은 `templates/`, `rules/`, `skills/`, `hooks/` 로 옮기지 않습니다.

```yaml
# 나쁜 예 — 사내 Issue에서 왔다는 이유로 검증 없이 신뢰했습니다.
trust: validated
```

```yaml
# 좋은 예
trust: untrusted
```

### 4.13 `regression_check`

- **의미**: 승격 판정에서 무엇을 실행하고 무엇을 회귀로 볼 것인지의 사전 약속, 그리고 판정 후에는 그 실행 결과.
- **타입 / 필수**: string(여러 줄이면 블록 스칼라 `|`) / 필수.
- **허용값**: 자유 서술. 대표/held-out task ID 와 판정 기준을 포함해야 합니다.
- **작성 지침**: `candidate` 단계에서는 **미리** 적습니다. 판정을 마친 뒤에는 실제 실행 결과(변경 전후 `score`, 계층별 점수, `.harness/latest-eval.json` 경로)를 덧붙입니다. 판정 후에 기준을 바꿔 적는 것은 평가 조작입니다([../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md)).

```yaml
# 나쁜 예 — 무엇을 실행할지도, 무엇이 실패인지도 없습니다.
regression_check: 문제 없는지 확인합니다.
```

```yaml
# 좋은 예
regression_check: |
  대상: REP-2, REP-5, HLD-1, HLD-3
  기준: 총점이 기준선 이상이고 6개 계층 어느 것도 기준선보다 낮지 않을 것
  근거 파일: .harness/baseline-eval.json, .harness/latest-eval.json
```

### 4.14 `owner`

- **의미**: 이 항목의 다음 행동과 재검토를 책임지는 주체.
- **타입 / 필수**: string / 필수.
- **허용값**: 사람·팀 식별자, 또는 아직 정해지지 않았음을 뜻하는 `unassigned`.
- **작성 지침**: `candidate` 단계에서는 `unassigned` 여도 됩니다. `promoted` 로 올릴 때는 반드시 실제 주체로 바꿉니다. 소유자 없는 승격 항목은 청소 라운드에서 재검토 대상이 되지 못하고 영구 잔존물이 됩니다.

```yaml
# 나쁜 예 — 승격 항목의 소유자가 사람이 아닌 상태입니다.
owner: agent
```

```yaml
# 좋은 예
owner: platform-team
```

### 4.15 `expires`

- **의미**: 이 항목을 다시 판단해야 하는 기한.
- **타입 / 필수**: string / 필수.
- **허용값**: `YYYY-MM-DD` 또는 `none`.
- **작성 지침**: 기본은 날짜입니다. `candidate` 는 기한까지 검증에 착수하지 않으면 `expired` 로 종결합니다. `none` 은 조건이 사라지지 않는 한 유효한 규칙에만 쓰고, 그 근거를 `regression_check` 에 남깁니다. 만료 항목의 처리는 [../rules/harness-gc.rule.md](../rules/harness-gc.rule.md) 를 따릅니다.

```yaml
# 나쁜 예 — 기한을 비워 두면 아무도 다시 보지 않습니다.
expires: ""
```

```yaml
# 좋은 예
expires: 2026-11-09
```

## 5. 최소 예시

전체 예시는 [2026-08-09-001.example.yaml](2026-08-09-001.example.yaml) 에 있고, 빈 템플릿은 [_template.yaml](_template.yaml) 입니다. 같은 사건을 실제 스택의 클래스·도구 이름으로 채운 판은 `../language/<언어>/<kind>/improvement-log.example.yaml` 에 있습니다.

```yaml
id: 2026-08-09-002
date: 2026-08-09
status: candidate
symptom: 통합 테스트 없이 신규 API가 병합되었습니다.
evidence: |
  .harness/verify.json 의 test 단계는 pass 였으나 신규 경로에 해당하는 테스트가 없습니다.
  근거: .harness/logs/test.log 에 해당 엔드포인트 이름이 등장하지 않습니다.
root_cause: 신규 엔드포인트에 대한 테스트 존재 여부를 검증하는 단계가 없습니다.
fix: 누락된 통합 테스트를 추가했습니다.
recurrence_risk: medium
harness_element: HE-5
proposed_harness_change: 엔드포인트 추가 시 대응 테스트 존재를 검사하는 검증 단계를 둡니다.
preferred_enforcement: test
trust: untrusted
regression_check: |
  대상: REP-1, REP-4, HLD-2
  기준: correctness 계층 점수가 기준선 이상일 것
owner: unassigned
expires: 2026-11-09
```

## 6. status 전이표

전이 규범의 정본은 [../rules/promotion-gate.rule.md](../rules/promotion-gate.rule.md) 이며, 아래 표는 같은 전이를 "어떤 키가 채워져 있어야 하는가"의 관점으로 옮긴 것입니다. 조건과 다음 상태는 정본과 같아야 하고, 어긋나면 정본을 따릅니다. 표에 없는 전이는 허용하지 않습니다.

| 현재 status | 조건 | 다음 status | 이 전이 전에 채워져 있어야 하는 키 |
| --- | --- | --- | --- |
| (없음) | 실패·교정·재시도 사건이 1회 관측됨 | `candidate` | `id`, `date`, `symptom`, `evidence`, `root_cause` |
| `candidate` | 프로젝트 전체에 적용 가능한 문장으로 일반화됨 | `validating` | `fix`, `recurrence_risk`, `harness_element`, `proposed_harness_change`, `preferred_enforcement`, `regression_check`(사전 기준) |
| `candidate` | 재현되지 않거나 기존 승격 항목과 중복됨 | `rejected` | `evidence` 에 재현 시도 기록 또는 중복 항목 `id` |
| `candidate` | `expires` 까지 검증에 착수하지 않음 | `expired` | `expires`, 미착수 사유 |
| `validating` | 대표 task 와 held-out task 양쪽에서 회귀 없음 | `promoted` | `regression_check` 의 실행 결과, `owner`(실제 주체), `expires`, `trust: validated` |
| `validating` | 어느 한쪽에서 회귀 또는 점수 하락 | `rejected` | 회귀 layer 와 task ID, 되돌린 변경 범위 |
| `validating` | 일반화 문장이 기존 승격 규칙과 충돌 | `rejected` | 충돌 규칙 ID 와 충돌 지점 |
| `promoted` | `expires` 도달 또는 근거 조건이 코드에서 사라짐 | `expired` | 재검토 일자, 제거 후 회귀 검증 결과 |

`scripts/improvement-log.sh set-status <id> <status>` 는 이 표의 부분집합(`candidate → validating`, `validating → promoted|rejected`, 모든 상태 → `expired`)만 자동 수행합니다. 표에는 있으나 스크립트가 거부하는 전이(`candidate → rejected`)는 종결 근거를 `evidence` 에 남긴 뒤 해당 YAML 의 `status` 만 직접 수정하고 `validate` 를 다시 실행합니다. 스크립트가 거부하는 전이를 다른 값으로 우회해 만들지 않습니다.

`rejected` 와 `expired` 는 종결 상태입니다. 되돌리려면 새 `id` 로 후보를 다시 발급하고, 이전 항목의 `id` 를 새 항목의 `evidence` 에 적습니다.

## 7. validate 가 검사하는 것

`scripts/improvement-log.sh validate` 는 다음을 기계적으로 검사합니다. 위반이 하나라도 있으면 종료 코드 `1` 로 실패합니다.

| 검사 | 실패 시 |
| --- | --- |
| 15개 키가 모두 존재하고 순서가 2절과 일치 | 오류 |
| 스키마에 없는 키가 존재 | 오류 |
| 값이 비어 있음(`owner` 제외) | 오류 |
| `id` 형식이 `YYYY-MM-DD-NNN` | 오류 |
| `date` 형식이 `YYYY-MM-DD` | 오류 |
| `expires` 가 `YYYY-MM-DD` 또는 `none` | 오류 |
| `status`, `recurrence_risk`, `preferred_enforcement`, `trust` 의 열거값 | 오류 |
| `harness_element` 가 `HE-1`~`HE-15` 범위 | 오류 |

`_` 로 시작하는 파일은 디렉터리 전체 검사에서 제외됩니다. `owner` 는 `candidate` 단계에서 비어 있어도 검사를 통과하지만, 이 문서의 규약은 `unassigned` 를 명시적으로 적는 것입니다.

다음 항목은 스크립트가 잡아주지 않으므로 **승격 판정에서 사람이 확인합니다.** 검증이 통과했다는 사실은 승격 조건이 아닙니다.

| 사람이 확인하는 것 | 판정 기준 |
| --- | --- |
| `status: promoted` 인데 `trust` 가 `validated` 인가 | 아니면 승격 무효 |
| `status: promoted` 인데 `owner` 가 실제 주체인가 | `unassigned` 이면 승격 무효 |
| `evidence` 에 실제 경로·오류 문구가 있는가 | 요약만 있으면 반려 |
| `regression_check` 에 task ID 와 판정 기준이 있는가 | 없으면 반려 |
| 파일명과 `id` 가 일치하는가 | 다르면 파일명을 되돌립니다 |

검증에 실패한 항목은 승격 절차의 입력이 되지 못합니다. 검증을 통과시키기 위해 키를 지우거나 값을 형식만 맞춰 채우지 않습니다.

## 관련 문서

- [README.md](README.md)
- [_template.yaml](_template.yaml)
- [2026-08-09-001.example.yaml](2026-08-09-001.example.yaml)
- [../rules/promotion-gate.rule.md](../rules/promotion-gate.rule.md)
- [../rules/untrusted-experience.rule.md](../rules/untrusted-experience.rule.md)
- [../rules/lesson-placement.rule.md](../rules/lesson-placement.rule.md)
- [../rules/harness-gc.rule.md](../rules/harness-gc.rule.md)
- [../references/harness-elements.md](../references/harness-elements.md)
