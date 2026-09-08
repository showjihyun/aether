# 반복 예산과 종료 조건 규칙 (LB)

이 문서는 에이전트를 반복 실행하는 루프를 설계하거나 실행하기 직전에 읽습니다. `scripts/loop.sh` 를 돌리기 전, 새로운 자동 반복 절차를 추가하기 전, 그리고 루프가 같은 실패를 반복하고 있을 때 중단 여부를 판정할 때 이 문서를 근거로 삼습니다. 계속 반복한다고 반드시 개선되는 것은 아니며, 종료 조건이 없는 루프는 개선이 아니라 소모입니다.

## 규칙

| ID | 규칙 |
| --- | --- |
| **LB-1** | 종료 조건 없는 루프를 실행하지 않습니다. 루프를 시작하기 전에 아래 다섯 가지 종료 조건이 모두 선언되어 있어야 합니다. |
| **LB-2** | `while true` 를 문자 그대로 구현하지 않습니다. 모든 반복은 회차 카운터와 상한을 가지며, 상한에 도달하면 조건 없이 종료합니다. |
| **LB-3** | 같은 자리에서 맴도는 상태를 감지해 중단합니다. 동일 실패가 3회 반복되거나 2라운드 연속으로 개선이 없으면 루프를 종료합니다. |
| **LB-4** | 예산을 초과하면 중단합니다. 반복 횟수, 시간, 비용 중 어느 하나라도 선언된 예산을 넘으면 다음 라운드를 시작하지 않습니다. |
| **LB-5** | 보안에 민감한 변경이 필요하다고 판정되면 자동으로 적용하지 않고 사람 검토로 에스컬레이션한 뒤 루프를 종료합니다. |
| **LB-6** | 중단할 때는 지금까지의 증거와 남은 실패를 사람에게 넘깁니다. 조용히 종료하거나 성공처럼 보고하지 않습니다. |
| **LB-7** | 예산과 종료 조건은 `harness.config` 에 선언되고, 루프 실행 중에 상향되지 않습니다. 에이전트가 자기 상한을 늘리는 변경을 제안하면 그 라운드는 중단 대상입니다. |

### 정본 종료 조건

아래 값은 하네스 전체가 공유하는 고정 상수입니다. 프로젝트별 조정은 `harness.config` 재정의로만 하고, 루프 실행 중에는 바꾸지 않습니다.

| 조건 | 값 | `harness.config` 키 | 도달 시 동작 |
| --- | --- | --- | --- |
| Maximum Iterations | 8 | `HARNESS_MAX_ITERATIONS` | 중단 |
| 동일 실패 반복 | 3회 | `HARNESS_MAX_SAME_FAILURE` | 중단 |
| 개선 없는 연속 라운드 | 2라운드 | `HARNESS_NO_IMPROVEMENT_ROUNDS` | 중단 |
| 보안 민감 변경 | 판정 시 즉시 | (판정 결과) | 사람 검토로 에스컬레이션 후 중단 |
| 예산 초과 | 선언된 반복·시간·비용 상한 | `HARNESS_MAX_ITERATIONS` 및 프로젝트 예산 선언 | 중단 |

```bash
# harness.config 발췌 — 루프 시작 전에 이 값들이 모두 선언되어 있어야 합니다.
HARNESS_MAX_ITERATIONS=8
HARNESS_MAX_SAME_FAILURE=3
HARNESS_NO_IMPROVEMENT_ROUNDS=2
HARNESS_THRESHOLD=80
HARNESS_AGENT_CMD=""
```

## 판정 절차

각 라운드는 다음 순서로 중단 여부를 먼저 판정하고, 판정을 통과했을 때만 에이전트를 호출합니다. 판정 입력은 `.harness/loop-state.json` 에 누적된 반복 상태이며, 이 파일의 스키마는 [../scripts/loop.sh](../scripts/loop.sh) 가 소유합니다. 직전 라운드의 검증·평가 결과는 `.harness/verify.json` 과 `.harness/latest-eval.json` 에서 읽습니다.

1. **선언 확인 (LB-1, LB-2)** — `harness.config` 에서 `HARNESS_MAX_ITERATIONS`, `HARNESS_MAX_SAME_FAILURE`, `HARNESS_NO_IMPROVEMENT_ROUNDS` 를 읽습니다. 하나라도 비어 있으면 루프를 시작하지 않고 종료합니다.
2. **반복 상한 (LB-2, LB-4)** — `.harness/loop-state.json` 의 현재 회차가 `HARNESS_MAX_ITERATIONS` 이상이면 중단합니다. 기본값은 8 입니다.
3. **성공 종료** — 직전 `.harness/verify.json` 의 `status` 가 `pass` 이고 `.harness/latest-eval.json` 의 `pass` 가 `true` 이면 성공으로 종료합니다. 목표를 이미 달성한 뒤 추가 반복을 돌리지 않습니다.
4. **동일 실패 (LB-3)** — 직전 라운드의 실패 시그니처(실패한 step id 와 요약)를 `.harness/loop-state.json` 에 누적된 직전 시그니처들과 비교합니다. 동일 시그니처가 연속 3회면 중단합니다.
5. **정체 (LB-3)** — `.harness/latest-eval.json` 의 `score` 를 직전 라운드들과 비교합니다. 2라운드 연속으로 점수가 오르지 않고 `failed_required` 도 줄지 않으면 중단합니다.
6. **보안 민감 판정 (LB-5)** — 다음 라운드에서 제안된 변경이 인증·인가, 비밀값, 암호화, 권한 경계, 의존성 공급망, 배포 자격 증명 중 어느 하나에 닿으면 적용하지 않고 사람 검토로 에스컬레이션한 뒤 종료합니다.
7. **예산 (LB-4, LB-7)** — 누적 시간과 비용이 선언된 예산 안에 있는지 확인합니다. 초과하면 중단합니다. 이 단계에서 상한을 올려 계속하는 선택지는 없습니다.
8. **라운드 실행** — 1~7 을 모두 통과했을 때만 `HARNESS_AGENT_CMD` 를 호출하고, 결과를 `.harness/loop-state.json` 에 기록한 뒤 1 로 돌아갑니다.
9. **인계 (LB-6)** — 어떤 이유로 중단하든, 중단 사유 · 실행한 라운드 수 · 마지막 `.harness/verify.json` 과 `.harness/latest-eval.json` 경로 · 남아 있는 실패 목록 · `largest_failure` 를 함께 출력합니다. 반복될 만한 실패였다면 `improvement-log/` 에 candidate 를 남깁니다.

## 위반 예시와 교정

### 예시 1 — 종료 조건 없는 반복

검증이 통과할 때까지 에이전트를 계속 호출하는 스크립트를 작성했습니다.

```bash
# 위반: 상한도 정체 감지도 없습니다.
while true; do
  $HARNESS_AGENT_CMD
  ./scripts/verify.sh && break
done
```

- 위반: LB-1 과 LB-2 를 동시에 어깁니다. 검증이 구조적으로 통과할 수 없는 상태라면 이 루프는 예산을 모두 소모할 때까지 멈추지 않습니다.
- 교정: 회차 카운터와 상한을 두고, 매 라운드 시작 시 판정 절차 1~7 을 먼저 실행합니다.

```bash
# 교정: 상한과 판정을 앞에 둡니다.
iteration=0
while [ "$iteration" -lt "$HARNESS_MAX_ITERATIONS" ]; do
  iteration=$((iteration + 1))
  should_stop && break
  $HARNESS_AGENT_CMD
  ./scripts/verify.sh || record_failure
done
report_handoff
```

### 예시 2 — 같은 실패를 8회까지 반복

동일한 통합 테스트가 매 라운드 같은 이유로 실패했지만, 루프는 상한인 8회를 모두 소모한 뒤에야 멈췄습니다.

- 위반: LB-3 의 동일 실패 3회 조건을 판정하지 않았습니다. 4회차부터 8회차까지는 예산만 소모했습니다.
- 교정: 실패 시그니처를 `.harness/loop-state.json` 에 누적하고, 연속 3회에서 중단합니다. 중단 시 LB-6 에 따라 반복된 실패 로그와 재현 절차를 사람에게 넘깁니다. 이 실패가 하네스의 공백에서 비롯되었다면 `improvement-log/` 에 candidate 를 남깁니다.

### 예시 3 — 실행 중 상한 상향

7회차에서 목표에 근접했다고 판단한 에이전트가 `harness.config` 의 `HARNESS_MAX_ITERATIONS` 를 8 에서 20 으로 바꾸고 반복을 이어갔습니다.

- 위반: LB-7 위반입니다. 예산은 루프 밖에서 사람이 정하는 값이며, 루프 안에서 스스로 늘릴 수 있다면 예산이 아닙니다.
- 교정: 8 회차에서 중단하고 결과를 인계합니다. 상한이 실제로 부족하다면 사람이 `harness.config` 를 갱신하고 루프를 다시 시작합니다. 상한 상향 제안 자체는 `improvement-log/` 의 candidate 로 남깁니다.

## 관련 문서

- [../scripts/loop.sh](../scripts/loop.sh) — 종료 조건을 구현하고 `.harness/loop-state.json` 을 기록하는 진입점
- [../scripts/harness.config.example](../scripts/harness.config.example) — 예산과 종료 조건 선언 예시
- [evaluation-integrity.rule.md](evaluation-integrity.rule.md) — 반복 중 평가를 공략하기 시작하는 상태의 판정
- [untrusted-experience.rule.md](untrusted-experience.rule.md) — 중단 후 남긴 candidate 의 신뢰 경계
- [../references/inner-outer-loop.md](../references/inner-outer-loop.md) — Inner Loop 와 Outer Loop 의 구분
