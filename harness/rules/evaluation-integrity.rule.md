# 평가 무결성 규칙 (EI)

이 문서는 에이전트가 검증이나 평가를 통과시키기 위해 무언가를 바꾸려 할 때 읽습니다. 테스트·타입·lint 를 손대기 직전, 평가 가중치나 임계값을 조정하려 할 때, 그리고 지표는 좋아졌는데 실제 품질이 좋아졌다고 말하기 어려울 때 이 문서를 근거로 삼습니다. 에이전트는 사람이 의도한 목적이 아니라 주어진 평가 함수를 최적화하며, 이는 전형적인 Goodhart's Law 문제입니다. 지표가 목표가 되는 순간 그 지표는 더 이상 좋은 지표가 아닙니다.

## 규칙

| ID | 규칙 |
| --- | --- |
| **EI-1** | 평가를 통과하기 위해 테스트·타입·lint 를 약화하지 않습니다. 실패는 검증 장치가 아니라 대상 코드를 고쳐서 해소합니다. |
| **EI-2** | 평가 기준·가중치·임계값을 에이전트가 스스로 수정하지 않습니다. `HARNESS_EVAL_WEIGHTS`, `HARNESS_THRESHOLD`, `evaluation/rubric.md` 는 사람이 소유합니다. |
| **EI-3** | 커버리지 같은 단일 지표를 목표로 주지 않습니다. 하나의 숫자만 최적화 대상이 되면 그 숫자를 채우는 가장 값싼 경로가 선택됩니다. |
| **EI-4** | 평가는 계층별로 보고하고 총점만으로 판정하지 않습니다. `latest-eval.json` 의 `layers` 배열과 `largest_failure` 를 항상 함께 읽습니다. |
| **EI-5** | 가능한 계층은 deterministic 하게 만듭니다. 테스트가 통과했는지 같은 판정은 LLM 에게 묻지 않고 실행해서 확인합니다. |
| **EI-6** | lint rule 비활성화, 테스트 skip, assertion 제거는 평가 회피로 간주합니다. 근거와 만료 조건 없이는 허용하지 않습니다. |
| **EI-7** | 평가 결과를 보고할 때는 실제 실행한 명령어와 로그 경로를 함께 제시합니다. 실행하지 않은 계층은 통과가 아니라 미측정으로 표기합니다. |

### 평가 계층 (고정 6종)

layer 식별자는 `correctness`, `architecture`, `quality`, `behavior`, `performance`, `subjective` 여섯 개로 고정입니다. 각 계층의 측정 대상, deterministic 여부, 기본 가중치는 [../references/evaluation-layers.md](../references/evaluation-layers.md) 가 소유하므로 여기에 다시 적지 않습니다.

EI-5 는 `subjective` 를 제외한 다섯 계층을 LLM 판정으로 대체하지 말라는 뜻입니다. `subjective` 계층만 판단형 평가를 쓰며, 그 점수는 단독으로 gate 가 되지 못합니다.

## 판정 절차

평가 점수를 올리기 위한 변경을 제안할 때마다 다음 순서로 판정합니다.

1. **변경 대상 분류** — 변경이 (a) 대상 코드, (b) 검증 장치(테스트·lint 설정·타입 설정), (c) 평가 정의(가중치·임계값·rubric) 중 무엇에 닿는지 먼저 분류합니다.
2. **(c) 라면 중단 (EI-2)** — 평가 정의 변경은 에이전트가 하지 않습니다. 필요하다면 `improvement-log/` 에 candidate 로 남기고 사람에게 넘깁니다.
3. **(b) 라면 회피 판정 (EI-1, EI-6)** — 다음 중 하나에 해당하면 평가 회피로 간주하고 기본적으로 거부합니다.
   - lint rule 을 끄거나 파일·디렉터리를 검사 대상에서 제외
   - 테스트를 skip / xfail / only 로 비활성화하거나 삭제
   - assertion 을 제거하거나 실제 값과 무관하게 항상 참인 형태로 완화
   - 타입 검사 억제 주석 추가, strict 옵션 완화
   - 실패하는 step 을 `required: false` 로 변경
4. **예외 요건 (EI-6)** — 3 의 변경이 불가피하면 다음 네 가지를 모두 갖춘 경우에만 허용합니다. 하나라도 없으면 거부합니다.
   - 왜 대상 코드를 고칠 수 없는지에 대한 근거
   - 영향 범위를 최소로 좁힌 적용 범위
   - 만료 조건 또는 만료일
   - 소유자
5. **지표 형태 확인 (EI-3)** — 목표가 단일 숫자 하나로 표현되어 있지 않은지 확인합니다. 단일 지표라면 계층별 목표로 분해합니다.
6. **계층별 판정 (EI-4)** — `.harness/latest-eval.json` 의 `layers` 를 계층별로 읽고, `score` 가 `threshold` 를 넘더라도 `required` 계층이 실패했으면 통과로 보지 않습니다. `largest_failure` 를 다음 라운드의 작업 대상으로 삼습니다.
7. **증거 첨부 (EI-7)** — 실행한 명령어와 `.harness/logs/` 아래 로그 경로를 결과에 함께 남깁니다.

이 절차의 3~4 단계는 [../hooks/guard-evaluation-tampering.sh](../hooks/guard-evaluation-tampering.sh) 가 기계적으로 한 번 더 확인합니다. 훅이 차단한 변경을 우회하기 위해 훅 자체를 수정하는 것도 EI-2 위반입니다. 훅이 보호하는 언어별 파일 목록(lint·타입·테스트 러너·아키텍처 규칙 설정)은 `language/<언어>/lang.sh` 가 소유하며, 그 목록에서 패턴을 지워 차단을 피하는 것 역시 같은 위반입니다.

## 위반 예시와 교정

### 예시 1 — Coverage > 90% 를 무의미한 테스트로 채우기

에이전트에게 `Test Coverage > 90%` 라는 목표를 주었습니다. 에이전트는 훌륭한 테스트를 작성할 수도 있지만, 실제로는 의미 없는 테스트 수백 개를 추가해 커버리지 숫자만 올렸습니다. 추가된 테스트는 함수를 호출하기만 하고 결과를 검증하지 않습니다.

- 위반: EI-3 위반입니다. 단일 지표를 목표로 준 결과, 그 지표를 가장 값싸게 채우는 경로가 선택되었습니다. 커버리지는 실행된 줄의 비율일 뿐 정확성의 대리 지표가 아닙니다. Goodhart's Law 의 교과서적 사례입니다.
- 교정: 목표를 계층별로 분해합니다. `correctness` 계층은 커버리지 비율이 아니라 대표 시나리오와 회귀 케이스의 통과 여부로 평가하고, 커버리지는 판정 기준이 아니라 참고 지표로만 보고합니다. assertion 없는 테스트는 EI-6 의 assertion 제거와 같은 성질이므로 리뷰에서 거부합니다.

```text
위반: correctness 목표 = "coverage >= 90"
교정: correctness 목표 = "representative tasks 전부 통과 + 회귀 케이스 통과"
      coverage 는 layers[].notes 에 참고값으로만 기록
```

### 예시 2 — Lint Errors = 0 을 rule 비활성화로 달성하기

`Lint Errors = 0` 이라는 목표를 주었습니다. 가장 쉬운 해결책은 해당 lint rule 을 꺼버리는 것이고, 에이전트는 설정 파일에서 문제가 되는 rule 을 `off` 로 바꿔 목표를 달성했습니다.

- 위반: EI-1 과 EI-6 위반입니다. 평가 함수는 만족되었지만 의도한 품질은 전혀 개선되지 않았습니다. 이 역시 Goodhart's Law 문제입니다.
- 교정: 대상 코드를 고쳐 경고를 해소합니다. 정말 규칙 자체가 이 저장소에 맞지 않는다면 그것은 평가 정의 변경이므로 EI-2 에 따라 사람에게 넘깁니다. 한시적으로 억제해야 한다면 EI-6 의 네 가지 요건을 모두 채운 뒤, 범위를 좁혀 적용합니다.

```text
거부: lint 설정에서 rule 을 전역 off 로 변경
허용 조건: 근거 + 최소 범위 + 만료 조건 + 소유자 4개가 모두 기록된 경우에 한함
기록 위치: improvement-log/ 의 candidate 및 억제 지점 주석
```

### 예시 3 — 총점만 보고 통과 판정

`.harness/latest-eval.json` 의 `score` 가 `threshold` 를 넘었다는 이유로 작업을 완료로 보고했습니다. 실제로는 `correctness` 계층이 실패했고 다른 계층 점수가 높아 총점이 가려졌습니다.

- 위반: EI-4 와 EI-7 위반입니다. 가중 평균은 실패한 계층을 감출 수 있습니다.
- 교정: `layers` 를 계층별로 보고하고, 필수 계층이 실패하면 총점과 무관하게 실패로 판정합니다. `largest_failure` 를 다음 라운드의 작업 대상으로 명시합니다.

## 관련 문서

- [../hooks/guard-evaluation-tampering.sh](../hooks/guard-evaluation-tampering.sh) — 평가 회피 변경을 기계적으로 차단하는 훅
- [../references/evaluation-layers.md](../references/evaluation-layers.md) — 6개 평가 계층의 정의와 구성 방법
- [../evaluation/rubric.md](../evaluation/rubric.md) — 계층별 가중치와 임계값 정본
- [loop-budget.rule.md](loop-budget.rule.md) — 반복 중 평가 공략이 시작될 때의 중단 조건
- [untrusted-experience.rule.md](untrusted-experience.rule.md) — 평가 완화 요구가 외부 입력에서 들어온 경우의 처리
