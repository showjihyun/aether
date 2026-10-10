# 관측 — span 과 속성, 그리고 KPI 집계

Run 하나가 남기는 span 과 그 속성을 한 곳에 모읍니다. 코드를 읽지 않고도 집계를 쓸 수 있어야 합니다. 정본은 `packages/runtime` 의 `ExecuteRunUseCase`(span 을 여는 곳)와 `ContextReport`(숫자의 출처, [../specs/0004-phase-3-context-compiler.md](../specs/0004-phase-3-context-compiler.md) 2.3, 2.7)입니다.

속성 값은 **전부 문자열**입니다(spec 0002 2.9). 숫자도 `"232"` 처럼 문자열로 올라가므로 집계에서 `tonumber` 가 필요합니다. 프롬프트·응답·청크·기억 **본문은 어떤 속성에도 없습니다**(spec 0004 D-11) — 숫자와 종류만 있습니다.

## 1. 무엇이 어느 span 에 붙는가

```
run
└─ task                (모델 호출마다 하나)
   ├─ model.complete   (재시도하면 같은 task 안에 여러 번 compile 이 일어납니다)
   └─ tool.run         (도구 호출마다 하나)
```

| span | 속성 | 언제 붙는가 |
| --- | --- | --- |
| `run` | `aether.run_id`, `aether.agent_version_id` | span 을 열 때 |
| `run` | `aether.run.status` = `succeeded`·`failed`·`cancelled`·`timed_out` | 종결이 확정된 뒤 span 이 닫히기 전. **Task Success 의 원천**입니다. `RunStatus` 의 값 그대로이며 새 이름은 없습니다 |
| `task` | `aether.run_id`, `aether.agent_version_id`, `aether.task_id` | span 을 열 때 |
| `model.complete` | `aether.run_id`, `aether.agent_version_id`, `aether.task_id`, `aether.model.id` | span 을 열 때 |
| `model.complete` | `context.tokens.<source>` — `<source>` 는 `system`·`conversation`·`knowledge`·`memory`·`tools` | `compile` 이 돌아온 직후. **그 조립에 실제로 있던 소스만**입니다 |
| `model.complete` | `context.tokens.total`, `context.budget` | 같은 때. 항상 있습니다 |
| `model.complete` | `context.dropped.<source>` | 예산 초과로 뺀 소스만. 값은 뺀 토큰 수입니다 |
| `model.complete` | `context.dropped.sources` — 뺀 소스 이름을 뺀 순서대로 `,` 로 이은 것 (예: `memory,knowledge`) | 무엇이든 뺐을 때만. 아무것도 빼지 않았으면 속성이 없습니다 |
| `tool.run` | `aether.run_id`, `aether.agent_version_id`, `aether.task_id`, `aether.tool.name` | span 을 열 때 |

읽을 때 두 가지를 기억합니다.

- **속성이 없는 것과 `"0"` 인 것은 다릅니다.** `context.tokens.knowledge` 가 없으면 그 조립에 Knowledge 소스가 없었다는 뜻이고, `"0"` 이면 있었고 비용이 0 이었다는 뜻입니다. 없는 소스에 `"0"` 을 채우지 않으므로, 집계에서 없는 키를 0 으로 취급하면 그것은 집계의 선택이지 데이터의 사실이 아닙니다.
- **`context.*` 는 Run 하나에 여러 벌입니다.** `model.complete` span 마다 한 벌이 붙고, 그 span 은 스텝마다 하나입니다. Run 단위 숫자가 필요하면 집계에서 합치십시오 — 어느 한 span 의 값이 Run 전체가 아닙니다. **모델 재시도는 span 을 더 만들지 않습니다** — 같은 `model.complete` 안에서 `compile` 이 다시 일어나 속성을 덮어쓰므로, 재시도한 호출의 속성은 **마지막 시도의 조립**입니다. 시도별 조립을 보려면 span 을 시도마다 열어야 하고, 그것은 이 단위가 하지 않았습니다.

## 2. 집계 예시 — 종결 상태별 Context 토큰

이 저장소에는 span 을 담는 표가 없습니다. 지금 있는 것은 collector 가 파일로 내보낸 OTLP JSON 한 줄 단위 파일뿐이므로(`smoke` 가 `infra/docker/out/otel-smoke/spans.jsonl` 에 남깁니다) 예시는 그 파일에 대한 `jq` 입니다. 장래에 span 저장소가 생기면 그때 같은 집계의 SQL 을 이 절에 더합니다.

질문: 종결 상태별로, 모델 호출 한 번이 평균 몇 토큰의 Context 를 썼는가. `run` span 에서 상태를, 같은 trace 의 `model.complete` span 들에서 토큰을 가져와 trace 로 묶습니다.

```jq
[ .[].resourceSpans[]?.scopeSpans[]?.spans[]?
  | { trace: .traceId, name: .name,
      a: ((.attributes // []) | map({(.key): .value.stringValue}) | add // {}) } ]
| group_by(.trace)
| map(select(any(.[]; .name == "run")))
| map({
    status: (map(select(.name == "run") | .a["aether.run.status"]) | first),
    model_calls: (map(select(.name == "model.complete")) | length),
    context_tokens: (map(select(.name == "model.complete")
                         | .a["context.tokens.total"] // "0" | tonumber) | add // 0)
  })
| group_by(.status)
| map({ calls: (map(.model_calls) | add), tok: (map(.context_tokens) | add) } as $s
      | { status: .[0].status,
          runs: length,
          model_calls: $s.calls,
          context_tokens: $s.tok,
          tokens_per_model_call:
            (if $s.calls > 0 then ($s.tok / $s.calls) else null end) })
```

`// "0"`·`// 0` 과 `if $s.calls > 0` 은 장식이 아닙니다. `model.complete` 가 없는 Run — 시작 전에 취소된 Run — 이 파일에 하나라도 있으면 그 보호가 없는 판은 **집계 전체가 죽습니다**(`null (null) and number (0) cannot be divided`). 그 Run 을 하나 섞어 실측으로 확인했습니다: 보호가 없으면 위 오류, 있으면 `tokens_per_model_call: null` 인 행 하나. **`null` 은 "모델을 부르지 않았다" 이고 0 이 아닙니다** — 1절의 "없는 것과 0 은 다르다" 가 집계에서도 같습니다.

`jq -s -f agg.jq infra/docker/out/otel-smoke/spans.jsonl` 로 돌립니다(`-s` — 파일 한 줄이 export 한 번이고 한 trace 의 span 이 여러 줄에 나뉘어 있습니다). 2026-10-10 에 `smoke` 직후의 파일(`smoke` 시나리오와 `bench` 의 Run 이 섞여 있습니다)로 돌린 출력입니다. 이 개발 환경에는 `jq` 실행 파일이 없어 PyPI 의 `jq`(jq 라이브러리 바인딩)로 같은 프로그램을 `slurp` 로 돌렸습니다.

```json
[
  {
    "status": "succeeded",
    "runs": 64,
    "model_calls": 65,
    "context_tokens": 1065,
    "tokens_per_model_call": 16.384615384615383
  }
]
```

모델이 도구를 한 번 부른 Run 은 `model.complete` 가 둘이라 `model_calls` 가 `runs` 보다 큽니다. 이 파일에는 `succeeded` 만 있으므로 실패·취소·시간 초과의 행은 이 출력에 나타나지 않습니다 — 그 상태의 Run 이 생기면 `group_by(.status)` 가 행을 더합니다.

## 3. 이 숫자를 단일 목표로 주지 않는다

`context.tokens.total` 이나 `tokens_per_model_call` 을 "줄여라" 같은 단일 목표로 두지 않습니다(spec 0004 2.7, intent 0004 Non-goals, EI-3 의 제품판). 토큰 수를 목표로 주면 조립이 소스를 덜 넣는 쪽 — Knowledge 청크를 덜 붙이고, 기억을 먼저 빼고, 오래된 대화를 자르는 쪽 — 으로 최적화되고, 그 결과는 모델이 근거를 잃어 답이 나빠지는 동안 지표만 좋아지는 것입니다. 이 숫자는 **무엇이 얼마나 들어갔고 무엇이 예산 때문에 빠졌는지**를 설명하는 계기이지, 낮출수록 좋은 값이 아닙니다. 비용을 줄이려면 같은 Task Success(`aether.run.status` 가 `succeeded` 인 비율) 아래에서 보고, 둘이 함께 움직이는지를 사람이 읽습니다. 토큰 수를 겨냥한 평가 task 를 더할지는 이번 Phase 에서 결정하지 않았습니다.
