# 실행 기록 템플릿

이 파일을 복사해 프로젝트의 `evaluation/runs/<YYYY-MM-DD>-<task-id>.md` 로 만듭니다. task 한 건당 한 파일입니다.

이 기록이 필요한 이유는 [../../scripts/eval.sh](../../scripts/eval.sh) 가 task 를 실행하지 않기 때문입니다. `eval.sh` 는 `harness.config` 의 `HARNESS_STEPS` 만 집계하고, 그 산출인 `.harness/latest-eval.json` 은 "하네스 자신이 성립하는가" 에만 답합니다. task 합격 기준의 판정은 이 파일이 소유하며, 승격은 두 근거를 함께 봅니다([../../rules/promotion-gate.rule.md](../../rules/promotion-gate.rule.md) PG-3, PG-6).

## 머리말

| 키 | 내용 |
| --- | --- |
| `task` | task ID 하나(`REP-1`, `HLD-3`). 여러 task 를 한 파일에 담지 않습니다 |
| `candidate` | 이 실행이 판정하는 improvement log 항목 id |
| `harness_rev` | 실행 시점의 커밋 해시. 어느 하네스를 평가했는지 없으면 재현할 수 없습니다 |
| `fresh_session` | `yes` / `no`. 앞선 대화를 이어 실행하면 진입점 문서의 발견 여부를 측정할 수 없습니다 |
| `verdict` | `pass` / `fail` / `not-run` 셋 중 하나 |

## 본문

task 문서의 합격 기준 항목을 **한 줄씩 그대로 옮겨 적고** 관측 결과와 근거를 답니다. 근거는 종료 코드, 로그 경로, 변경된 파일 목록처럼 다시 확인할 수 있는 것이어야 합니다. "잘 동작함" 은 근거가 아닙니다.

판정하지 못한 항목은 `not-run` 으로 남깁니다. 실행하지 않은 항목을 통과로 적는 것이 이 기록이 막으려는 실패입니다. 항목이 하나라도 `not-run` 이면 파일 전체의 `verdict` 도 `not-run` 입니다.

## 예시

    task: REP-4
    candidate: 2026-08-09-001
    harness_rev: 0000000
    fresh_session: yes
    verdict: pass

    | 합격 기준 | 관측 | 근거 |
    | --- | --- | --- |
    | 추가 전 exit 0, 추가 후 exit 2 를 모두 실행 결과로 제시 | 충족 | 추가 전 exit 0 / 추가 후 exit 2, 명령과 출력을 아래 인용 |
    | 무관한 파일이 여전히 exit 0 | 충족 | AGENTS.md exit 0 |
    | self-check.sh --only protection 통과 | 충족 | .harness/logs/protection.log |
