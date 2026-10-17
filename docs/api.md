# API 계약

이 문서는 `apps/api` 가 내는 HTTP 계약과 Plane 사이의 스트림 계약의 **읽기용 요약**입니다. 정본은 셋입니다 — 경로·모델은 [../packages/sdk/openapi.json](../packages/sdk/openapi.json)(`aether-api openapi` 가 내보내고 `test_openapi_drift` 가 지킴), 결정은 [../specs/0002-phase-1-agent-runtime.md](../specs/0002-phase-1-agent-runtime.md) 2.2·2.7·2.18, 용어는 [domain.md](domain.md). 이 문서가 그것들과 갈라지면 그쪽이 이깁니다.

## 1. 공통

| 항목 | 규칙 |
| --- | --- |
| 인증 | `Authorization: Bearer <key>`(spec 0001 2.9). `/healthz` 와 OpenAPI 문서 경로(`/openapi.json`, `/docs`, `/redoc`)만 예외. 실패는 `401 {"detail": "unauthorized"}` + `WWW-Authenticate: Bearer` |
| 오류 본문 | `{"detail": "<코드>"}` 하나의 형태. **예외**: 요청 검증 실패 `422` 는 FastAPI 기본 형태(`detail` 이 배열) |
| 식별자 | uuid. 버전 번호는 1 부터의 정수 |
| 시각 | ISO 8601, UTC |
| 계약 변경 | API-first(DP-1). 경로·모델을 바꾸면 `openapi.json` 과 sdk 생성 타입을 같은 PR 에서 갱신하고, 파괴적 변경 여부를 먼저 판정합니다 |

## 2. Agent Registry (P1-1)

`Agent` 는 정의이고 `Agent Version` 은 그 불변 스냅숏입니다([domain.md](domain.md) 1절). 수정은 새 버전을 만듭니다 — 이전 버전은 DB 트리거가 불변을 보장합니다([data-model.md](data-model.md)).

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| `POST /agents` | `{ name, definition }` — `definition` 은 3절의 `AgentDefinition` | `201 { id, name, current_version: 1, created_at, updated_at }` | `409 agent_name_taken` · `422` |
| `GET /agents` | `?limit=50&cursor=` | `200 { items: [{ id, name, current_version, updated_at }], next_cursor }` — 커서는 불투명 문자열 | — |
| `GET /agents/{id}` | — | `200 { id, name, current_version, definition, versions: [{ version, created_at }], created_at, updated_at }` — `definition` 은 현재 버전의 것 | `404 agent_not_found` |
| `GET /agents/{id}/versions/{version}` | — | `200 { agent_id, version, definition, created_at }` | `404 agent_not_found` · `404 agent_version_not_found` |
| `PUT /agents/{id}` | `{ definition }` | `200`(`GET /agents/{id}` 와 같은 본문, `current_version` +1) | `404 agent_not_found` · `409 agent_version_conflict` · `422` |

- `PUT` 은 `definition` 만 바꿉니다. `name` 은 Phase 1 에서 불변입니다.
- 버전 번호는 서버가 한 트랜잭션에서 `control.agents` 행을 `SELECT … FOR UPDATE` 로 잠근 뒤 `current_version + 1` 로 정합니다. 동시 `PUT` 은 직렬화되며, 그래도 unique 위반이 나면 `409 agent_version_conflict` 입니다(spec 0002 D-9).
- 삭제는 없습니다(spec 0002 6절).

## 3. `AgentDefinition`

`agent_versions.definition` 의 내용입니다. 정본은 `packages/runtime/src/aether_runtime/domain/agent.py` 의 pydantic 모델이고, 그 JSON Schema 가 OpenAPI 에 그대로 실립니다(spec 0002 2.3, D-3).

```json
{
  "schema_version": 1,
  "system_prompt": "You are …",
  "model": { "id": null },
  "tools": ["clock", "calculator"],
  "mcp_servers": [{ "name": "builtin", "transport": "stdio", "ref": "builtin" }],
  "context_budget_tokens": null,
  "knowledge": ["handbook"],
  "knowledge_top_k": null,
  "memory_enabled": false,
  "policy": {
    "timeout_seconds": 120,
    "max_steps": 8,
    "model_retries": 2,
    "tool_retries": 1,
    "backoff": { "base_seconds": 0.5, "max_seconds": 8.0 }
  }
}
```

| 키 | 규칙 |
| --- | --- |
| `schema_version` | `1` 만. 올리는 것은 파괴적 변경 판정 대상 |
| `system_prompt` | 비어 있지 않음 |
| `model.id` | 문자열 또는 `null`(배포 설정 `AETHER_MODEL_ID`). 어댑터 종류·thinking 은 정의가 아니라 배포 설정 |
| `tools` | 중복 없음. **이름의 존재 여부는 생성 시 검증하지 않습니다**(spec 0003 D-16) — 도구는 Discovery 에서 오고 api 는 생성 시점에 어떤 MCP Server 가 무엇을 내놓는지 알 수 없습니다. 없는 이름은 Run 시점에 `ToolNotFound` 로 실패하고 감사에 남습니다 |
| `mcp_servers` | 목록, 기본 `[]`. 각 항목은 `{ name, transport: "stdio"｜"http", ref }` 입니다. **자격증명이나 절대 URL 을 넣지 않습니다** — `ref` 는 배포 설정 `AETHER_MCP_SERVERS` 가 실제 명령·URL 로 푸는 키입니다(spec 0003 2.6·2.9, D-2). 바인딩 변경은 `definition` 변경이므로 기존 `PUT /agents/{id}` 가 그대로 새 Version 을 만듭니다. 빈 목록이면 Run 은 도구 없이 실행됩니다 |
| `context_budget_tokens` | 정수(≥1) 또는 `null`(기본). Context Compiler 가 조립에 쓰는 토큰 예산입니다. `null` 이면 배포 설정 `AETHER_CONTEXT_BUDGET_TOKENS`(기본 8192)를 씁니다 — 모델별 한계가 아니라 **보수적인 고정값**입니다(spec 0004 2.2, D-5) |
| `knowledge` | 이름 목록, 기본 `[]`. 이 Version 이 검색할 Knowledge Set 의 **이름**입니다. 중복 없음. **존재 여부는 생성 시 검증하지 않습니다**(`tools` 와 같은 이유) — 없는 이름은 Run 시점에 조용히 0건이고, 바인딩되지 않은 집합은 검색되지 않습니다. 바인딩 변경은 `definition` 변경이므로 기존 `PUT /agents/{id}` 가 새 Version 을 만듭니다(spec 0004 D-5, R-9) |
| `knowledge_top_k` | 정수(≥1) 또는 `null`(기본 5). 검색 상위 k 입니다(spec 0004 D-2, D-5) |
| `memory_enabled` | `true`｜`false`(기본 `false`). 켜면 Run 이 `succeeded` 로 종결할 때 **마지막 assistant 메시지 본문 그대로** 한 건을 이 Agent 의 Memory 로 남기고, 다음 Run 의 Context 에 `verified=false` 표지를 단 **독립 메시지**로 들어갑니다(spec 0004 2.6, D-8, R-10). 요약·분할·자동 승격은 없습니다. 꺼진 Agent 는 **기록도 읽기도** 하지 않습니다 — 예전에 쌓인 기억이 있어도 읽지 않습니다. 기록 실패는 Run 을 실패시키지 않습니다(부산물) |
| `policy` | `timeout_seconds` 1~3600, `max_steps` 1~64, `model_retries`·`tool_retries` 0~10, `backoff.base_seconds` > 0, `max_seconds ≥ base_seconds` |

## 4. Run (P1-5b)

`Run` 은 `Agent Version` 하나를 한 번 실행한 사건입니다([domain.md](domain.md) 1절). Control Plane(api)은 **선언**만 하고 Data Plane(worker)이 실행합니다(AR-7, spec 0001 D-11) — api 는 `control.runs` 에 행을 넣고 `aether:runs:requested` 로 통지하며, 실행 상태는 worker 의 `aether:runs:status` 알림을 api 안의 소비자가 `control.runs` 의 투영 열로 복제합니다(spec 0002 2.4, D-2).

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| `POST /agents/{id}/run` | `{ input: string, agent_version?: int }` | `202 { run_id, agent_id, agent_version, status: "queued", requested_at, requested_by }` | `404 agent_not_found` · `404 agent_version_not_found` · `422` |
| `GET /runs/{id}` | — | `200 { run_id, agent_id, agent_version, status, requested_at, requested_by, started_at, finished_at, failure_reason, trace_id, cancel_requested_at }` | `404 run_not_found` |
| `POST /runs/{id}/cancel` | — | `202 { run_id, status, cancel_requested_at }` | `404 run_not_found` |

- **선언과 통지의 순서**: `control.runs` 삽입(`input`, `agent_version_id`, `requested_by` = 호출한 API 키의 id, `status = queued`)을 **커밋한 뒤** `aether:runs:requested` 에 XADD. XADD 가 실패해도 `202` — Run 은 `queued` 로 남아 관측 가능하고 선언은 잃지 않습니다(spec 0002 C-2). 클라이언트 재시도는 새 Run 을 만듭니다(멱등키는 Non-goal).
- **`GET /runs/{id}`** 는 `control.runs` 의 투영 열만 읽습니다. 투영이 아직 도착하지 않았으면 `queued` 입니다. `status` 값은 `queued` / `running` / `waiting` / `succeeded` / `failed` / `cancelled` / `timed_out`, `failure_reason` 은 종결이 `failed` 일 때 `model_error` / `tool_error` / `max_steps_exceeded` / `unknown_tool` / `definition_invalid` / `internal`.
- **취소는 협력적이고 멱등**입니다. `cancel_requested_at` 이 비어 있으면 지금 시각을 적고, 이미 있으면 그대로 둡니다. 종결된 Run 에도 `202` 이고 상태는 바뀌지 않습니다. 실제 반영은 worker 가 다음 단계 시작에서 하며(spec 0002 D-11), 결과는 `GET` 이나 이벤트로 봅니다.
- **투영의 멱등**: 상태 알림에는 Run 단위 `seq` 가 있고, api 는 `status_seq < seq` 인 알림만 적용합니다(중복·역행 무시, DB 커밋 뒤 ack).

## 5. 이벤트 스트림

`GET /runs/{id}/events` 는 SSE(`text/event-stream`)입니다(P1-6). 이벤트 모델의 정본은 `packages/runtime/src/aether_runtime/domain/events.py`(P1-4) 이고, `aether-api events-schema` 가 그것을 JSON Schema 로 내보내 [../packages/sdk/events.schema.json](../packages/sdk/events.schema.json) 에 커밋합니다. sdk 의 TS 타입은 그 파일에서 생성됩니다(spec 0002 2.7, D-4, R-12).

**접속 절차**

| 항목 | 규칙 |
| --- | --- |
| 요청 | `GET /runs/{id}/events`, `Authorization: Bearer <key>`, `Accept: text/event-stream`. 재개는 `Last-Event-ID: <seq>` 헤더 — 그 `seq` **다음**부터 받습니다(스트림 ID `<seq>-0` 다음) |
| SSE 필드 | `id: <seq>` · `event: <type>` · `data: <봉투 JSON>`. 빈 줄로 이벤트 구분 |
| 종료 | 서버가 `run.finished` 를 보낸 뒤 연결을 닫습니다. 클라이언트가 먼저 끊어도 Run 은 계속됩니다(worker 는 api 를 모릅니다, AR-7) |
| 스트림이 없을 때 | Run 이 종결이면 `run.finished { status }` 하나를 **합성**해 보내고 닫습니다(TTL 뒤 늦게 온 독자). 종결이 아니면 첫 이벤트가 생길 때까지 기다립니다 |
| 보장하지 않는 것 | `MAXLEN` 으로 잘려 나간 구간의 재생, 재접속 이어보기의 보장(spec 0002 6절). 브라우저 `EventSource` 는 `Authorization` 헤더를 붙일 수 없어 sdk 는 `fetch` 로 SSE 를 파싱합니다 — 브라우저 직접 접속용 인증은 🔒 사람 결정(C-4) |
| 오류 | `404 run_not_found`, `401` |

봉투: `{ "v": 1, "run_id", "seq", "at", "type", "payload" }`. `seq` 는 Run 안에서 1 부터 단조 증가하고, 선택 필드는 값이 없으면 키 자체가 빠집니다.

| type | payload | 언제 |
| --- | --- | --- |
| `run.status` | `status`, `failure_reason?` | 상태 전이마다(`queued→running`, `running↔waiting`, 종결). 같은 `seq` 의 `StatusMessage` 가 `aether:runs:status` 로도 나감 |
| `task.started` | `task_id`, `step` | 단계(모델 호출 1회) 시작 |
| `task.finished` | `task_id` | 단계가 정상 종료(도구 유무 무관). 실패한 단계에서는 없음 |
| `model.completed` | `finish_reason`, `usage?` | `complete` 응답 직후 |
| `tool.called` | `task_id`, `tool_call_id`, `name`, `arguments` | 도구 실행 직전 |
| `tool.result` | `task_id`, `tool_call_id`, `name`, `is_error`, `content`, `truncated` | 도구 실행 직후(잘림 반영) |
| `run.finished` | `status` | 종결 시 **항상 마지막**. 재개 시 재발행되어도 같은 `seq` |
| `model.delta` | `text` | **예약** — Phase 1 은 발생시키지 않음 |

## 5.1 목록 경로 (MVP-0)

모든 목록은 **`GET /agents` 와 같은 규칙**입니다(spec 0006 D-3 — 새 규약을 만들지 않았습니다). 전부 인증 뒤이고 인증 없으면 401 입니다.

- 쿼리: `limit`(기본 **50**, 1~200, 범위 밖은 **422**), `cursor`(이전 응답의 `next_cursor`, **불투명**한 값)
- 응답: `{ "items": [...], "next_cursor": string | null }` — 마지막 쪽은 `null`, **빈 목록도 200** + `items: []`
- **정렬은 경로별로 고정**이고 바꿀 수 없습니다(`order` 파라미터 없음)
- 깨진 `cursor`(빈 문자열·base64 아님·형식 틀림)는 **여섯 경로 전부**(`GET /agents` 포함) **422 `{"detail": "invalid_cursor"}`** 입니다

| 경로 | 정렬 | 필터 |
| --- | --- | --- |
| `GET /runs` | **최신 것부터**(`requested_at`·id 내림차순) | `status` |
| `GET /workflow-runs` | **최신 것부터** | `status` |
| `GET /knowledge-sets/{id}/ingestions` | **최신 것부터**. 없는 세트는 `404 knowledge_set_not_found` | `status` |
| `GET /workflows` | 오래된 것부터(`GET /agents` 와 같음) | 없음 |
| `GET /knowledge-sets` | 오래된 것부터 | 없음 |

**Run·Workflow Run·적재가 최신 것부터인 이유**: 목록 화면의 첫 쪽에 **방금 돌린 것**이 있어야 합니다. 오래된 것부터면 사용자가 마지막 쪽까지 가야 합니다. `/workflows`·`/knowledge-sets` 는 정의 목록이라 생성 순이 자연스럽고 `GET /agents` 와 같습니다.

**`GET /runs` 의 `requested_by` 는 비어 있을 수 있습니다** — Workflow 가 띄운 자식 Run 은 0007 이전에 만들어졌으면 요청자가 없습니다. 그래서 목록 전용 항목(`RunSummary`)은 그 값을 **nullable** 로 둡니다. **상세(`GET /runs/{id}`)는 아직 그 행에서 500** 이고, 그 자리는 Run 상세 화면을 만드는 단위(MVP-2b)가 고칩니다.

**`GET /workflow-runs` 는 `control.workflow_runs`(투영)만 봅니다** — 노드 실행은 `data` 평면이고 api 역할은 그 평면에 권한이 없습니다(spec 0006 D-4). 그래서 **이 경로가 api 역할로 통과하는 것 자체가** 평면을 지켰다는 증거입니다.

SDK: `listRuns`·`listWorkflows`·`listWorkflowRuns`·`listKnowledgeSets`·`listIngestions`(`packages/sdk`).

## 6. Plane 사이의 스트림 계약

Redis Streams(spec 0001 D-10). 방향은 선언은 Control, 실행은 Data 이고 서로의 코드를 import 하지 않습니다(AR-7). 메시지는 선언이 아니라 통지입니다 — 내구적 선언은 `control.runs` 행이고 Redis 가 메시지를 잃어도 Run 은 남습니다(spec 0002 2.18, C-2).

| 스트림 | 방향 | 필드 | 소비 | ID |
| --- | --- | --- | --- | --- |
| `aether:runs:requested` | Control → Data | `run_id`, `agent_version_id`, `traceparent` | worker consumer group `aether-worker`, `count=1`. 시작 시 자기 PEL 먼저(`XREADGROUP … 0`), 그 뒤 `XAUTOCLAIM`(`min-idle` = `AETHER_WORKER_XAUTOCLAIM_MIN_IDLE_MS`, 기본 65분) → `XREADGROUP >`. 실행이 끝나야 `XACK`. 다른 worker 가 lease 를 쥐고 있으면 ack 하지 않음 | Redis 자동 |
| `aether:runs:status` | Data → Control | `StatusMessage`: `run_id`, `seq`, `status`, `at`, `started_at?`, `finished_at?`, `failure_reason?`, `trace_id?` (값 없는 선택 필드는 키 없음) | api consumer group `aether-api`(P1-5b) — `seq` 단조 증가로 멱등 투영 | Redis 자동 |
| `aether:runs:{run_id}:events` | Data → 독자 | `data` = 5절의 봉투 JSON | api SSE 리더(P1-6, 그룹 없음, `XREAD`) | **explicit `<seq>-0`**. 같은 ID 재-XADD(재개 시 재발행)는 어댑터가 성공으로 흡수. `MAXLEN ~ 10000`, `run.finished` 뒤 TTL 24시간 |
| `aether:knowledge:ingestions:requested` | Control → Data | `ingestion_id`, `knowledge_set_id`, `source`, `traceparent` | worker consumer group(적재 전용), `count=1`. Run 과 같은 패턴(자기 PEL → `XAUTOCLAIM` → `XREADGROUP >`). 성공·실패 **모두 ack** — 적재에는 lease 경합이 없습니다(한 적재는 한 worker 가 끝까지 처리) | Redis 자동 |
| `aether:knowledge:ingestions:status` | Data → Control | `ingestion_id`, `status`, `at`, `chunk_count?`, `failure_reason?` | api consumer group — `control.knowledge_ingestions` 에 투영 | Redis 자동 |
| `aether:workflow_runs:requested` | Control → Data | `workflow_run_id`, `workflow_version_id`, `traceparent` | worker consumer group `aether-worker`, `count=1`. Run 과 같은 패턴(자기 PEL → `XAUTOCLAIM` → `XREADGROUP >`). lease 를 다른 worker 가 쥐고 있으면 ack 하지 않음 | Redis 자동 |
| `aether:workflow_runs:status` | Data → Control | `workflow_run_id`, `seq`, `status`, `at`, `current_node_id?`, `waiting_run_id?`, `started_at?`, `finished_at?`, `failure_reason?` (값 없는 선택 필드는 키 없음) | api consumer group `aether-api` — `seq` 단조 증가로 멱등 투영 | Redis 자동 |
| `aether:workflow:agent_runs:requested` | Data → Control | `agent_run_id`, `agent_version_id`, `input`, `requested_by`, `traceparent` | api consumer group `aether-api` — 받은 id 로 `control.runs` 에 `INSERT … ON CONFLICT DO NOTHING` 하고 `aether:runs:requested` 에 통지 | Redis 자동 |
| `aether:workflow_runs:{id}:events` | Data → 독자 | `data` = Workflow 자기 어휘의 봉투 JSON(9절) | **읽는 경로가 아직 없습니다** — SSE 는 Phase 5 | **explicit `<seq>-0`**, `MAXLEN ~`, 종결 뒤 TTL. Run 이벤트와 같은 계약 |

**자식 Agent Run 의 선언을 api 가 만드는 이유**(spec 0005 2.5 개정 3): worker 는 `control.runs` 에 **INSERT 할 수 없습니다**(`aether_data` 는 `control` 에 SELECT 뿐). 그래서 실행기가 자식 Run 의 **id 를 정해** 요청만 싣고 api 가 그 id 로 선언을 만듭니다 — id 를 실행기가 정하므로 요청이 두 번 가도 선언은 한 행이고(R-8), 파킹은 처음부터 기다릴 대상을 압니다. api 는 **해석하지 않습니다**: Agent Version 은 실행기가 `control.agent_versions` 에서 풀고, 없으면 노드를 실패시킵니다 — api 가 풀게 하면 없는 Agent 를 가리킨 노드가 영원히 파킹됩니다(독약 메시지는 ack 되고 끝나므로).

재전달에서 선언이 이미 있으면 api 는 **상태를 보고** 결정합니다 — 아직 `queued` 면 **다시 통지**하고, `running` 이후면 하지 않습니다. 선언은 커밋됐는데 `XADD` 가 실패한 창이 있고, 그때 통지하지 않으면 자식 Run 이 `queued` 로 남아 그것을 기다리는 Workflow 가 영원히 파킹됩니다(스위퍼는 자식의 **종결**을 보므로 구하지 못합니다).

**적재의 상태를 api 가 쓰는 이유**(spec 0004 개정 5): `aether_data` 는 `control.knowledge_ingestions` 에 **SELECT 만** 가집니다(마이그레이션 0004). worker 는 그 표에 쓸 수 없으므로 상태를 스트림으로 되돌려 보내고 api 가 투영합니다 — Run 과 같은 경계입니다(Control 만 `control` 에 씁니다).

`StatusMessage.seq` 는 대응하는 `run.status` 이벤트의 `seq` 와 같은 수열입니다. worker 는 `aether:worker:{consumer}:heartbeat` 키(TTL = heartbeat 주기의 3배)로 살아 있음을 알리고 compose 의 healthcheck 가 그것을 봅니다(spec 0002 2.14).

## 7. Knowledge 적재 (P3-2b)

전부 인증 뒤입니다(P0-9). 적재는 **선언**이고 실행은 worker 입니다(spec 0004 D-4) — Run 과 같은 모양입니다.

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| `POST /knowledge-sets` | `{ name }` | `201 { id, name, created_at }` | `401`, 이름 중복 |
| `POST /knowledge-sets/{id}/ingestions` | `{ source }` | `202 { ingestion_id, knowledge_set_id, source, status: "queued", requested_at }` | `404 knowledge_set_not_found` |
| `GET /knowledge-ingestions/{id}` | — | `200 { …, status, started_at?, finished_at?, failure_reason? }` | `404 knowledge_ingestion_not_found` |

`202` 인 이유는 Run 과 같습니다 — 요청은 선언을 기록하고 즉시 돌아오며, 적재는 worker 가 비동기로 합니다. 상태는 6절의 두 스트림으로 오갑니다.

`failure_reason` 은 **500자로 잘립니다** — 적재 실패 메시지에 문서 본문이 섞여 들어가 무한정 커지는 것을 막습니다(spec 0004 R-11 과 같은 취지).

청크는 문자 기준 고정 크기 + 겹침입니다(기본 1000/200, `AETHER_KNOWLEDGE_CHUNK_CHARS`·`AETHER_KNOWLEDGE_CHUNK_OVERLAP_CHARS`). 임베딩은 `ModelGateway.embed` 를 지나고(AR-5) 모델은 채팅과 **별도 핀**입니다(`AETHER_EMBED_MODEL_ID`). 청크에는 그 모델 id 와 차원이 함께 저장되며, 검색 시 현재 설정과 다르면 **재적재를 요구하는 오류**가 납니다(spec 0004 D-9) — 조용히 섞지 않습니다.

검색의 HTTP 경로는 아직 없습니다. 이 단위는 포트와 어댑터까지이고, Context 에 넣는 것과 그 경로는 P3-3 입니다.

## 8. Workflow 정의 (P4-1)

전부 인증 뒤입니다(P0-9). 이 절은 **정의**뿐입니다 — 실행·승인 경로는 P4-2a·P4-4 입니다.

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| `POST /workflows` | `{ name, nodes[], edges[] }` | `201 { id, name, current_version, nodes, edges }` | `400 invalid_workflow_graph` + `violations[]`, `401`, `422`(요청 모양) |
| `GET /workflows/{id}` | — | `200`(최신 Version 포함) | `404 workflow_not_found` |
| `PUT /workflows/{id}` | `{ nodes[], edges[] }` | `200` — **새 Version** | `400`, `404 workflow_not_found` |
| `GET /workflows/{id}/versions/{version}` | — | `200 { workflow_id, version, nodes, edges }` | `404 workflow_version_not_found` |

**`PUT` 은 고치지 않고 더합니다.** `Workflow Version` 은 불변이고(spec 0005 D-12) 실행 중인 Run 은 시작 당시 Version 을 계속 가리킵니다 — `AgentDefinition` 의 `PUT`(2절)과 같은 규칙이며, 불변성은 앱의 예의가 아니라 **DB 트리거**가 지킵니다([data-model.md](data-model.md) 3절).

**검증은 저장 시점**입니다. 거부는 `400` 이고 본문이 `{"detail": "invalid_workflow_graph", "violations": [{ "reason", "node_id" }]}` 입니다 — 1절의 `{"detail": "<코드>"}` 에 `violations` 를 더한 모양입니다. `422` 를 쓰지 않은 이유는 FastAPI 의 요청 모양 검증이 그 코드를 이미 쓰고, 둘이 겹치면 클라이언트가 "그래프가 틀렸다" 와 "JSON 이 틀렸다" 를 구별할 수 없기 때문입니다.

**노드는 종류별 설정을 가집니다.** `kind = AGENT` 인 노드는 `agent_id`(필수)와 `agent_version`(선택)으로 **무엇을 실행할지** 말합니다 — `LOOP` 의 `max_iterations` 와 같은 자리입니다(spec 0005 **개정 3**). `agent_version` 을 주지 않으면 실행 시점의 최신 Version 입니다. 다른 종류의 `agent_id` 는 무시하고 거부하지 않습니다(`max_iterations` 를 다루는 방식과 같습니다). 두 키는 **선택**이므로 기존 요청 본문은 그대로 유효하고, 개정 3 전에 저장된 Version 은 두 값이 `null` 로 읽힙니다.

`kind = CONDITION` 인 노드는 세 키로 **무엇을 보고 갈라지는지** 말합니다(개정 4).

| 키 | 뜻 |
| --- | --- |
| `condition_path` | 판정 대상의 경로(점 표기). 맥락은 `{"input": <Workflow Run 의 입력>, "nodes": {"<노드 id>": <그 노드의 출력>}}` — 예 `input.q`, `nodes.ask.text` |
| `condition_operator` | `equals`·`not_equals`·`contains`·`gt`·`lt`·`exists` 중 하나. **열거형**이므로 다른 값은 `422` 입니다 |
| `condition_value` | 비교할 JSON 스칼라(문자열·숫자·불리언). `exists` 면 없음. `null` 은 "값 없음" 으로 읽으므로 `equals null` 은 표현하지 않습니다 |
| `wait_seconds` | `WAIT` 전용(필수, 0 보다 큼). 없으면 저장 때 `wait_node_without_duration` |
| `llm_prompt` · `llm_prompt_path` | `LLM` 전용. 리터럴 프롬프트(필수)와, 맥락에서 끌어와 **뒤에 덧붙일** 값의 경로(선택) |
| `tool_server` · `tool_name` | `TOOL`·`MCP` 전용(필수). 없으면 `tool_node_without_target` |
| `tool_arguments` · `tool_arguments_path` | `TOOL`·`MCP` 전용. 리터럴 객체(선택)와 맥락 경로(선택) — **경로 값이 리터럴을 이깁니다** |

분기는 나가는 간선의 `label` 이 `"true"`/`"false"` 인 쪽입니다 — 선언 순서와 무관합니다. `contains` 는 문자열의 부분 문자열·리스트의 원소·객체의 키를 봅니다. `gt`·`lt` 는 **숫자만**이고 불리언은 숫자로 취급하지 않습니다. 경로는 객체 키만 따라가므로 배열 인덱스를 쓸 수 없고, 노드 id 에 `.` 이 있으면 그 노드의 출력은 경로로 가리킬 수 없습니다 — 모호한 문법을 늘리지 않았습니다.

`reason` 은 열네 값 중 하나입니다 — `no_start`·`multiple_start`·`end_unreachable`·`orphan_node`·`dangling_edge`·`duplicate_node_id`·`loop_without_bound`·`parallel_without_join`·**`agent_node_without_agent`**(`AGENT` 에 `agent_id` 가 없음, 개정 3)·**`condition_node_without_predicate`**·**`condition_node_without_both_branches`**(개정 4 — `LOOP` 에도 같은 두 사유를 씁니다, 개정 7)·**`wait_node_without_duration`**(개정 7)·**`llm_node_without_prompt`**·**`tool_node_without_target`**(개정 9). `agent_node_without_agent` 의 뜻은 **"Agent 참조가 필요한 노드(`AGENT`·`TOOL`·`MCP`)에 참조가 없음"** 으로 넓어졌습니다(개정 9). 한 정의가 여러 규칙을 어기면 **전부** 돌려줍니다(spec 0005 2.2 와 개정 1·3·4).

## 9. Workflow Run (P4-2a)

전부 인증 뒤입니다. 실행은 **선언**이고 전진은 worker 입니다 — Agent Run·Knowledge 적재와 같은 모양입니다(spec 0005 D-1 은 "표가 아니라 패턴을 재사용" 이라고 적었습니다).

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| `POST /workflows/{workflow_id}/runs` | `{ input?, workflow_version? }` | `202 { workflow_run_id, workflow_id, workflow_version, status: "queued", requested_at }` | `401`, `404 workflow_not_found`·`workflow_version_not_found`, `422` |
| `GET /workflow-runs/{workflow_run_id}` | — | `200 { …, workflow_version_id, status, current_node_id?, waiting_run_id?, started_at?, finished_at?, failure_reason? }` | `401`, `404 workflow_run_not_found` |

`workflow_version` 을 주지 않으면 **최신 Version** 으로 시작하고, 시작한 Run 은 그 Version 을 계속 가리킵니다(D-12 — Version 은 불변입니다). 경로가 `/workflow-runs/{id}` 로 **최상위**인 이유는 Agent Run(`/runs/{id}`)과 같습니다 — Run 은 Workflow 의 하위 자원이 아니라 자기 수명을 가집니다.

`status` 는 일곱 값입니다(spec 0005 2.3) — `queued`·`running`·`waiting_run`·`waiting_approval`·`succeeded`·`failed`·`cancelled`. **Agent Run 의 `waiting` 과 다른 enum** 이고 `timed_out` 이 없습니다. 대기를 두 값으로 가른 것이 "무엇을 기다리는가" 를 상태만으로 답하게 합니다(R-13).

**`waiting_run_id` 는 상태에서 유도됩니다** — `waiting_run` 일 때만 값이 있고 다른 상태로 가면 비워집니다. 투영 스트림(6절)은 값을 **지우는** 신호를 실을 수 없으므로(값 없는 선택 필드는 키 자체가 없고, 투영은 `COALESCE(new, old)` 입니다) 이것을 불변식으로 둡니다. 그러지 않으면 `succeeded` 인 Run 이 자식 Run 을 기다리는 것처럼 보입니다.

`GET` 이 보는 것은 `control.workflow_runs` 의 **투영**입니다. 실행 상태의 정본은 `data.workflow_run_executions` 이고(spec 0005 2.9 개정 2) worker 가 씁니다 — 적재의 상태를 api 가 투영하는 것과 같은 경계입니다(6절). 그래서 조회는 상태 메시지가 도착한 뒤에 바뀝니다.

### 9.1 LLM · MCP · TOOL 노드 (P4-5)

Agent 를 거치지 않고 **한 번** 부르는 노드 셋입니다. 파킹하지 않습니다(자식 Run 이 없습니다).

**통로를 새로 만들지 않았습니다** — 모델은 `ModelGateway`(AR-5), 도구는 MCP Gateway(AR-6, 판정 → 호출 → 감사를 이미 하는 그 경로)를 지납니다. `aether_workflow` 는 포트만 선언하고 `httpx`·벤더 SDK·`mcp` 를 import 하지 않습니다(`api-arch` 가 판정). 조립은 worker 의 `main` 뿐입니다(AR-10).

**`MCP` 와 `TOOL` 은 v1 에서 같습니다**(spec 0005 개정 9) — 모든 도구 호출이 MCP Gateway 를 지나므로 구현이 같고, 쓰이지 않는 분기를 만들지 않습니다.

**권한 주체는 노드가 지목한 Agent 입니다**(개정 9, 사람 결정 2026-10-16). Policy 는 `agent_version_id` 로만 판정하고 그 열에는 `control.agent_versions` FK 가 걸려 있어 **Workflow Version 을 주체로 쓸 수 없습니다.** 그래서 `TOOL`·`MCP` 노드가 `agent_id`(선택 `agent_version`)를 지목하고 도구 호출은 **그 Agent Version 의 권한으로** 나갑니다. Policy 의 코드·스키마는 바뀌지 않았고 **기본 deny 가 그대로**입니다 — 권한이 없으면 노드가 `tool_call_denied` 로 **실패**합니다(조용히 넘어가지 않습니다). Workflow 자신을 주체로 보는 모델은 Phase 8 의 자리입니다.

출력은 `LLM` 이 `{"text", "finish_reason"}`, `TOOL`·`MCP` 가 `{"content", "is_error"}` 이고 9.2 의 상한을 그대로 받습니다. 도구가 `is_error` 면 노드 실패(`tool_call_failed`), 모델 호출이 터지면 `model_call_failed` 입니다.

**감사는 남습니다 — 그러려고 FK 를 풀었습니다**(개정 10). `data.tool_call_audit.run_id` 가 `control.runs` 를 FK 로 가리키고 있어서 Workflow Run 의 도구 호출은 감사 행을 쓸 수 없었고, 감사 쓰기 실패는 **삼켜지므로**(spec 0003 D-10) 호출은 성공하고 기록만 조용히 사라졌습니다. 마이그레이션 0010 이 그 FK 를 풀고 `run_kind`(`agent`·`workflow`)를 더해 **어느 평면의 Run 인지**를 남깁니다. 도구 호출은 Agent Run 이든 Workflow Run 이든 같은 표에 같은 모양으로 쌓입니다.

### 9.1 분기·합류·루프·대기 (P4-3)

**진행은 노드 실행 기록에서 읽습니다.** 분기가 둘 이상이면 "현재 노드" 하나로 진행을 말할 수 없습니다 — 전진할 수 있는 노드는 **들어오는 간선이 모두 결판나고 그중 하나 이상이 활성**인 노드입니다. 간선은 출발 노드가 `succeeded` 면 활성이고, `CONDITION`·`LOOP` 은 **고른 `label` 의 간선만** 활성입니다(타지 않은 분기의 하류는 실행되지 않습니다). `current_node_id` 는 이제 **"마지막으로 전진한 노드"**(관측용)입니다.

**`PARALLEL` 의 병렬은 동시성이 아닙니다**(spec 0005 개정 7). 한 worker 가 분기를 차례로 전진시키고 `JOIN` 이 전부를 기다립니다. 보장하는 것은 "모든 분기가 실행되고 합류 뒤 다음 노드가 **한 번**"(R-9)입니다. 분기 안에서 파킹이 일어나면 Run 전체가 파킹되고 재개 때 남은 분기를 잇습니다 — 그래서 자식 Run 을 가진 분기들은 직렬화됩니다. 목표는 표현력이고 처리량이 아닙니다(C-5).

`JOIN` 의 출력은 `{"branches": {"<들어오는 노드 id>": <그 노드의 출력 또는 null>}}` 이고 9.2 의 상한을 그대로 받습니다 — 넘치면 **가장 큰 분기 출력부터** `null` 로 바꾸고 `output_truncated` 를 켭니다. **분기 하나라도 실패하면** Workflow Run 이 `failed` + `branch_failed` 입니다.

**`LOOP`** 은 `CONDITION` 과 **같은 판정식 키**를 쓰고 `true` 간선이 본문, `false` 가 탈출입니다. 회차는 `iteration` 이고 본문 노드는 한 바퀴마다 1씩 늘어납니다. `max_iterations` 를 넘기면 `failed` + `loop_limit_exceeded` 입니다(R-10) — 분기 안에서도 이 사유는 `branch_failed` 로 덮이지 않습니다. 판정식이 **본문 출력**(`nodes.<본문>.…`)을 가리킬 때, 그 노드가 이 Version 에 있는데 이번 회차 기록이 아직 없으면 "계속" 으로 읽습니다(개정 8) — 그래프에 **없는** 노드 id(오타)는 그대로 `condition_path_missing` 으로 시끄럽게 실패합니다.

**`WAIT` 는 파킹입니다.** `waiting_timer` 와 `wake_at`(= 파킹 시각 + `wait_seconds`)으로 멈추고 **worker 슬롯을 놓습니다** — 실제 시간을 블록하면 그것이 D-4 가 금지한 점유입니다. 깨우는 외부 사건이 없으므로 **스위퍼가 안전망이 아니라 주 경로**입니다(`wake_at <= now()` 를 주워 재큐). 재개한 호출은 `clock.now() >= wake_at` 을 다시 확인하고, 아직이면 아무 것도 바꾸지 않습니다. 새 이벤트 타입은 없습니다 — `workflow.status` 의 값이 `waiting_timer` 입니다.

**파킹은 상태를 저장한 뒤 lease 를 놓고, 그 다음에 이벤트·통지를 냅니다**(개정 8). 상태가 "대기" 라고 말하는 순간부터 lease 는 비어 있습니다 — 그 순서가 아니면 R-7 이 "결국" 참일 뿐입니다. 대가 하나: 해제와 발행 사이에 다른 worker 가 이어받아 더 큰 `seq` 를 먼저 발행하면, 뒤늦은 파킹 이벤트는 스트림의 explicit ID 규칙에 걸려 **버려집니다**(순서가 섞이지 않고 하나가 사라집니다). 상태·투영은 `seq` 로 멱등이므로 영향이 없습니다.

### 9.1 승인 (P4-4, 🔒)

`HUMAN`·`APPROVAL` 노드에 닿으면 Workflow Run 이 `waiting_approval` 로 파킹되고 `waiting_node_execution_id` 가 **지금 무엇을 기다리는지** 가리킵니다. v1 에서 두 종류는 **같게** 동작합니다(spec 0005 개정 5) — "사람의 입력" 과 "승인 게이트" 의 구분은 입력을 받는 표면이 생길 때 갈라집니다.

| 메서드·경로 | 요청 | 성공 | 오류 |
| --- | --- | --- | --- |
| `POST /workflow-runs/{id}/approvals` | `{ "node_execution_id": <uuid>, "note"?: <str> }` | `201 { approval_id, workflow_run_id, node_execution_id, approved_by, approved_at, note }` | `401`, `404 workflow_run_not_found`, `400 workflow_run_not_waiting_approval`·`node_execution_not_waiting`·`already_approved` |
| `GET /workflow-runs/{id}/approvals` | — | `200 { items: [...] }` | `401`, `404 workflow_run_not_found` |

**인증된 주체 누구나 승인할 수 있습니다.** `approved_by` 는 그 주체의 id 를 **기록**할 뿐 판정하지 않고, "요청자 본인은 승인할 수 없다" 같은 규칙도 없습니다. **이 공백은 의도된 것**이고 Trust Layer(Phase 8)의 자리입니다(spec 0005 2.6·C-4). 반쪽짜리 권한 모델을 지금 넣으면 이전 비용만 만듭니다.

거부 넷은 전부 **정확성** 가드입니다 — 선승인(아직 대기가 아님), 엉뚱한 지목(기다리는 대상이 아님), 재전송(이미 승인됨), 없는 Run. 지목 대상을 `control` 의 투영에서 읽는 이유는 api 역할이 `data` 를 볼 수 없기 때문이고(0001 R-7), 투영에 값이 없으면 **어떤 노드 실행도 인정하지 않습니다**(fail-closed).

승인 기록은 `control.workflow_approvals` 에 **append-only** 로 남고 노드 실행당 **한 건**입니다(DB unique). 기록 뒤 api 가 재큐하지만 **전진의 근거는 재큐가 아니라 저장된 승인**입니다 — 실행기가 그것을 읽고 판정합니다. 재큐가 유실되면 스위퍼가 승인된 대기를 주워 갑니다.

`GET /workflow-runs/{id}` 의 응답에 `waiting_node_execution_id` 가 있습니다(승인 호출에 필요한 포인터). 승인 **기록**은 그 응답에 넣지 않고 위의 목록 경로로 봅니다.

### 9.1 노드 출력과 분기 (P4-2b)

`AGENT` 노드의 출력은 `{"text": <자식 Run 의 마지막 assistant 본문>, "status": <자식의 종결 상태>}` 입니다. 상한은 **직렬화된 UTF-8 바이트** 기준 `AETHER_WORKFLOW_NODE_OUTPUT_MAX_BYTES`(기본 8192, 최소 64)이고, 넘기면 **본문만** 잘라 `output_truncated` 를 함께 참으로 적습니다 — 조용히 자르지 않습니다. 자르는 단위는 코드 포인트라 한 글자를 반으로 가르지 않습니다. `status` 는 판정에 쓰이므로 줄이지 않습니다. `START`·`END`·`CONDITION` 은 출력이 **없습니다**(`NULL`).

**출력은 `data.workflow_node_executions` 에만 있습니다.** 조회 API 도, span·감사·보고도 아닙니다(spec D-8·C-3). 읽는 곳은 지금 **`CONDITION` 하나**이고 그 사실을 구조 테스트(`tests/arch/test_workflow_output_stays_in_data.py`)가 AST 로 고정합니다 — 출력에서 파생된 값이 발행·통지·페이로드·로깅 호출의 인자로 들어가면 실패합니다. 조회 API 를 만들지 않은 이유는 **api 역할이 `data` 에 권한이 없기** 때문입니다(0001 R-7) — 투영이 필요하고 그것은 화면이 생기는 Phase 5 의 일입니다. 소비자가 하나뿐인 덕에 C-3 의 되돌리기가 쌉니다.

실패 사유 둘이 더 생겼습니다 — `condition_path_missing`(`exists` 가 아닌 연산자가 없는 경로를 가리킴)과 `condition_type_mismatch`(`gt`·`lt` 에 숫자가 아닌 값 등). **없는 경로는 조용한 거짓이 아닙니다** — `exists` 만 거짓이고 나머지는 실행이 실패합니다. 조용히 한쪽으로 가는 Workflow 는 디버깅할 수 없습니다.

### 9.1 파킹과 재개 (P4-2a)

`AGENT` 노드에 닿으면 실행기는 Version 을 해석하고(`control.agent_versions`, 핀이 없으면 최신) 자식 Run 의 **id 를 정해 노드 실행 행에 영속한 뒤** 선언을 요청하고, Workflow Run 을 `waiting_run` + `waiting_run_id` 로 **파킹**합니다. id 를 발사보다 **먼저** 영속하는 순서가 멱등의 축입니다 — 반대로 하면 재전달에서 자식 Run 이 둘이 됩니다(R-8).

**파킹은 lease 를 놓습니다**(`finally`). 대기 중인 Workflow Run 은 worker 슬롯을 점유하지 않고(R-7), `lease_owner`·`lease_until` 이 비어 있습니다.

깨우는 신호는 둘이고 **하는 일은 재큐 하나**입니다 — `aether:workflow_runs:requested` 에 다시 싣고, 판정은 실행기가 합니다.

| 경로 | 무엇 | 왜 |
| --- | --- | --- |
| 빠른 경로 | `aether:runs:status` 를 Workflow 전용 group `aether-workflow` 로 소비. 종결 상태가 오면 그 Run 을 기다리는 파킹 건을 찾아 재큐 | api 의 투영 group(`aether-api`)과 **다른 group** 이고 그 투영을 건드리지 않습니다 |
| 안전망 | **스위퍼** — `AETHER_WORKFLOW_SWEEP_INTERVAL_SECONDS`(기본 30)마다 "`waiting_run` 인데 자식이 이미 종결" 을 한 번의 SQL 로 주워 재큐. 시작할 때 1회 | **이벤트만 믿지 않습니다**(spec 0005 2.5). 신호 하나가 유실되면 Workflow 가 영원히 파킹됩니다 — 그 실패를 하네스에서 세 번 겪었습니다(`improvement-log/2026-10-11-001`) |

재큐가 두 번 와도 전진은 한 번입니다. 자식이 아직 종결이 아니면 실행기는 **아무 것도 바꾸지 않습니다** — 이벤트도, `seq` 도, 발사도 없습니다. 자식이 종결이면 노드를 마치고 다음으로 가며, 자식이 `succeeded` 가 아니면 Workflow Run 은 `failed` + `agent_run_failed` 입니다.

실패 사유 셋이 더 생겼습니다 — `agent_run_failed`, `agent_version_not_found`(노드가 가리킨 Agent Version 이 없음), `workflow_run_without_requester`(0007 이전에 만들어진 Run — 요청자를 모르면 자식을 띄우지 않습니다).

### 9.1 Workflow 이벤트 어휘

Workflow 는 **자기 어휘**를 가집니다(spec 0005 D-13) — Agent Run 의 이벤트 계약(5절)에 섞지 않습니다. 봉투는 같은 모양(`{ v: 1, workflow_run_id, seq, at, type, payload }`)이고 스트림은 `aether:workflow_runs:{id}:events`, 엔트리 ID 는 `<seq>-0` 입니다.

| type | payload |
| --- | --- |
| `workflow.status` | `status`, `current_node_id?`, `failure_reason?` |
| `node.started` | `node_id`, `kind`, `iteration` |
| `node.finished` | `node_id`, `iteration`, `status`(`running`·`succeeded`·`failed`) |
| `workflow.finished` | `status` — **항상 마지막** |

`approval.requested`·`approval.granted` 는 **P4-4 가 더했습니다** — payload 는 `node_id`·`iteration` 뿐이고 **승인 주체를 싣지 않습니다**(주체 id 를 이벤트 스트림에 넣지 않습니다. 기록은 `control` 에 있고 조회로 봅니다). `approval.granted` 를 내는 쪽은 **실행기**입니다 — 기록은 api 가 하지만 이벤트 어휘는 실행기의 것이고(D-13) 그 이벤트의 뜻은 "엔진이 승인을 관측했다" 입니다.

`seq` 는 Workflow Run 하나 안에서 1부터 단조 증가하고 **이벤트와 상태 통지가 같은 수열**을 씁니다(Agent Run 과 같은 규칙). 정본은 `data.workflow_run_executions.status_seq` 입니다. 비종결 이벤트는 저장한 뒤 발행하므로 재시작이 `seq` 를 **다시 쓰는 일은 없고 빈틈만** 생깁니다. 종결 한 쌍(`workflow.status` + `workflow.finished`)만 반대로 **발행이 먼저**입니다 — 종결 상태를 먼저 저장하면 그 사이에 죽었을 때 재전달이 "종결이면 아무것도 하지 않는다" 에 걸려 투영이 영영 `running` 으로 남습니다. 같은 `seq` 재발행은 어댑터가 성공으로 흡수하고 투영은 `seq` 로 멱등이므로, 중복이 아니라 **빈틈 없음**을 택한 선택입니다.

실패 사유는 셋입니다 — `unsupported_node_kind`(이 단위가 모르는 종류), `unsupported_branching`(나가는 간선이 둘 이상 — 조용히 하나를 고르지 않습니다), `invalid_graph`(START 가 없거나 `END` 아닌 노드에 나가는 간선이 없음 — 저장 때 검증이 막지만 실행기도 조용히 넘기지 않습니다).

**읽는 HTTP 경로는 아직 없습니다.** Agent Run 의 SSE(5절)에 대응하는 Workflow 쪽 경로는 Phase 5 의 화면과 함께 만듭니다 — 지금 만들면 소비자 없는 계약이 하나 늘어납니다.

**이 단위가 실행하는 노드는 `START`·`END` 둘뿐입니다.** 다른 종류를 만나면 Workflow Run 이 `failed` 가 되고 사유가 `unsupported_node_kind` 로 구별됩니다 — 절반만 만든 노드를 두지 않습니다. AGENT 노드와 파킹은 같은 단위의 두 번째 PR 입니다.

## 관련 문서

- [README.md](README.md) — 문서 지도
- [architecture.md](architecture.md) — AR-7(Control Plane 은 선언만), DP-1(API-first)
- [data-model.md](data-model.md) — 이 계약이 저장되는 테이블
- [../specs/0002-phase-1-agent-runtime.md](../specs/0002-phase-1-agent-runtime.md) — 결정의 정본
