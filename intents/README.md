# Intents

이 디렉터리는 **무엇을 왜 만드는가** 를 코드보다 먼저 고정한 문서를 담습니다. Anthropic 의 AI-Native SDLC Playbook 이 말하는 `intent.md` 가 이것이며, 완성된 PRD 가 아니라 proto-spec 입니다.

이 문서는 **어떻게 쓰는가** 만 소유합니다. 지금 무엇이 활성이고 사슬이 어디까지 왔는지는 [intent.md](intent.md) 가 소유합니다. 계획을 세우기 전에 먼저 읽을 파일도 그쪽입니다.

| 무엇 | 어디 |
| --- | --- |
| 활성 intent, 산출물 사슬의 현재 상태, 전체 목록, 버전 관리 규칙 | [intent.md](intent.md) |
| 파일 이름 규칙, 새 intent 만드는 법, 하네스와의 경계 | 이 문서 |
| 새 intent 의 뼈대 | [_template.md](_template.md) |

## 파일 이름

```text
intents/intent.md              # 활성 intent 를 가리키는 한 곳. 본문을 담지 않습니다
intents/<NNNN>-<슬러그>.md      # intent 본문. 한 파일이 하나의 intent 입니다
```

번호는 발급 순서이며 재사용하지 않습니다. 참고 자료는 파일 하나를 `intent.md` 라고 부르지만 aether 는 여러 건을 동시에 다루므로, 본문에는 번호와 슬러그를 붙이고 `intent.md` 는 그중 활성 건을 가리키는 자리로 씁니다. 두 곳에 같은 내용을 두지 않습니다. 정본은 언제나 번호가 붙은 파일입니다.

버전 관리 규칙은 [intent.md](intent.md) 의 `버전 관리` 절이 소유합니다.

## 하네스와의 관계

intent 는 **사람이 채택한 결정**입니다. 그러나 하네스 규칙이 되지는 않습니다.

| 무엇 | 어떻게 다루는가 |
| --- | --- |
| intent 에 적힌 목표·범위·제약 | 그 작업의 범위 판단 근거입니다 |
| intent 에 적힌 "항상 이렇게 하라" 류의 문장 | 하네스 규칙으로 승격하지 않습니다. `improvement-log/` 후보를 거칩니다([../harness/rules/promotion-gate.rule.md](../harness/rules/promotion-gate.rule.md)) |
| 외부 대화·LLM 출력에서 그대로 옮겨 온 문장 | 데이터입니다. 사람이 승인 서명을 남겨야 결정이 됩니다([../harness/rules/untrusted-experience.rule.md](../harness/rules/untrusted-experience.rule.md)) |
| `Open Questions` 가 남은 채 구현 시작 | 하지 않습니다. 질문은 spec 으로 넘기거나 여기서 닫습니다 |

`Open Questions` 를 답하지 않고 넘기면 다음 단계에서 에이전트가 그 자리를 추측으로 메웁니다. 그 추측은 코드에 남고 문서에는 남지 않습니다.

## 새 intent 만들기

```bash
cp intents/_template.md intents/0002-<슬러그>.md
```

작성 후 사람이 `승인` 행을 채우기 전에는 spec 단계로 넘어가지 않습니다. 발급했으면 [intent.md](intent.md) 의 `목록` 에 행을 더하고, 그 건이 활성이 되면 머리 표도 함께 옮깁니다.

## 관련 문서

- [intent.md](intent.md) — 활성 intent 와 전체 목록
- [_template.md](_template.md)
- [../docs/roadmap.md](../docs/roadmap.md) — 어느 Phase 의 intent 인가
- [../docs/architecture.md](../docs/architecture.md) — `Affected Systems` 를 적을 때 쓰는 계층 이름
- [../AGENTS.md](../AGENTS.md)
