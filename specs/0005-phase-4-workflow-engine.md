# Spec 0005 — Phase 4: Workflow Engine

| 키 | 값 |
| --- | --- |
| 번호 | 0005 |
| 작성일 | 2026-10-12 |
| 선행 intent | [../intents/0005-phase-4-workflow-engine.md](../intents/0005-phase-4-workflow-engine.md) (승인됨 2026-10-12) |
| 상태 | 승인됨 |
| 승인 | showjihyun, 2026-10-12 |
| 대상 단위 | [../intents/mvp-backlog.md](../intents/mvp-backlog.md) 의 P4-1 ~ P4-5 |
| 후속 plan | (승인 뒤 `plans/0005-phase-4-workflow-engine.md`) |

이 문서는 intent 0005 의 열린 질문 8건을 결정(D-1 ~ D-16)으로 고정하고, 다섯 단위의 완료 판정을 **검증 가능한 명제**(R-1 ~ R-15)로 옮깁니다. 단위의 범위는 backlog 가 소유합니다.

여덟 질문의 답은 2026-10-12 에 사람이 정했고, **무엇과 무엇 사이에서 골랐는지**는 PR #143 의 결정 기록 코멘트가 소유합니다. 이 문서는 고른 결과만 적습니다.

Phase 1~3 의 결정(spec 0002 D-1 ~ D-19 · 개정 1~10, spec 0003 D-1 ~ D-16 · 개정 1~5, spec 0004 D-1 ~ D-14 · 개정 1~9)은 그대로 유효합니다. 이 spec 이 그중 무엇을 개정하면 해당 항목에 `[실질] 개정` 을 명시합니다 — **이번에는 없습니다.** Phase 4 는 기존 계약을 바꾸지 않고 옆에 새 것을 세웁니다. 그것이 D-1 의 이유이기도 합니다.

## 1. 요구사항

| # | 요구사항 | 근거 | 어떻게 판정하는가 |
| --- | --- | --- | --- |
| R-1 | 잘못된 그래프는 **저장 시점에** 거부되고 사유가 돌아옵니다 | Outcome 2 (P4-1) | `api-unit`: START 가 0개·2개, END 도달 불가, 고아 노드, 간선이 없는 노드 id 를 가리키는 경우 각각 거부되고 사유가 구별됨. `api-integration`: `POST` 가 4xx |
| R-2 | **Workflow Version 은 불변**입니다. 정의를 바꾸면 새 Version 이 되고 실행 중인 Run 의 정의는 바뀌지 않습니다 | Constraint (P4-1) | `api-integration`: Version 1 로 Run 을 시작한 뒤 `PUT` 으로 Version 2 를 만들고, 그 Run 의 조회가 여전히 Version 1 을 가리킴. Version 1 의 노드·간선이 바이트 단위로 같음 |
| R-3 | **상한 없는 LOOP 는 정의할 수 없습니다** | Constraint (P4-1) | `api-unit`: `max_iterations` 가 없거나 0 이하인 LOOP 노드가 검증에서 거부됨 |
| R-4 | `START → AGENT → CONDITION → HUMAN → AGENT → END` 가 worker 에서 끝까지 실행됩니다 | Phase 완료 판정 (P4-2, P4-4) | `api-integration`: 승인 대기에서 멈추고, 승인 API 호출 뒤 재개되어 END 도달. 노드 실행 기록이 순서대로 남음 |
| R-5 | CONDITION 의 **분기 양쪽이 각각 타집니다** | Outcome 3 (P4-2) | `api-integration`: 같은 Workflow 를 두 입력으로 돌려 서로 다른 경로를 타고, 지난 노드 목록이 다름 |
| R-6 | 프로세스를 재시작해도 **중단된 지점부터** 이어 실행됩니다 | Outcome 4 (P4-2) | `api-integration`: 노드 하나를 마친 뒤 worker 를 죽이고 다시 띄워 END 까지 감. 마친 노드가 두 번 실행되지 않음(실행 기록 1건) |
| R-7 | 대기 중인 Workflow Run 은 **worker 슬롯을 점유하지 않습니다** | D-4 (P4-2) | `api-integration`: 승인 대기 Workflow Run 을 worker 동시성 한도만큼 만든 뒤, 평범한 Agent Run 하나가 정상 처리됨. 대기 중인 Workflow Run 의 lease 가 비어 있음 |
| R-8 | 재개는 **멱등**입니다 | D-4 (P4-2) | `api-unit`: 같은 깨우는 신호를 두 번 넣어도 노드가 한 번만 전진. `api-integration`: 승인 API 를 두 번 불러도 노드 실행 기록이 1건 |
| R-9 | PARALLEL 이 합류하고, **분기 하나의 실패가 합류에서 관측**됩니다 | Outcome 5 (P4-3) | `api-unit`: 두 분기가 모두 실행되고 합류 뒤 다음 노드가 한 번 실행됨. 한 분기를 실패시키면 합류 결과에 그 실패가 담기고 Workflow Run 이 `failed` |
| R-10 | LOOP 가 상한을 넘기면 `failed` 가 되고 사유가 남습니다 | Outcome 5 (P4-3) | `api-unit`: 상한 n 인 루프가 n+1 회에 `failed` 가 되고 사유가 상한 초과로 구별됨 |
| R-11 | WAIT 는 **주입된 시계**로 결정적으로 테스트됩니다 | Outcome 5 (P4-3) | `api-unit`: 실제 시간을 쓰지 않고 시계를 앞으로 돌려 대기가 끝남. 테스트 소요가 대기 시간과 무관 |
| R-12 | **승인 전 재개는 거부**되고, 승인 기록이 조회됩니다 | Outcome 6 (P4-4) | `api-integration`: 승인 없이 재개 요청 → 4xx. 승인 뒤 재개 성공. `approved_by`·`approved_at`·대상 노드 실행이 조회에 나옴. 대기가 아닌 노드 실행을 지목한 승인은 거부됨 |
| R-13 | **"도구 대기" 와 "사람 대기" 가 상태만으로 구별**됩니다 | Outcome 9, D-2 (P4-4) | `api-integration`: 자식 Run 대기 중인 Workflow Run 의 상태가 `waiting_run`, 승인 대기 중인 것이 `waiting_approval`. Agent Run 의 `waiting` 값은 바뀌지 않음(회귀) |
| R-14 | LLM·MCP·TOOL 노드가 각자의 통로를 지납니다 | Outcome 7 (P4-5) | `api-arch`: `aether_workflow` 가 `httpx`·벤더 SDK·MCP 클라이언트 라이브러리를 import 하지 않음(AR-5·AR-6·AR-9). `api-integration`: 세 노드가 각각 한 번씩 들어간 Workflow 가 END 도달하고 도구 호출이 감사에 남음 |
| R-15 | **`runtime → workflow` 역참조가 금지되고 그 금지가 발화합니다** | Outcome 8, D-10 | `api-arch` + `tests/arch` 에 `aether_runtime/_bad.py`(`import aether_workflow`) 주입 케이스 1건이 **실패**함 |

위 전부가 **네트워크 없이** 통과합니다(fake 모델). 새 HTTP 경로는 전부 인증 뒤에 있고 인증 없는 요청은 401 입니다 — `apps/api/tests/test_routes_require_auth.py` 가 경로를 열거하지 않고 라우터에서 수집하므로 새 경로가 자동으로 그 판정에 들어옵니다.

## 2. 설계

### 2.1 배치와 호출 방향 (D-1, D-10)

```
apps/worker ──┬─> aether_workflow (그래프·실행·노드)
              │        └─> (포트) Agent Run 생성·관찰, 모델 호출, 도구 호출
              └─> aether_runtime (Agent Run 실행)

aether_workflow ──> aether_runtime        (허용)
aether_runtime  ──> aether_workflow       (금지, AR-13)
```

`aether_workflow` 는 자기 outbound 포트로 "Agent Run 을 만들고 그 결과를 받는다" 를 선언하고, **조립은 `apps/worker` 의 `main` 이 합니다**(AR-10). Phase 3 에서 `ModelGatewayEmbedder`·`MemoryWriter` 를 꽂은 자리와 같습니다 — 그래서 `aether_workflow` 는 `aether_runtime` 의 타입을 import 하지 않아도 됩니다.

반대 방향은 **AR-13 으로 막습니다**(2.13).

### 2.2 Workflow 모델과 검증 (P4-1, D-11, D-12, D-14)

`Workflow` 는 이름과 Version 목록을 가집니다. `Workflow Version` 은 **노드와 간선의 집합**이고 불변입니다.

노드 종류는 **열**입니다 — `START`, `END`, `AGENT`, `CONDITION`, `PARALLEL`, `JOIN`, `LOOP`, `WAIT`, `LLM`, `MCP`, `TOOL`. `WEBHOOK`·`SCHEDULE` 은 이번 범위 밖입니다(D-14).

검증은 저장 시점에 하고 다음을 **각각 다른 사유로** 거부합니다(R-1).

| 거부 | 왜 |
| --- | --- |
| START 가 0개 | 시작점이 없는 그래프는 실행 순서가 정의되지 않습니다. **사유를 2개 이상과 나눕니다**(개정 1 — R-1 이 "0개·2개 각각" 을 요구합니다) |
| START 가 2개 이상 | 같은 이유. 사유 값이 다릅니다 |
| END 에 도달할 수 없는 노드가 있음 | 도달 못 하는 노드는 죽은 정의입니다 |
| 고아 노드(들어오는 간선도 나가는 간선도 없음) | 같은 이유 |
| 간선이 없는 노드 id 를 가리킴 | 실행 중에 터지는 것을 저장 때 잡습니다 |
| `LOOP` 에 `max_iterations` 가 없거나 0 이하 | D-11 |
| `PARALLEL` 에 대응하는 `JOIN` 이 없음 | 합류 없는 분기는 끝을 정의하지 않습니다. **"대응" 의 v1 정의**(개정 1): `PARALLEL` 의 하류에 `JOIN` 이 하나라도 있으면 통과합니다. 중첩 `PARALLEL` 의 짝 맞추기와 `JOIN` 이 모든 분기를 받는지는 **검사하지 않습니다** — P4-3 이 합류를 실제로 구현할 때 실측으로 좁힙니다 |
| `CONDITION` 에 판정식이 없음 | **개정 4 에서 더했습니다.** `CONDITION` 의 종류별 설정은 `condition_path`·`condition_operator`(·`condition_value`)입니다. 없으면 실행 시점에 터지므로 저장 때 잡습니다 |
| `CONDITION` 의 분기가 둘 다 있지 않음 | **개정 4.** 나가는 간선의 `label` 이 `true`·`false` **둘 다** 있어야 합니다. 한쪽만 있으면 그 방향으로 갈라진 실행이 갈 곳이 없고, 그것을 실행 중에 발견하면 이미 자식 Run 을 띄운 뒤입니다 |
| `AGENT` 에 Agent 참조가 없음 | **개정 3 에서 더했습니다.** 노드는 종류별 설정을 가집니다 — `LOOP` 의 `max_iterations` 와 같은 자리에 `AGENT` 의 `agent_id`(선택 `agent_version`)가 있습니다. 초안의 노드 모델에는 그 자리가 없어서 `AGENT` 노드가 **무엇을 실행할지 말할 수 없었습니다**. 참조가 없으면 실행 시점에 터지므로 저장 때 잡습니다(`dangling_edge` 와 같은 근거). `agent_version` 을 주지 않으면 실행 시점의 최신 Version 입니다 |
| 같은 id 를 가진 노드가 둘 이상 | **개정 1 에서 더했습니다.** 2026-10-13 구현에서 발견한 구멍입니다 — 중복 id 는 검증을 통과하고 저장에서 PK 충돌로 터집니다. "실행 중에 터지는 것을 저장 때 잡습니다"(간선 거부와 같은 근거)이고, 4xx 로 사유를 주는 쪽이 500 보다 낫습니다 |

거부 사유는 위 표 때문에 **값 열한 개**입니다(개정 1·3·4). 한 정의가 여러 규칙을 어기면 위반을 전부 돌려주고, 파생 증상이 중복 보고되지 않게 고아 노드는 "END 도달 불가" 에서 제외합니다.

검증은 **순수 함수**입니다 — `aether_workflow.domain` 안에 있고 I/O 를 하지 않습니다(AR-9).

### 2.3 Workflow Run 의 상태와 전이 (D-1, D-2)

Agent Run 과 **별도 enum** 입니다. `data.run_execution_status`(마이그레이션 0001)는 건드리지 않습니다.

| 값 | 뜻 |
| --- | --- |
| `queued` | 요청됨, 아직 집히지 않음 |
| `running` | 노드를 실행하는 중 |
| `waiting_run` | **자식 Agent Run** 의 종결을 기다림 |
| `waiting_approval` | **사람의 승인**을 기다림 |
| `succeeded` / `failed` / `cancelled` | 종결 |

대기를 **두 값으로 나눈 것**이 이 절의 핵심입니다. 사유 컬럼 하나로 두면 "멈춘 이유" 를 보려고 모든 조회가 두 칼럼을 봐야 하고, Phase 5 의 "내 승인 대기" 필터가 상태로 표현되지 않습니다.

`timed_out` 은 두지 않습니다 — Phase 4 는 Workflow 전체 타임아웃을 만들지 않습니다. 자식 Agent Run 의 타임아웃은 그 Run 의 것이고, Workflow 는 그것을 `failed` 로 받습니다. 없는 상태를 미리 적지 않습니다.

전이표는 Agent Run 과 같은 모양으로 코드에 두고 종결 상태에서 나가는 전이를 금지합니다. `cancelled` 는 대기 중에도 가능합니다 — 승인을 기다리는 Workflow 를 취소할 수 없으면 영원히 남습니다.

### 2.4 노드 실행과 출력 (D-8, D-9)

노드 실행 하나는 `node_executions` 에 한 행이고, **출력은 구조화된 작은 값**입니다.

- 출력은 JSON 객체이고 **8 KiB 상한**입니다. 상한을 넘기면 자르고 **잘렸다는 사실을 함께 기록**합니다(조용히 자르지 않습니다).
- `AGENT` 노드의 출력은 자식 Run 의 **마지막 assistant 본문을 상한까지 자른 것**과 그 Run 의 종결 상태입니다.
- 출력은 `data` 의 노드 실행 기록에만 둡니다. **span·감사·보고에는 넣지 않습니다**(spec 0004 D-11 과 같은 선).

**이 결정이 새 제품 표면을 만든다는 사실을 적어 둡니다.** 지금까지 제품은 모델의 응답 본문을 어느 API 로도 내지 않았습니다 — `model.completed` 는 `finish_reason`·`usage` 만, `model.delta` 는 Phase 1 미발생, trace 는 본문 없음. 2026-10-12 의 수동 확인은 `memory_enabled` 를 켜고 `data.agent_memory` 를 읽어서 겨우 봤습니다([../docs/step_results/phase-3.md](../docs/step_results/phase-3.md)).

그 표면을 만드는 이유는 하나입니다 — 만들지 않으면 **CONDITION 이 내용으로 분기할 수 없고**, 그러면 "모델 답변에 따라 갈라지는 Workflow" 라는 대부분의 실제 용도가 성립하지 않습니다.

경계를 넘지 않는 근거: Phase 3 이 이미 `memory_enabled` 일 때 그 본문 **전체**를 `data.agent_memory` 에 영속시킵니다. `data` 안의 상한 있는 복사본은 **새 프라이버시 경계가 아닙니다.** D-11 이 막는 것은 span·보고이고 그것은 그대로 지킵니다.

**개정 4 (2026-10-15, P4-2b 착수 전).** 넷을 고정합니다.

1. **판정 대상은 선언된 맥락 하나**입니다 — `{"input": <Workflow Run 의 입력>, "nodes": {"<노드 id>": <그 노드의 출력>}}`. 경로는 점 표기(`nodes.ask.answer`·`input.q`)입니다. "직전 노드의 출력" 같은 암묵 규칙을 두지 않습니다 — 그 규칙은 그래프를 고칠 때 조용히 뜻이 바뀝니다.
2. **없는 경로는 조용한 거짓이 아닙니다.** `exists` 만 거짓이고 나머지 연산자는 **실행 실패**(`condition_path_missing`)입니다. 비교할 수 없는 타입(`gt`·`lt` 에 문자열 등)도 실패(`condition_type_mismatch`)입니다. 조용히 한쪽으로 가는 Workflow 는 디버깅할 수 없습니다.
3. **노드 실행 조회 API 를 만들지 않습니다.** 출력은 `data` 에 있고 api 역할(`aether_control`)은 `data` 에 **아무 권한이 없습니다**(0001 R-7). 조회를 만들려면 노드 실행을 `control` 로 투영해야 하고 그것은 화면이 필요해지는 Phase 5 의 일입니다. 그래서 2.4 가 적은 "출력의 소비자 둘" 은 **지금 하나**입니다 — `CONDITION` 뿐입니다. C-3 의 되돌리기가 그만큼 싸집니다.
4. **상한은 직렬화된 바이트 기준**이고, 자르면 `data.workflow_node_executions.output_truncated` 를 함께 참으로 적습니다. `AGENT` 노드의 출력은 `{"text": <마지막 assistant 본문, 상한까지>, "status": <자식 Run 의 종결 상태>}` 이고 본문은 `data.run_states` 에서 읽습니다(worker 가 소유하는 평면 — 새 권한이 필요하지 않습니다).

**CONDITION 의 판정**(D-9)은 **선언된 필드 경로 + 선언된 연산자**입니다. 임의 표현식을 평가하지 않고, 모델에게 묻지 않습니다. 연산자는 v1 에서 `equals`·`not_equals`·`contains`·`gt`·`lt`·`exists` 로 닫고, 그보다 복잡한 판정이 필요하면 그것은 노드(코드)의 일입니다.

### 2.5 파킹과 재개 (D-4)

대기는 **파킹**입니다. Workflow Run 은 상태와 "무엇을 기다리는가" 만 남기고 메모리에서 내려가며, worker 슬롯과 lease 를 **놓습니다**(R-7).

깨우는 신호는 둘이고 **같은 경로**로 들어옵니다.

| 기다리는 것 | 깨우는 신호 | 경로 |
| --- | --- | --- |
| 자식 Agent Run | 이미 있는 `run.finished` 이벤트(spec 0002 2.7 — "항상 스트림의 마지막") | 이벤트 소비 → 재큐 |
| 사람의 승인 | 승인 API 호출 | api → 재큐 |

**개정 3 (2026-10-14, P4-2a B 착수 전).** 자식 Agent Run 의 깨우는 신호는 그 Run 의 **종결 상태 통지**(`aether:runs:status`, Workflow 전용 consumer group `aether-workflow`)입니다 — 위 표가 적은 `run.finished` **이벤트**가 아닙니다. `run.finished` 는 `aether:runs:{run_id}:events` 에 있고 그 스트림은 **group 으로 받을 수 없습니다**(run 마다 키가 다릅니다). 거기서 읽으려면 "지금 파킹된 Run 목록" 을 먼저 DB 에서 구해야 하는데, 그러면 빠른 경로가 스위퍼와 **같은 장치**가 되어 이 절이 요구한 "경로 둘" 이 하나로 붕괴합니다. 상태 통지는 같은 사실(종결)을 group 으로 받을 수 있는 모양으로 싣고 있고, `seq` 로 멱등이며, 이미 Phase 1 의 계약입니다(2.18). **두 경로는 그대로 둘**입니다 — 통지 소비(빠름)와 스위퍼(안전망).

**같은 개정에서 함께 정한 것 둘.** 자식 Run 의 입력은 **Workflow Run 의 `input` 을 직렬화한 것**입니다(노드 출력을 다음 노드의 입력으로 잇는 것은 D-8·P4-2b 의 일입니다). 자식 Run 의 `requested_by` 는 **비웁니다** — 사람이 아니라 Workflow 가 요청했고, `control.workflow_runs` 에는 요청자 열이 없습니다(P4-1 실측).

**이벤트만 믿지 않습니다.** 이벤트 하나가 유실되면 Workflow 가 영원히 파킹됩니다. 낮은 빈도의 **스위퍼**를 안전망으로 둡니다 — `waiting_run` 인데 자식 Run 이 이미 터미널인 건을 주워 재큐합니다.

이 안전망의 근거는 하네스에 있습니다. improvement-log `2026-10-11-001` 이 같은 교훈을 적었습니다 — **대기 장치의 침묵은 "변화 없음" 의 증거가 아닙니다.** 그 실패를 폴링 루프 만료 2회와 낡은 초록 1회로 겪었고, 같은 모양을 제품에 넣지 않습니다.

재개는 **멱등**입니다(R-8). 같은 신호가 두 번 와도 노드가 두 번 전진하지 않습니다 — Phase 1 의 lease + 전이 검사를 그대로 씁니다. 전진은 "현재 노드가 이 노드이고 상태가 이 대기값일 때만" 일어납니다.

### 2.6 승인 (P4-4, D-5, D-6, DP-6)

`HUMAN` / `APPROVAL` 노드에 닿으면 Workflow Run 이 `waiting_approval` 로 파킹되고, 승인 대기 사실이 조회됩니다. **알림은 보내지 않습니다**(Non-goal).

승인 API 는 **특정 노드 실행을 지목**해야 하고, 그 실행이 실제로 `waiting_approval` 이 아니면 거부합니다(R-12). 선승인과 재전송을 막는 **정확성** 가드이고 권한 판정이 아닙니다.

기록은 `control` 에 append-only 로 남깁니다 — `approved_by`(주체 id), `approved_at`, 대상 노드 실행, 그리고 선택적 메모. `data.tool_call_audit`(Phase 2)과 **다른 평면**인 이유는 그것이 worker 가 쓰는 실행 부산물이고 승인은 **사람의 결정**이기 때문입니다.

**이 spec 이 만들지 않는 것을 이름 붙여 적습니다 — 승인자 권한 모델.** v1 은 **인증된 주체 누구나** 승인할 수 있습니다. 누가 승인했는지는 남기고 **누가 승인할 수 있는지는 묻지 않습니다.** 그 판정은 Trust Layer(Phase 8)의 것입니다.

승인자 목록을 Workflow 정의에 넣지 않은 이유: Version 이 불변이므로 **승인자를 바꾸려면 새 Version** 이 되고, 그것은 운영에서 쓸 수 없습니다.

"요청자는 자기 것을 승인할 수 없다" 도 **넣지 않습니다.** 그럴듯하지만 그것이 바로 권한 모델이고, 반쪽짜리 권한 모델은 Phase 8 에서 이전 비용만 만듭니다. 이 공백은 Phase 8 이 메울 자리로 남겨 둡니다.

승인 경로의 코드·마이그레이션·API 는 **사람 검토로 에스컬레이션합니다**(DP-6).

### 2.7 PARALLEL / JOIN / LOOP / WAIT (P4-3, D-15)

- **PARALLEL·JOIN**: 분기를 모두 실행하고 `JOIN` 에서 합칩니다. 합류 결과에는 각 분기의 결과가 담기고, **분기 하나라도 실패하면 Workflow Run 이 `failed`** 입니다(R-9). 병렬은 **한 worker 안의 병렬**입니다 — 분산 실행은 범위 밖입니다(D-15).
- **LOOP**: `max_iterations` 가 필수이고(D-11), 넘기면 `failed` 에 상한 초과 사유가 남습니다(R-10).
- **WAIT**: 주입된 시계를 씁니다(R-11). 실제 시간을 기다리는 테스트를 만들지 않습니다 — Phase 1 의 타임아웃 테스트와 같은 방식입니다.

### 2.8 LLM / MCP / TOOL 노드 (P4-5)

Agent 를 거치지 않고 한 번만 부르는 노드입니다. 통로는 바뀌지 않습니다 — 모델은 `ModelGateway`(AR-5), 도구는 MCP Gateway(AR-6)를 지나고 감사도 그대로 남습니다. `aether_workflow` 는 그 라이브러리를 직접 import 하지 않고 포트로만 선언합니다(R-14).

### 2.9 데이터 모델 (마이그레이션 0005, D-5)

| 표 | 평면 | 누가 쓰는가 |
| --- | --- | --- |
| `control.workflows` | `control` | api — 이름과 현재 Version |
| `control.workflow_versions` | `control` | api — 노드·간선. **불변** |
| `control.workflow_runs` | `control` | api — Run 투영(상태·현재 노드·기다리는 대상) |
| `control.workflow_approvals` | `control` | api — **승인 기록, append-only** |
| `data.workflow_node_executions` | `data` | worker — 노드 실행 기록과 출력(8 KiB 상한) |

**개정 2 (2026-10-14, P4-2a 착수 전 실측).** 실행 상태와 lease 는 `control.workflow_runs` 가 아니라 **`data.workflow_run_executions`**(마이그레이션 0006)에 둡니다. 위 표의 "누가 쓰는가" 가 `control.workflow_runs` 를 api 로 적어 둔 것은 맞지만, **실행기는 worker** 이고 worker 의 역할(`aether_data`)은 `control` 에 **SELECT 뿐**입니다 — 마이그레이션 0001(`GRANT SELECT ON control.runs`·`control.agent_versions`)과 0005(`GRANT SELECT ON control.workflow_versions`·`control.workflow_runs`) 실측. 그래서 worker 는 상태·lease·현재 노드를 `control` 에 쓸 수 없습니다. **GRANT 를 넓히지 않습니다** — D-5 의 평면 규칙을 거스르고 권한 변경은 사람 검토 대상입니다([../AGENTS.md](../AGENTS.md) Loop). 대신 Phase 1·3 이 이미 쓰는 모양을 그대로 씁니다: 실행 상태는 `data`, `control` 쪽은 **투영**이고 `aether:workflow_runs:status` 스트림으로 **api 가** 갱신합니다(`data.run_executions` → `aether:runs:status` → `control.runs` 와 같은 선, `control.knowledge_ingestions` 도 같습니다). `control.workflow_runs` 의 열(`status`·`status_seq`·`current_node_id`·`waiting_run_id`)은 그대로 쓰이고 뜻만 "투영" 으로 고정됩니다.

**자식 Agent Run 의 선언도 같은 이유로 api 가 만듭니다**(2.5). worker 는 `control.runs` 에 INSERT 할 수 없습니다. 실행기가 자식 Run 의 id 를 **정해서** `aether:workflow:agent_runs:requested` 에 싣고, api 가 그 id 로 선언 행을 만들어 `aether:runs:requested` 에 통지합니다 — id 를 실행기가 정하므로 같은 요청이 두 번 가도 선언은 한 행이고(R-8), 파킹은 처음부터 기다릴 대상을 압니다. 스위퍼는 `data.run_executions`(worker 가 소유하는 평면)의 상태를 봅니다 — `control.runs` 의 투영을 기다리지 않습니다.

평면을 가른 규칙은 **쓰는 주체**입니다 — 마이그레이션 0001 의 역할·GRANT 가 이미 그렇게 정해 두었고 Phase 3 이 같은 규칙을 따랐습니다(`control.knowledge_ingestions` / `data.knowledge_chunks`).

자식 Agent Run 과의 연결은 `data.workflow_node_executions.agent_run_id` 입니다 — **workflow 쪽에** 둡니다. Run 쪽에 "이 Run 은 어느 Workflow 노드의 것" 을 두면 `aether_runtime` 이 workflow 를 알아야 하고, 그것이 AR-13 위반입니다(D-1).

### 2.10 이벤트 (D-13)

Workflow 는 **자기 어휘**를 가집니다 — `workflow.status`, `node.started`, `node.finished`, `approval.requested`, `approval.granted`, `workflow.finished`. Agent Run 의 이벤트 계약(`task.started`·`tool.called`·`model.completed` …)에 섞지 않습니다. 이벤트 스키마는 계약이고(DP-1) 어휘가 다른 것을 한 계약에 넣으면 둘 다 바꾸기 어려워집니다.

스트림과 SSE 경로는 Agent Run 의 **모양을 그대로 베끼되** 다른 이름입니다. 표가 아니라 패턴을 재사용하는 것이 D-1 의 뜻입니다.

### 2.11 설정 (추가되는 환경변수)

| 변수 | 기본 | 뜻 |
| --- | --- | --- |
| `AETHER_WORKFLOW_NODE_OUTPUT_MAX_BYTES` | `8192` | 노드 출력 상한(D-8) |
| `AETHER_WORKFLOW_SWEEP_INTERVAL_SECONDS` | (plan 이 정함) | 파킹 스위퍼 주기(2.5) |

새 변수는 `infra/docker/.env.example` 과 함께 갑니다. 기본값으로 오프라인에서 동작해야 합니다.

### 2.12 검증 단계 (D-16)

**단계 수를 늘리지 않습니다.** 2026-10-12 실측으로 `verify.sh --full` 이 507.6초이고 예산 600초 대비 **여유가 92초(15%)** 뿐입니다. Phase 4 의 판정은 기존 `api-unit`·`api-integration`·`api-arch` 에 얹습니다.

**`smoke` 에 Workflow 시나виоли오를 더하지 않습니다.** `smoke` 는 2026-10-12 에 Knowledge 적재·검색 시나리오가 들어가 99.7초가 됐고(spec 0004 2.9.1), 여기에 Workflow 를 더하면 남은 여유를 그 하나가 먹습니다. Phase 완료 판정은 `api-integration` 의 testcontainers 로 충분히 관측됩니다 — compose 전체를 띄워야만 보이는 것이 Phase 4 에는 없습니다.

예산이 넘으면 선택 실패로 집계되고, **임계 조정은 사람이 합니다**(EI-2). 에이전트가 올리지 않습니다.

### 2.13 아키텍처 규칙 (보호 파일 `.importlinter`, 사람) — D-10

**AR-13 을 신설합니다.** AR-3 은 "mcp 와 context 는 runtime 을 import 하지 않는다" 이고 workflow 는 방향이 반대(workflow 가 runtime 을 씀)라, 같은 계약에 넣으면 이름과 내용이 어긋납니다. `AR-1 ~ AR-12` 가 쓰였으므로 AR-13 이 빕니다.

```ini
[importlinter:contract:ar13-runtime-does-not-know-workflow]
name = AR-13 runtime must not import workflow
type = forbidden
source_modules =
    aether_runtime
forbidden_modules =
    aether_workflow
```

**함께 닫는 구멍 하나.** AR-3 의 `source_modules` 는 `aether_mcp`·`aether_context` 뿐이라 **`aether_memory` 도 방향 계약이 없습니다** — Phase 3 이 그 패키지를 만들면서 넣지 않았습니다. 실제 위반은 없습니다(2026-10-12 확인: `aether_memory` 는 자기 자신 외에 아무것도 import 하지 않고, 포트는 각 패키지가 자기 시그니처로 선언하며 worker 의 `main` 이 꽂습니다). 막는 것이 없을 뿐입니다. AR-13 과 같은 PR 에서 `aether_memory` 를 AR-3 의 `source_modules` 에 더합니다.

`.importlinter` 는 보호 파일이고 하네스 변경은 **한 번에 하나**이며 변경 사이에 평가를 실행합니다(CC-1·CC-5). 그래서 이 변경은 **intent·spec 과 다른 PR** 로, `harness-change` 라벨과 red 증거(runtime 에 `import aether_workflow` 를 주입해 `api-arch` 가 실패하는지)와 함께 사람이 병합합니다. 적용 시점은 **P4-1 보다 앞**입니다 — 계약을 먼저 세우면 첫 workflow 코드가 처음부터 위반할 수 없습니다.

## 3. 우려 지점

| # | 우려 | 지금의 답 |
| --- | --- | --- |
| C-1 | Workflow Run 을 분리하면 이벤트·취소·trace·SSE 를 한 벌 더 만듭니다 | 받아들입니다. 합치는 대안은 `aether_runtime` 이 workflow 를 알아야 해서 AR-13 을 깨고, 이벤트 어휘도 섞입니다(DP-1). **표가 아니라 패턴을 재사용**해 중복을 줄입니다 |
| C-2 | 파킹·재개가 상태 기계를 하나 더 만들고, 거기서 유실·중복이 생길 수 있습니다 | 유실은 스위퍼가, 중복은 멱등 재개가 막습니다(2.5). 둘 다 R-7·R-8 이 판정합니다. 안전망 없는 이벤트 의존은 받지 않습니다 — 그 실패를 하네스에서 이미 겪었습니다(`2026-10-11-001`) |
| C-3 | **노드 출력이 새 제품 표면입니다**(2.4). 확신이 가장 낮은 결정입니다 | 상한(8 KiB)·평면(`data` 만)·제외(span·감사·보고)를 spec 에 박았습니다. 되돌리는 조건: CONDITION 이 메타데이터만으로 충분하다는 실측이 나오면 출력을 메타데이터로 좁힙니다. 그 판단은 Phase 4 가 끝난 뒤 사람이 합니다 |
| C-4 | 승인자 권한 모델이 없어 "승인" 이 형식만 남을 수 있습니다 | 그렇습니다. 그 공백을 2.6 에 **이름 붙여** 적었습니다. v1 이 보장하는 것은 "승인 없이는 전진하지 않는다" 와 "누가 승인했는지 남는다" 둘이고, "누가 승인할 수 있는가" 는 Phase 8 입니다. 반쪽짜리 권한 모델을 지금 넣지 않는 것이 이전 비용을 줄입니다 |
| C-5 | 병렬이 한 worker 안이라 큰 Workflow 가 느립니다 | Phase 4 의 목표는 표현력이지 처리량이 아닙니다. 분산은 Non-goal 이고, 필요해지면 그때 측정으로 시작합니다 |
| C-6 | verify 예산 여유가 15% 뿐인데 통합 테스트가 늘어납니다 | 단계 수를 늘리지 않고 `smoke` 도 건드리지 않습니다(2.12). 그래도 넘으면 선택 실패로 집계되고 임계는 사람이 봅니다(EI-2) |
| C-7 | `domain.md` 에 용어가 없어 코드가 용어를 발명할 수 있습니다 | 이 spec 이 용어를 고정합니다(2.2, D-7). `domain.md` 는 타입이 실재하는 P4-1 병합 커밋에서 채웁니다 — 있는 것을 서술하는 문서이기 때문입니다 |

## 4. 결정 요청

| # | 결정 | 근거 | 어디 |
| --- | --- | --- | --- |
| D-1 | Workflow Run 은 Agent Run 과 **분리**합니다 — 다른 표·다른 enum·다른 이벤트 어휘. 표가 아니라 **패턴**을 재사용합니다. 합치면 `aether_runtime` 이 workflow 를 알아야 하고 그것이 AR-13 위반입니다 | intent OQ 1 | 2.1, 2.3, 2.10, C-1 |
| D-2 | Workflow Run 의 대기를 **두 값**으로 둡니다 — `waiting_run`·`waiting_approval`. 사유 컬럼 하나로 두지 않습니다. `data.run_execution_status`(마이그레이션 0001)는 건드리지 않습니다 | intent OQ 2 | 2.3, R-13 |
| D-3 | 자식 Agent Run 과의 연결은 **workflow 쪽**(`data.workflow_node_executions.agent_run_id`)에 둡니다. Run 쪽에 Workflow 참조를 넣지 않습니다 | D-1, AR-13 | 2.9 |
| D-4 | 대기는 **파킹**입니다 — 상태만 남기고 worker 슬롯과 lease 를 놓습니다. 깨우는 신호는 자식 Run 의 `run.finished` 이벤트와 승인 API 이고 같은 경로("재큐")로 들어옵니다. **스위퍼를 안전망으로** 두고, 재개는 **멱등**입니다 | intent OQ 3 | 2.5, R-7, R-8, C-2 |
| D-5 | 평면은 **쓰는 주체**로 가릅니다 — 정의·Version·Run 투영·**승인 기록**은 `control`, 노드 실행 기록은 `data`. 마이그레이션 0001 의 역할·GRANT 가 정한 규칙입니다 | intent OQ 4 | 2.9 |
| D-6 | 승인은 **인증된 주체 누구나** 할 수 있고 `approved_by`·`approved_at`·대상 노드 실행을 기록합니다. **승인자 권한 모델은 만들지 않고 그 공백을 명시**합니다(Phase 8). 승인은 특정 노드 실행을 지목해야 하고 그것이 대기가 아니면 거부합니다(정확성 가드). "자기 승인 금지" 는 넣지 않습니다 | intent OQ 5 | 2.6, R-12, C-4 |
| D-7 | **용어는 이 spec 이 고정**하고(2.2), `docs/domain.md` 는 **P4-1 병합과 함께** 채웁니다. 문서는 있는 것을 서술합니다 | intent OQ 6 | 2.2, C-7 |
| D-8 | 노드 출력은 **JSON 객체 + 8 KiB 상한**이고 자르면 그 사실을 기록합니다. `AGENT` 노드의 출력은 자식 Run 의 마지막 assistant 본문을 상한까지 자른 것입니다. **`data` 에만 두고 span·감사·보고에는 넣지 않습니다.** 이것이 **새 제품 표면**이라는 사실과 되돌리는 조건을 함께 적습니다 | intent OQ 7 | 2.4, R-15, C-3 |
| D-9 | CONDITION 은 **선언된 필드 경로 + 선언된 연산자**로 판정합니다(`equals`·`not_equals`·`contains`·`gt`·`lt`·`exists`). 임의 표현식을 평가하지 않고 **모델에게 묻지 않습니다** | intent Non-goal | 2.4, R-5 |
| D-10 | 방향 계약은 **AR-13 신설**이고, 같은 PR 에서 **`aether_memory` 를 AR-3 에 추가**합니다. `.importlinter` 는 보호 파일이므로 intent·spec 과 **다른 PR**, `harness-change` 라벨, red 증거와 함께 사람이 병합합니다. 적용은 **P4-1 보다 앞** | intent OQ 8, CC-1·CC-5 | 2.13, R-15 |
| D-11 | `LOOP` 는 `max_iterations` 가 **필수**입니다. 없거나 0 이하인 정의는 저장 시점에 거부합니다 | intent Constraint | 2.2, R-3, R-10 |
| D-12 | `Workflow Version` 은 **불변**입니다. 실행 중인 Run 의 정의는 바뀌지 않습니다 | intent Constraint | 2.2, R-2 |
| D-13 | Workflow 는 **자기 이벤트 어휘**를 가집니다. Agent Run 의 이벤트 계약에 노드 이벤트를 섞지 않습니다 | DP-1 | 2.10 |
| D-14 | 노드 종류는 열 — `START`·`END`·`AGENT`·`CONDITION`·`PARALLEL`·`JOIN`·`LOOP`·`WAIT`·`LLM`·`MCP`·`TOOL`. `WEBHOOK`·`SCHEDULE` 은 범위 밖(인바운드 네트워크·스케줄러) | backlog | 2.2 |
| D-15 | 병렬은 **한 worker 안**입니다. 분산 실행은 범위 밖 | backlog | 2.7, C-5 |
| D-16 | **검증 단계 수를 늘리지 않고 `smoke` 도 건드리지 않습니다.** 2026-10-12 실측 `--full` 507.6초 / 예산 600초(여유 15%). 판정은 기존 `api-unit`·`api-integration`·`api-arch` 에 얹습니다. 임계 조정은 사람 | EI-2, 실측 | 2.12, C-6 |

## 5. 검증 매핑

| 요구 | 단위 | 어디서 판정 |
| --- | --- | --- |
| R-1, R-2, R-3 | P4-1 | `api-unit`(검증 순수 함수), `api-integration`(저장 거부) |
| R-4, R-5, R-6 | P4-2, P4-4 | `api-integration` |
| R-7, R-8 | P4-2 | `api-integration`(점유), `api-unit`(멱등) |
| R-9, R-10, R-11 | P4-3 | `api-unit` |
| R-12, R-13 | P4-4 | `api-integration` |
| R-14 | P4-5 | `api-arch`, `api-integration` |
| R-15 | D-10(사람) | `api-arch` + `tests/arch` 주입 1건 |

## 6. 이 spec 이 답하지 않는 것

- **승인자 권한 모델** — 누가 승인할 수 있는가. Phase 8(Trust Layer). 공백을 2.6 에 명시했습니다.
- `WEBHOOK`·`SCHEDULE` 노드 — 인바운드 네트워크와 스케줄러.
- Workflow 편집 UI·시각화 — Phase 5.
- 승인 알림(메일·메신저·푸시).
- 분산 실행·수평 확장.
- 노드별 재시도 정책의 세분화 — Run 수준의 재시도(P1-7)를 그대로 씁니다.
- Workflow 정의의 마이그레이션·버전 호환 — Version 은 불변이고 이전은 하지 않습니다.
- Workflow 를 겨냥한 평가 task — Phase 7 과 하네스 평가 쪽 결정입니다.

## 개정 이력

| 개정 | 내용 |
| --- | --- |
| 4 | 2026-10-15, **P4-2b 착수 전**(2.2·2.4). (1) `CONDITION` 도 종류별 설정을 가집니다 — `condition_path`·`condition_operator`·`condition_value`, 분기는 간선 `label` 의 `true`·`false`. 저장 때 거부 둘을 더해 사유가 **열한 개**입니다. (2) 판정 대상을 **선언된 맥락**(`input`·`nodes.<id>`)으로 고정했습니다 — "직전 노드" 같은 암묵 규칙을 두지 않습니다. (3) 없는 경로·비교 불가 타입은 **실행 실패**이고 조용한 거짓이 아닙니다. (4) **노드 실행 조회 API 를 만들지 않습니다** — api 역할은 `data` 에 권한이 없고 투영은 Phase 5 의 일입니다. 그래서 출력의 소비자는 지금 `CONDITION` **하나**이고 C-3 의 되돌리기가 더 싸집니다. R-5 의 판정은 그대로입니다 |
| 3 | 2026-10-14, **P4-2a B 착수 전에 막힌 것 둘**. (1) 노드가 **종류별 설정**을 가집니다(2.2) — `AGENT` 의 `agent_id`(선택 `agent_version`). 초안 모델에는 그 자리가 없어 `AGENT` 노드가 무엇을 실행할지 말할 수 없었습니다. 참조 없는 `AGENT` 를 저장 때 거부하므로 사유가 **아홉 개**가 됩니다. (2) 깨우는 신호는 자식 Run 의 **종결 상태 통지**(`aether:runs:status` + Workflow 전용 group)입니다(2.5) — `run.finished` 가 있는 per-run 이벤트 스트림은 group 으로 받을 수 없고, 거기서 읽으면 빠른 경로가 스위퍼와 같은 장치가 되어 "경로 둘" 이 붕괴합니다. 함께 정한 것: 자식 Run 의 입력은 Workflow Run 의 `input` 직렬화, `requested_by` 는 비움. R-1 ~ R-15 를 약화하지 않습니다 — 거부를 하나 늘리고 R-7·R-8 의 판정 대상을 그대로 둡니다 |
| 2 | 2026-10-14, **P4-2a 착수 전 GRANT 실측**(2.9). 실행 상태·lease 를 `data.workflow_run_executions`(마이그레이션 0006)로 옮기고 `control.workflow_runs` 를 **투영**으로 고정했습니다 — worker 역할은 `control` 에 SELECT 뿐이라 초안대로는 실행기가 상태를 쓸 수 없습니다. 자식 Agent Run 의 **선언은 api 가** 만들고 실행기는 id 를 정해 요청만 싣습니다. 요구는 약해지지 않습니다 — R-6·R-7·R-8 의 판정 대상이 `control` 에서 `data` 로 옮겨 가고, 평면 규칙(D-5)과 권한 경계는 그대로 지켜집니다. **GRANT 를 넓히지 않은 것이 이 개정의 요점**입니다 |
| 1 | 2026-10-13, **P4-1 구현 중 발견한 것 셋**(2.2). (1) START 거부를 **두 사유로** 나눴습니다 — R-1 이 "0개·2개 각각" 을 요구하므로 한 사유로는 판정이 서지 않습니다. (2) **같은 id 를 가진 노드 거부를 더했습니다** — 중복 id 가 검증을 통과해 저장에서 PK 충돌로 터지는 구멍이 있었습니다(2026-10-13 실측: 위반 0건으로 통과). 저장 때 4xx 로 잡는 쪽이 500 보다 낫고, 근거는 "간선이 없는 노드 id" 거부와 같습니다. (3) `PARALLEL` ~ `JOIN` 의 **"대응" 을 v1 에서 정의**했습니다 — 하류에 JOIN 이 하나라도 있으면 통과이고 중첩 짝 맞추기는 검사하지 않습니다. 초안이 "대응" 을 정의하지 않아 구현이 해석해야 했습니다. 셋 다 R-1 ~ R-15 를 **약화하지 않습니다** — 거부를 늘리고 판정을 좁힙니다 |
| 초안 | 2026-10-12. intent 0005 의 열린 질문 8건을 D-1 ~ D-10 으로 닫고, backlog 와 intent 의 제약을 D-11 ~ D-16 으로 고정했습니다. 외부 사실 확인은 없었습니다 — 여덟 질문 전부가 이 저장소의 관측(방향 계약 부재, `waiting` 선점, 평면 규칙, 응답 본문의 표면 부재)으로 답해졌습니다. 가장 확신이 낮은 결정은 **D-8**(노드 출력이 새 제품 표면)이고 되돌리는 조건을 C-3 에 적었습니다 |
