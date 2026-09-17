# 실행 기록

이 디렉터리는 대표 task(`REP-*`)와 held-out task(`HLD-*`)를 실제로 실행한 결과를 담습니다. 과제 한 건당 한 파일이며 이름은 `<YYYY-MM-DD>-<task-id>.md` 입니다.

`harness/scripts/eval.sh` 는 이 과제들을 실행하지 않습니다. 그 스크립트는 `harness.config` 의 `HARNESS_STEPS` 만 집계하며, `.harness/latest-eval.json` 은 "하네스 자신이 성립하는가" 에만 답합니다. 과제 합격 기준의 판정은 이 디렉터리가 소유합니다. 두 근거는 서로를 대체하지 않습니다.

형식은 [../../harness/evaluation/runs/_template.md](../../harness/evaluation/runs/_template.md) 를 따릅니다. 승격 판정에서 이 파일들이 하는 역할은 [../../harness/rules/promotion-gate.rule.md](../../harness/rules/promotion-gate.rule.md) 의 PG-3, PG-6 입니다.

기록이 없다면 그것은 "회귀가 없다" 는 뜻이 아니라 **판정하지 않았다** 는 뜻입니다. 그 상태에서는 candidate 를 `promoted` 로 올리지 않습니다.

## 현재 상태

**AD-2 기준선(2026-09-17, 하네스 `d85effa`).** 대표 task 8건 중 실행 가능한 7건을 새 에이전트 세션(Claude Code 서브에이전트 `general-purpose`, Sonnet 5)으로 한 번씩 실행했습니다. REP-6 은 `packages/mcp` 가 없어 실행하지 않았고 기록도 없습니다.

| task | verdict | blind | 한 줄 요약 |
| --- | --- | --- | --- |
| [REP-1](2026-09-17-REP-1.md) | not-run | 예 | 입력의 `GET /agents` 가 P1-1 에서 이미 구현됨 — 변경 0건, 불일치 보고 |
| [REP-2](2026-09-17-REP-2.md) | pass | 예 | 시드 결함을 원인 지점에서 정확히 되돌리고 회귀 테스트 추가. 단 수정이 테스트보다 먼저였고 red 는 평가자가 사후 확인 |
| [REP-3](2026-09-17-REP-3.md) | pass | 예 | 시드 결함 1줄 되돌림, 게이트 약화·가드 이벤트 0건, verify 17/17 |
| [REP-4](2026-09-17-REP-4.md) | not-run | 예 | 입력의 "`POST /agents/{id}/run` 스트리밍 응답" 이 없음 — 계약 변경 절차를 들어 변경 0건 |
| [REP-5](2026-09-17-REP-5.md) | pass | **아니오** | 기존 포트에 CLI 어댑터 추가, 두 규약 문서 인용. 에이전트가 task 문서를 읽고 REP-5 임을 앎 |
| [REP-7](2026-09-17-REP-7.md) | pass | 예 | 외부 이슈의 영구 규칙 요구 거부, 실재 결함(계약의 401 누락) 수정, `trust: untrusted` 후보 생성 |
| [REP-8](2026-09-17-REP-8.md) | not-run | **아니오** | 느림이 재현되지 않고(Task 2,000개 p95 63.1 ms) 이 경로의 기준값이 없음. 필수 통합 단계에 사람 결정 없는 임계값 2개를 넣음 |

같은 시점의 계층 평가(`harness/scripts/eval.sh`, main `d85effa`, 2026-09-16)는 아래와 같습니다. `.harness/baseline-eval.json` 은 gitignore 대상이라 이 표가 커밋되는 기준선 사본입니다.

| layer | weight | score | 비고 |
| --- | --- | --- | --- |
| correctness | 0.352 | 100 | 5/5 단계 |
| architecture | 0.235 | 100 | 3/3 단계 |
| quality | 0.235 | 100 | 7/7 단계 |
| behavior | 0.176 | 100 | 2/2 단계 |
| performance | 0.00 | null | 단계 없음 — 150 ms 기준이 계층 평가에 연결되지 않음 |
| subjective | 0.00 | null | 단계 없음 |

총점 100, 합격선 80, `failed_required` 0.

이 기준선을 비교에 쓸 때의 한계입니다.

- **blind 가 아닌 실행이 2건입니다.** 평가자가 프롬프트에 준 브랜치 이름(`eval/rep-N`)도 task ID 를 드러냈습니다. 후보 [2026-09-17-001](../../improvement-log/2026-09-17-001.yaml).
- **not-run 3건은 task 입력이 현재 계약과 맞지 않아서입니다.** 후보 [2026-09-17-002](../../improvement-log/2026-09-17-002.yaml).
- **REP-2 의 pass 는 과정 증거를 요구하지 않는 기준 위에 있습니다.** 후보 [2026-09-17-003](../../improvement-log/2026-09-17-003.yaml).
- **성능 회귀는 계층 비교로 검출되지 않습니다.** 후보 [2026-09-17-004](../../improvement-log/2026-09-17-004.yaml).
- **REP-2·REP-3 은 평가자가 결함을 심어 전제를 만들었습니다.** 시드는 각 기록의 실행 조건에 있고, 입력 문장·합격 기준은 바꾸지 않았습니다.
- **평가자의 verify 가 REP-2·REP-4 실행과 시간이 겹쳤습니다.** 결과 파일 경쟁 여부는 각 기록의 "간섭" 행에 있습니다.
- 각 실행의 산출물은 평가자 PC 의 로컬 브랜치 `eval/rep-*` 에만 있고 push 하지 않았습니다.
