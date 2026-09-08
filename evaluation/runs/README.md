# 실행 기록

이 디렉터리는 대표 task(`REP-*`)와 held-out task(`HLD-*`)를 실제로 실행한 결과를 담습니다. 과제 한 건당 한 파일이며 이름은 `<YYYY-MM-DD>-<task-id>.md` 입니다.

`harness/scripts/eval.sh` 는 이 과제들을 실행하지 않습니다. 그 스크립트는 `harness.config` 의 `HARNESS_STEPS` 만 집계하며, `.harness/latest-eval.json` 은 "하네스 자신이 성립하는가" 에만 답합니다. 과제 합격 기준의 판정은 이 디렉터리가 소유합니다. 두 근거는 서로를 대체하지 않습니다.

형식은 [../../harness/evaluation/runs/_template.md](../../harness/evaluation/runs/_template.md) 를 따릅니다. 승격 판정에서 이 파일들이 하는 역할은 [../../harness/rules/promotion-gate.rule.md](../../harness/rules/promotion-gate.rule.md) 의 PG-3, PG-6 입니다.

기록이 없다면 그것은 "회귀가 없다" 는 뜻이 아니라 **판정하지 않았다** 는 뜻입니다. 그 상태에서는 candidate 를 `promoted` 로 올리지 않습니다.

## 현재 상태

비어 있습니다. 제품 코드가 없어 어떤 task 도 실행할 수 없습니다([../README.md](../README.md) "지금 이 세트의 상태").
