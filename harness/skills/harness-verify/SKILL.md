---
name: harness-verify
description: 통합 검증 명령 harness/scripts/verify.sh 를 실행하고 그 결과를 근거로 실패를 하나씩 좁혀 고치는 Inner Loop 실행 스킬입니다. 구현·수정 작업을 끝까지 통과시켜야 할 때, 테스트·타입체크·lint·아키텍처 검사 중 무엇이 왜 실패했는지 확인해야 할 때, 수정 후 재검증이 필요할 때, 반복을 언제 멈춰야 하는지 판단해야 할 때 사용합니다. 하네스 자체를 바꾸거나 회고로 개선안을 만드는 작업은 이 스킬의 범위가 아니며 harness-retro 와 harness-promote 가 담당합니다.
metadata:
  short-description: verify.sh 기반 Inner Loop 실행과 종료 조건 판정
---

# Harness Verify

이 스킬은 Inner Loop, 즉 지금 맡은 작업 하나를 검증 가능한 상태로 끝내기 위한 반복을 실행할 때 읽습니다. 현재 작업이 통과 상태가 아니거나, 무엇이 실패하는지 확인하지 못한 채 코드를 고치려는 상황이면 먼저 이 절차를 따릅니다. 미래 작업을 더 잘하기 위한 반복은 Outer Loop이며 [../../references/inner-outer-loop.md](../../references/inner-outer-loop.md) 에서 두 루프의 경계를 확인합니다.

## 절차

### 1. verify 실행

프로젝트 루트에서 통합 검증 명령 하나를 실행합니다. 개별 도구를 따로 실행해 결과를 눈으로 합치지 않습니다.

```bash
harness/scripts/verify.sh
```

스택 감지 결과나 실행할 단계를 확인해야 하면 먼저 도움말을 읽습니다.

```bash
harness/scripts/verify.sh --help
```

단계 구성을 바꾸어야 하는 경우에도 이 스킬 안에서는 바꾸지 않습니다. `harness.config` 변경은 하네스 변경이며 [../../rules/harness-change-control.rule.md](../../rules/harness-change-control.rule.md) 의 통제를 받습니다.

### 2. 실패 증거 수집

결과는 항상 `.harness/verify.json` 에서 읽습니다. 터미널 스크롤을 기억에 의존해 요약하지 않습니다.

```bash
cat .harness/verify.json
```

`jq` 가 있으면 실패한 단계만 추립니다.

```bash
jq '.status, .failed_required, [.steps[] | select(.status != "pass")]' .harness/verify.json
```

`jq` 가 없으면 로그 파일 경로를 직접 확인합니다.

```bash
grep -o '"log": "[^"]*"' .harness/verify.json
```

각 실패 단계에 대해 다음 네 가지를 근거로 확보합니다.

| 항목 | 출처 |
| --- | --- |
| 실패한 단계 id | `.harness/verify.json` 의 `steps[].id` |
| 평가 계층 | `steps[].layer` (`correctness` / `architecture` / `quality` / `behavior` / `performance` / `subjective`) |
| 필수 여부 | `steps[].required` 와 `failed_required` |
| 실제 오류 메시지 | `steps[].log` 가 가리키는 로그 파일 |

로그 파일을 열어 실제 오류 문구를 확인하기 전에는 원인을 단정하지 않습니다.

### 3. 가장 큰 실패 하나 선택

한 번의 반복에서는 실패 하나만 다룹니다. 선택 기준은 다음 순서입니다.

1. `required: true` 인 단계가 실패했다면 그 중에서 고릅니다.
2. 여러 개라면 다른 실패의 원인일 가능성이 높은 것을 고릅니다. 컴파일·타입체크 실패가 테스트 실패보다 먼저입니다.
3. 계층이 같다면 오류 메시지가 가장 구체적인 것을 고릅니다.

선택한 실패와 선택하지 않은 실패를 함께 기록합니다. 남은 실패는 다음 반복의 대상이며 버리는 것이 아닙니다.

### 4. 범위를 좁힌 변경 하나 적용

선택한 실패를 없애기 위한 최소 변경만 적용합니다. 같은 반복에서 리팩터링, 포맷 정리, 무관한 파일 정리를 함께 하지 않습니다.

변경 전에 다음을 확인합니다.

- 이 변경이 실패의 원인을 제거하는가, 아니면 증상만 가리는가.
- 이 변경이 검증 기준 자체를 건드리는가. 건드린다면 중단하고 [../../rules/evaluation-integrity.rule.md](../../rules/evaluation-integrity.rule.md) 를 따릅니다.
- 이 변경이 보안 민감 영역(인증, 권한, 비밀값, 네트워크 경계)에 닿는가. 닿는다면 사람 검토로 에스컬레이션합니다.

### 5. 재검증

같은 명령으로 다시 검증합니다.

```bash
harness/scripts/verify.sh
```

`.harness/verify.json` 을 다시 읽고 다음을 비교합니다.

- 선택했던 단계가 `pass` 로 바뀌었는가.
- `failed_required` 가 줄었는가.
- 이전에 통과하던 단계가 새로 실패하지 않았는가.

이전에 통과하던 단계가 실패했다면 그 변경은 회귀이므로 되돌리고 3단계로 돌아갑니다.

### 6. 종료 조건 판정

매 반복이 끝날 때마다 종료 조건을 판정합니다. 판정하지 않고 다음 반복으로 넘어가지 않습니다.

| 조건 | 값 | 조치 |
| --- | --- | --- |
| 성공 | `status` 가 `pass` 이고 `failed_required` 가 0 | 정상 종료 |
| 최대 반복 | 8회 | 중단하고 현재 상태를 보고 |
| 동일 실패 반복 | 같은 단계 id 가 3회 연속 실패 | 중단하고 접근 방식을 바꿔 보고 |
| 개선 없음 | 2라운드 연속으로 실패 수가 줄지 않음 | 중단 |
| 보안 민감 변경 | 해당 시 즉시 | 사람 검토로 에스컬레이션 |
| 예산 초과 | 시간·비용 한도 초과 | 중단 |

반복 상태는 `.harness/loop-state.json` 에서 확인할 수 있습니다. 값의 근거와 예외 처리는 [../../rules/loop-budget.rule.md](../../rules/loop-budget.rule.md) 를 따릅니다.

중단으로 끝났다면 실패를 숨기지 않고 남은 실패, 시도한 변경, 마지막 오류 메시지를 그대로 보고합니다. 이 보고는 Outer Loop의 입력이 되며 회고는 harness-retro 스킬이 담당합니다.

## 완료 조건

다음을 모두 충족해야 이 스킬의 실행이 끝난 것으로 봅니다.

- 실제로 실행한 명령어를 그대로 제시했습니다. 실행하지 않은 명령을 실행했다고 쓰지 않습니다.
- `.harness/verify.json` 의 최종 `status`, `failed_required`, 실패한 단계 id 목록을 근거로 제시했습니다.
- 각 반복에서 무엇을 하나 골라 무엇을 하나 바꿨는지 대응이 드러납니다.
- 종료가 성공인지 중단인지 명시했고, 중단이면 어떤 종료 조건에 걸렸는지 밝혔습니다.
- 검증 기준(테스트, 타입 설정, lint 규칙, 임계값)을 바꾸지 않았음을 확인했습니다. 불가피하게 바꿨다면 그 사실과 이유를 별도로 보고했습니다.

## 하지 않는 것

- 게이트를 통과하려고 테스트·타입 검사·lint 를 약화하지 않습니다. 테스트 삭제·`skip`·단언 완화, 타입 검사 우회 주석, lint 규칙 비활성화, 임계값 하향은 모두 금지입니다.
- Inner Loop 안에서 하네스를 바꾸지 않습니다. `harness/` 아래 규칙·스킬·스크립트·훅과 `harness.config`, `AGENTS.md`, `CLAUDE.md` 는 이 스킬에서 수정 대상이 아닙니다.
- 요청 범위 밖 변경을 섞지 않습니다. 실패와 무관한 리팩터링, 의존성 업그레이드, 포맷 일괄 변경을 같은 반복에 넣지 않습니다.
- 종료 조건 없이 반복하지 않습니다. 반복 횟수를 세지 않거나 같은 실패에 계속 같은 수정을 시도하지 않습니다.
- 결과를 추정으로 보고하지 않습니다. 로그를 읽지 않은 채 "통과했을 것"이라고 쓰지 않습니다.

## 관련 문서

- [../../references/inner-outer-loop.md](../../references/inner-outer-loop.md)
- [../../rules/evaluation-integrity.rule.md](../../rules/evaluation-integrity.rule.md)
- [../../rules/loop-budget.rule.md](../../rules/loop-budget.rule.md)
- [../../rules/harness-change-control.rule.md](../../rules/harness-change-control.rule.md)
