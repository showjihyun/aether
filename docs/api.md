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

## 6. Plane 사이의 스트림 계약

Redis Streams(spec 0001 D-10). 방향은 선언은 Control, 실행은 Data 이고 서로의 코드를 import 하지 않습니다(AR-7). 메시지는 선언이 아니라 통지입니다 — 내구적 선언은 `control.runs` 행이고 Redis 가 메시지를 잃어도 Run 은 남습니다(spec 0002 2.18, C-2).

| 스트림 | 방향 | 필드 | 소비 | ID |
| --- | --- | --- | --- | --- |
| `aether:runs:requested` | Control → Data | `run_id`, `agent_version_id`, `traceparent` | worker consumer group `aether-worker`, `count=1`. 시작 시 자기 PEL 먼저(`XREADGROUP … 0`), 그 뒤 `XAUTOCLAIM`(`min-idle` = `AETHER_WORKER_XAUTOCLAIM_MIN_IDLE_MS`, 기본 65분) → `XREADGROUP >`. 실행이 끝나야 `XACK`. 다른 worker 가 lease 를 쥐고 있으면 ack 하지 않음 | Redis 자동 |
| `aether:runs:status` | Data → Control | `StatusMessage`: `run_id`, `seq`, `status`, `at`, `started_at?`, `finished_at?`, `failure_reason?`, `trace_id?` (값 없는 선택 필드는 키 없음) | api consumer group `aether-api`(P1-5b) — `seq` 단조 증가로 멱등 투영 | Redis 자동 |
| `aether:runs:{run_id}:events` | Data → 독자 | `data` = 5절의 봉투 JSON | api SSE 리더(P1-6, 그룹 없음, `XREAD`) | **explicit `<seq>-0`**. 같은 ID 재-XADD(재개 시 재발행)는 어댑터가 성공으로 흡수. `MAXLEN ~ 10000`, `run.finished` 뒤 TTL 24시간 |

| `aether:knowledge:ingestions:requested` | Control → Data | `ingestion_id`, `knowledge_set_id`, `source`, `traceparent` | worker consumer group(적재 전용), `count=1`. Run 과 같은 패턴(자기 PEL → `XAUTOCLAIM` → `XREADGROUP >`). 성공·실패 **모두 ack** — 적재에는 lease 경합이 없습니다(한 적재는 한 worker 가 끝까지 처리) | Redis 자동 |
| `aether:knowledge:ingestions:status` | Data → Control | `ingestion_id`, `status`, `at`, `chunk_count?`, `failure_reason?` | api consumer group — `control.knowledge_ingestions` 에 투영 | Redis 자동 |

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

## 관련 문서

- [README.md](README.md) — 문서 지도
- [architecture.md](architecture.md) — AR-7(Control Plane 은 선언만), DP-1(API-first)
- [data-model.md](data-model.md) — 이 계약이 저장되는 테이블
- [../specs/0002-phase-1-agent-runtime.md](../specs/0002-phase-1-agent-runtime.md) — 결정의 정본
