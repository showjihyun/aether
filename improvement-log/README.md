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

**AD-2(Week 1)에 진입했습니다.** 2026-09-11, P0-7 에서 candidate 13건을 일괄 발급했습니다(`2026-09-11-001` ~ `013`). 전부 `status: candidate`, `trust: untrusted` 이며 `promoted` 는 아직 0건입니다.

이 13건은 Phase 0 실행(P0-1 ~ P0-6, P0-8) 중 실제로 관측되어 `PROVENANCE.md` 8절 이력·커밋 본문·테스트 docstring 에 그림자 로그로만 남아 있던 사건들과, 이 항목을 발급하는 세션 자체에서 재현한 사건(`2026-09-11-004`, guard hook 오탐) 하나를 포함합니다. `validate` 는 통과했지만 사람의 승격 판정(`../harness/rules/promotion-gate.rule.md`)은 아직 거치지 않았습니다 — 그 전까지는 여기 적힌 내용을 결론이 아니라 후보로 다룹니다.

AD-1(Day 1)의 "비어 있는 것이 정상" 규칙([../harness/references/harness-adoption.md](../harness/references/harness-adoption.md) 3.3)은 검증(verify)이 자리 잡기 전 단계의 이야기였습니다. P0-7 이 그 단계를 닫았으므로, 지금부터 남기는 항목은 상상이 아니라 관측입니다.

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
