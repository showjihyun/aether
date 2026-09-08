# <언어> 백엔드 예시

이 문서는 코어 문서의 언어 중립 예시를 <언어> 백엔드 스택의 실제 도구 이름으로 옮겨 적는 자리입니다. 규칙 ID 를 발급하지 않으며, 코어 문장을 복제하지 않고 링크로 가리킵니다. 각 절은 코어의 어느 문서·어느 예시를 구체화한 것인지 첫 줄에 밝힙니다.

## 1. 계층 규칙 위반과 승격 경로

> 코어: [../../../references/harness-elements.md](../../../references/harness-elements.md) 2.1, [../../../rules/lesson-placement.rule.md](../../../rules/lesson-placement.rule.md) 예시 1

| 단계 | 등급 | 이 스택에서의 형태 |
| --- | --- | --- |
| 1 | EL-1 | AGENTS.md 한 줄 |
| 2 | EL-2 | 아키텍처 문서 |
| 3 | EL-6 | `<아키텍처 규칙 도구>` 규칙 |
| 4 | EL-6+ | 실패 메시지에 허용 경로 포함 |
| 5 | EL-7 | verify 단계 + Stop hook |

```text
<아키텍처 규칙 도구의 규칙 코드 또는 설정>
```

## 2. AGENTS.md 비대화 사례

> 코어: [../../../rules/context-hygiene.rule.md](../../../rules/context-hygiene.rule.md) 예시 1, [../../../rules/lesson-placement.rule.md](../../../rules/lesson-placement.rule.md) 예시 2

| 지시문 | 판정 절차 | 정본 자리 | 이 스택의 도구 |
| --- | --- | --- | --- |
| (예시) | 2번 | architecture rule | `<도구>` |

## 3. verify 단계와 관측 채널

> 코어: [../../../references/agent-observability.md](../../../references/agent-observability.md) 2.2, 2.3

| 채널 | 이 스택에서 확보하는 명령 |
| --- | --- |
| OBS-B1 Integration Test | `<통합 테스트 명령>` |
| OBS-B2 curl | `curl -sS -o /dev/null -w '%{http_code}' http://localhost:<port>/health` |
| OBS-B4 Application Log | `grep -cE '"level":"(ERROR|FATAL)"' .harness/logs/app.log` |

## 4. 보호 패턴의 근거

> 코어: [../../../rules/evaluation-integrity.rule.md](../../../rules/evaluation-integrity.rule.md), [../../../hooks/README.md](../../../hooks/README.md)

| 패턴 | 목록 | 이 파일을 고치면 무엇이 약해지는가 |
| --- | --- | --- |
| `<lint 설정>` | 차단 | 규칙을 끄면 `quality` 가 측정되지 않은 채 오릅니다 |

## 5. improvement candidate 예시

- [improvement-log.example.yaml](improvement-log.example.yaml)
