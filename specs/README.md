# Specs

이 디렉터리는 **승인된 intent 를 요구사항과 설계로 옮긴 문서**를 담습니다. AI-Native SDLC Playbook 의 `spec.md` 가 이것입니다(출처: [../PROVENANCE.md](../PROVENANCE.md) 6절). intent 가 "무엇을 왜" 라면 spec 은 "무엇을 만족해야 하고 경계가 어디인가" 입니다. "어느 파일을 어떤 순서로" 는 다음 단계인 plan 이 답합니다.

이 디렉터리는 첫 spec 이 나올 때 만들었습니다. 사슬의 현재 위치는 [../intents/intent.md](../intents/intent.md) 가 소유합니다.

## 파일 이름

```text
specs/<intent 와 같은 번호>-<같은 슬러그>.md
```

intent 하나에 spec 하나입니다. 번호가 같아야 두 문서가 짝임을 찾을 수 있습니다.

## spec 이 답하는 것과 답하지 않는 것

| 답합니다 | 답하지 않습니다 |
| --- | --- |
| 무엇을 만족해야 하는가 — 판정 방법이 붙은 요구사항 | 어느 파일을 어떤 순서로 고치는가 (plan) |
| 경계와 계약 — 구조, 인터페이스, 데이터, 검증 단계 | 구현 코드 |
| 우려 지점 — 정책 충돌, 열린 게이트, 사람 검토가 필요한 곳 | intent 가 이미 정한 문제와 범위 (반복하지 않고 링크합니다) |
| 이 spec 을 승인하면 무엇이 결정되는가 | 승인 없이 내려도 되는 결정 |

## 절 구성

모든 spec 은 같은 절을 같은 순서로 둡니다. 순서가 같아야 두 번째 spec 을 읽는 사람이 첫 번째에서 배운 위치 감각을 그대로 씁니다.

| # | 절 | 내용 |
| --- | --- | --- |
| 0 | 머리 표 | 번호, 근거 intent, 상태, 승인, 후속 plan |
| 1 | 요구사항 | `R-n`. intent 의 `Proposed Outcome` 과 `Constraints` 각각에서 유도합니다. 판정 방법이 없는 요구사항은 요구사항이 아닙니다 |
| 2 | 설계 | 요구사항을 만족시키는 구조와 계약. 계층·용어는 [../docs/architecture.md](../docs/architecture.md), [../docs/domain.md](../docs/domain.md) 의 것만 씁니다 |
| 3 | 우려 지점 | 플레이북이 요구하는 "areas of concern". 서로 부딪히는 정책, 닫히지 않은 게이트, 🔒 사람 검토 |
| 4 | 결정 요청 | `D-n`. 이 spec 을 승인하면 채택되는 결정. intent 의 Open Questions 에 대한 답이 여기 옵니다 |
| 5 | 검증 매핑 | `R-n` ↔ 작업 단위 ↔ 판정 명령. 빠진 R 이 있으면 설계가 덜 된 것입니다 |
| 6 | Non-goals | intent 의 것을 반복하고, 설계하면서 새로 뺀 것을 더합니다 |

## 승인

intent 와 같습니다. 사람이 `승인` 행을 채우기 전에는 plan 으로 넘어가지 않습니다.

spec 을 승인하는 것은 **4절 `결정 요청` 을 전부 채택하는 것**입니다. 일부만 채택한다면 그 항목을 먼저 고친 뒤 승인합니다. 승인된 spec 과 다른 결정이 코드에 들어가면 그것은 불일치이고, 어느 쪽을 고칠지는 사람이 정합니다.

## 버전 관리

intent 와 spec 은 짝으로 커밋합니다. 요구사항과 그때의 결정이 한 기록으로 남아야 "왜 이렇게 만들었는가" 를 나중에 복원할 수 있습니다. 승인 뒤에 spec 을 고치면 머리 표의 `개정` 행에 날짜와 이유를 남깁니다. 승인 전에는 자유롭게 고칩니다.

## 목록

| 번호 | 제목 | 근거 intent | 상태 |
| --- | --- | --- | --- |
| [0001](0001-phase-0-foundation.md) | Phase 0 — Architecture & Foundation | [intents/0001](../intents/0001-phase-0-foundation.md) | 승인됨 |

## 관련 문서

- [../intents/intent.md](../intents/intent.md) — 활성 intent 와 사슬의 현재 위치
- [../intents/README.md](../intents/README.md) — intent 작성 규칙
- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — spec 이 다루는 작업 단위
- [../AGENTS.md](../AGENTS.md)
