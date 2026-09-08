# 이 저장소의 개선 후보

이 디렉터리는 aether 를 만들면서 **실제로 관측된** 실패를 담습니다. 스키마·템플릿·상태 전이 규칙은 번들이 소유하며 여기서 복제하지 않습니다.

| 무엇 | 어디 |
| --- | --- |
| 키 명세와 검증 규칙 | [../harness/improvement-log/schema.md](../harness/improvement-log/schema.md) |
| 템플릿 | [../harness/improvement-log/_template.yaml](../harness/improvement-log/_template.yaml) |
| 운용 규칙 | [../harness/improvement-log/README.md](../harness/improvement-log/README.md) |
| 승격 판정 | [../harness/rules/promotion-gate.rule.md](../harness/rules/promotion-gate.rule.md) |
| 배치 판단 | [../harness/rules/lesson-placement.rule.md](../harness/rules/lesson-placement.rule.md) |

## 현재 상태

**비어 있습니다.** 2026-09-08 하네스 도입 시점 기준으로 aether 에서 관측된 실패가 아직 없습니다.

비어 있는 것이 정상입니다. 하네스 도입 단계는 AD-1(Day 1)이고, [../harness/references/harness-adoption.md](../harness/references/harness-adoption.md) 3.3 은 이 단계에서 improvement log 를 만들지 말라고 규정합니다. 남길 실패의 근거가 되는 검증이 먼저 있어야 하기 때문입니다. 지금 채워 넣는 항목은 관측이 아니라 상상입니다.

실운영은 AD-3(Month 1), 로드맵 기준 Phase 4 전후에 시작합니다([../docs/roadmap.md](../docs/roadmap.md)).

## 항목 만들기

손으로 파일을 복사하지 않습니다. 스크립트가 id 를 발급하고 파일명을 맞춥니다.

```bash
./harness/scripts/improvement-log.sh new
./harness/scripts/improvement-log.sh list
./harness/scripts/improvement-log.sh validate
```

## 무엇을 남기는가

작업이 끝날 때 한 가지만 묻습니다.

> 이번 작업에서 에이전트가 겪은 문제 중, 다음 작업을 위해 시스템에 남겨야 할 것은 무엇인가.

남길 값이 있다면 자연어 지시가 아니라 test, lint, arch-rule, hook, script 중 하나로 바꿉니다. 강제력 등급은 [../harness/HARNESS.md](../harness/HARNESS.md) 의 EL-1 … EL-7 을 따르고, 가능한 한 높은 등급을 고릅니다.

aether 에서 특히 높은 등급으로 올려야 할 것은 [../docs/architecture.md](../docs/architecture.md) 의 AR-1 ~ AR-7 입니다. 지금은 문서(EL-2)이고, Phase 0 에서 `.importlinter` 와 `.dependency-cruiser.cjs` 로 옮기면 EL-6 이 됩니다.
