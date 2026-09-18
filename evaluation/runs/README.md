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

`performance` 의 공백은 2026-09-18 에 메웠습니다(improvement log `2026-09-17-004`). `harness.config` 에 `bench` 단계와 `HARNESS_BENCH_P95_MAX_MS=150` 이 들어가 단계는 18개가 되었고, 같은 날 다시 실행한 계층 평가는 아래와 같습니다. 기준선(`.harness/baseline-eval.json`)도 이 값으로 다시 고정했습니다.

| layer | weight | score | 비고 |
| --- | --- | --- | --- |
| correctness | 0.315 | 100 | 5/5 단계 |
| architecture | 0.21 | 100 | 3/3 단계 |
| quality | 0.21 | 100 | 7/7 단계 |
| behavior | 0.157 | 100 | 2/2 단계 |
| performance | 0.105 | 100 | 1/1 단계 — Run 생성 p95 42.5 ms(로컬) · 68.8 ms(CI), 기준 150 ms |
| subjective | 0.00 | null | 단계 없음 |

총점 100, 합격선 80, `failed_required` 0.

이 기준선을 비교에 쓸 때의 한계입니다.

- **blind 가 아닌 실행이 2건입니다.** 평가자가 프롬프트에 준 브랜치 이름(`eval/rep-N`)도 task ID 를 드러냈습니다. 후보 [2026-09-17-001](../../improvement-log/2026-09-17-001.yaml).
- **not-run 3건은 task 입력이 현재 계약과 맞지 않아서입니다.** 후보 [2026-09-17-002](../../improvement-log/2026-09-17-002.yaml).
- **REP-2 의 pass 는 과정 증거를 요구하지 않는 기준 위에 있습니다.** 후보 [2026-09-17-003](../../improvement-log/2026-09-17-003.yaml).
- **성능 회귀는 계층 비교로 검출되지 않았습니다.** 후보 [2026-09-17-004](../../improvement-log/2026-09-17-004.yaml) — 2026-09-18 에 `bench` 단계를 넣어 해소했습니다(위 표).
- **REP-2·REP-3 은 평가자가 결함을 심어 전제를 만들었습니다.** 시드는 각 기록의 실행 조건에 있고, 입력 문장·합격 기준은 바꾸지 않았습니다.
- **평가자의 verify 가 REP-2·REP-4 실행과 시간이 겹쳤습니다.** 결과 파일 경쟁 여부는 각 기록의 "간섭" 행에 있습니다.
- 각 실행의 산출물은 push 하지 않았고, 평가자 PC 의 저장소 밖 git 번들(`C:\WorkSpace\aether-eval-evidence\2026-09-17-ad2-baseline.bundle`)에 있습니다. 다음 실행이 보지 못하도록 로컬 브랜치는 지웠습니다.

### 개정 입력 첫 실행 (2026-09-17, 하네스 `3bac2e9`)

REP-1 · REP-4 · REP-8 의 입력을 improvement log `2026-09-17-002` 에 따라 다시 쓰고(PR #33) 같은 날 한 번씩 실행했습니다. 훅·규칙·스크립트·`harness.config` 는 `d85effa` 와 같습니다. 파일 이름의 `-r2` 는 같은 날 같은 task 의 두 번째 실행이라는 뜻입니다.

| task | verdict | blind | 한 줄 요약 |
| --- | --- | --- | --- |
| [REP-1](2026-09-17-REP-1-r2.md) | pass | 예 | 이름 필터를 라우터 → 포트 → 유스케이스 → 저장소 순서로 추가, 계약·SDK 갱신, 단위·통합·SDK 테스트 추가 |
| [REP-4](2026-09-17-REP-4-r2.md) | fail | 예 | keep-alive 구현과 테스트는 좋았으나 실측이 가짜 이벤트 소스의 로컬 uvicorn 뿐 — 캡처 파일·컨테이너 로그·`run.finished` 종료 미관측 |
| [REP-8](2026-09-17-REP-8-r2.md) | fail | 부분 | 시드 N+1 을 정확히 고쳐 p95 35.8 ms. 그러나 개선 전을 측정하지 않고 추정만 함. 성능 기준 문서에서 task ID 를 알아 코드 주석에 적음 |

세 건 모두 not-run 이 아니므로 `2026-09-17-002` 의 회귀 확인 기준(입력 개정 뒤 not-run 0건)은 충족했습니다. 이 세트로 비교할 때의 기준선은 **REP-1 · 2 · 3 · 5 · 7 pass, REP-4 · 8 fail** 입니다.

이번 실행에서 평가자는 브랜치 이름에 task ID 를 쓰지 않았고, 앞선 증거 브랜치를 저장소 밖으로 옮겼습니다. 그래도 REP-8 은 `../README.md` 의 성능 기준 행("넘으면 REP-8 실패")에서 task ID 를 알았습니다 — `2026-09-17-001` 의 근거에 더했습니다. 산출물은 같은 폴더의 `rerun-rep1.bundle` · `rerun-rep4.bundle` · `rerun-rep8.bundle` 에 있습니다.
