# 데이터 모델 v1

이 문서는 PostgreSQL 스키마의 **열 단위 정본**입니다. 경계와 제약의 개요는
[../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) 2.8 이 정하고,
이 문서는 그 표를 열 단위로 확장합니다. 둘이 어긋나면 스키마·역할·GRANT 의 경계는
spec 2.8 이, 열의 세부(타입·기본값·제약 이름)는 이 문서가 정본입니다. 실체는
`apps/api/migrations/versions/0001_schemas_and_roles_grants.py`(Phase 0)와
`0002_phase1_runs_lease_states.py`(Phase 1, P1-2a) 코드입니다 — 이 문서가 그 코드와
갈라지면 코드가 이깁니다.

용어(`Agent`, `Agent Version`, `Run`)는 [domain.md](domain.md) 1절이 정의합니다. 여기서는
그 정의를 저장소로 어떻게 표현하는지만 다룹니다.

## 1. 스키마와 역할

| 스키마 | 소유(Plane) | 테이블 | 접근 역할과 권한 |
| --- | --- | --- | --- |
| `control` | Control Plane(`apps/api`) | `agents`, `agent_versions`, `api_keys`, `runs`, `tool_permissions`, `knowledge_sets`, `knowledge_ingestions` | `aether_control`: `USAGE` + 테이블 전부 |
| `data` | Data Plane(`apps/worker`, `packages/runtime`, `packages/mcp`, `packages/context`, `packages/memory`) | `run_executions`, `run_states`, `tool_call_audit`, `knowledge_chunks`, `agent_memory` | `aether_data`: `USAGE` + `run_executions`·`run_states` 전부, `tool_call_audit` 은 **`INSERT`·`SELECT` 만**(append-only). 그리고 `control` 스키마 `USAGE` + `control.agent_versions`·`control.runs`·`control.tool_permissions` **SELECT 만** |

`aether_control` 은 `data` 스키마에 **아무 권한이 없습니다** — `USAGE` 조차 없습니다. `SELECT`
를 시도하면 relation 이 아니라 스키마 단계에서 `permission denied for schema data` 로
거부됩니다([../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) R-7,
`apps/api/tests/test_plane_roles.py`). `aether_data` 가 `control` 의 세 테이블을 읽는 것은
의도된 허용입니다 — Control Plane 이 **선언**하고(`control.runs`), Data Plane 이 그 선언을
읽어 **실행**합니다([../docs/architecture.md](architecture.md) 4절, AR-7).

역할 자체(`CREATE ROLE`)는 클러스터 수준이라 마이그레이션이 만들 수 없습니다.
`infra/docker/postgres/init/01-roles.sh` 가 두 역할만 만들고, 스키마·테이블·트리거·GRANT
는 `apps/api/migrations/versions/0001_schemas_and_roles_grants.py` 가 전부 소유합니다(이후 표의 추가는 그 표를
만든 마이그레이션이 자기 GRANT 를 함께 소유합니다 — 0002, 0003).
마이그레이션은 관리자 역할로 실행합니다 — `aether_control`/`aether_data` 는 스키마를 만들
권한이 없습니다.

## 2. 테이블

### `control.agents`

| 열 | 타입 | 제약 |
| --- | --- | --- |
| `id` | `uuid` | PK, 기본값 `gen_random_uuid()` |
| `name` | `text` | `NOT NULL`, `UNIQUE`(`uq_agents_name`) |
| `created_at` | `timestamptz` | `NOT NULL`, 기본값 `now()` |
| `updated_at` | `timestamptz` | `NOT NULL`, 기본값 `now()` |
| `current_version` | `integer` | `NOT NULL`, 기본값 `1` — 마이그레이션 0002. `PUT /agents/{id}` 의 `SELECT … FOR UPDATE` 잠금 대상이자 조회의 정본(spec 0002 D-9) |

`Agent` 는 정의이지 실행이 아닙니다([domain.md](domain.md) 1절). `updated_at`·`current_version` 을 앱이
갱신하는 로직은 P1-1 이 만듭니다.

### `control.agent_versions`

| 열 | 타입 | 제약 |
| --- | --- | --- |
| `id` | `uuid` | PK, 기본값 `gen_random_uuid()` |
| `agent_id` | `uuid` | `NOT NULL`, FK → `control.agents.id` |
| `version` | `integer` | `NOT NULL` |
| `definition` | `jsonb` | `NOT NULL`, `CHECK (definition ? 'schema_version')`(`ck_agent_versions_definition_has_schema_version`) |
| `created_at` | `timestamptz` | `NOT NULL`, 기본값 `now()` |

추가 제약: `UNIQUE(agent_id, version)`(`uq_agent_versions_agent_id_version`). **`BEFORE UPDATE OR
DELETE` 트리거(`agent_versions_immutable`)가 모든 시도를 `RAISE EXCEPTION`(SQLSTATE
`P0001`)으로 거부합니다** — 불변은 앱의 예의가 아니라 DB 제약입니다. 이 트리거는 관리자
역할에도 적용됩니다: 권한이 있어도 거부되는 것이 증명이지, 권한이 없어 거부되는 것은
증명이 아닙니다([../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md)
R-8, `apps/api/tests/test_agent_version_immutable.py`).

`definition` 의 내부 형태는 Phase 1 이 정합니다. Phase 0 은 `schema_version` 키 하나만
top-level 존재를 요구합니다(`?` 는 jsonb 최상위 키 존재 연산자).

### `control.api_keys`

| 열 | 타입 | 제약 |
| --- | --- | --- |
| `id` | `uuid` | PK, 기본값 `gen_random_uuid()` |
| `label` | `text` | `NOT NULL` |
| `key_hash` | `text` | `NOT NULL`, `UNIQUE`(`uq_api_keys_key_hash`) |
| `created_at` | `timestamptz` | `NOT NULL`, 기본값 `now()` |
| `revoked_at` | `timestamptz` | `NULL` 허용 |

원문 키는 저장하지 않습니다 — `key_hash` 는 SHA-256 해시입니다(spec 2.9, P0-9 가 채웁니다).

### `control.runs`

| 열 | 타입 | 제약 |
| --- | --- | --- |
| `id` | `uuid` | PK, 기본값 `gen_random_uuid()` |
| `agent_version_id` | `uuid` | `NOT NULL`, FK → `control.agent_versions.id` |
| `requested_at` | `timestamptz` | `NOT NULL`, 기본값 `now()` |
| `requested_by` | `uuid` | `NULL` 허용, FK → `control.api_keys.id` |
| `input` | `text` | `NOT NULL`, 기본값 없음 — 마이그레이션 0002(행이 없는 시점이라 서버 기본값 `''` 을 잠깐 걸고 곧 제거). Run 의 사용자 입력, 선언의 일부 |
| `status` | `text` | `NOT NULL`, 기본값 `'queued'` — **투영 열**. enum 이 아닙니다: 정본 enum 은 `data` 스키마에 있고 전이 규칙은 `packages/runtime` 이 코드로 소유 |
| `status_seq` | `integer` | `NULL` 허용 — 마지막으로 적용한 `aether:runs:status` 메시지의 `seq`. 투영 멱등의 근거(spec 0002 D-2) |
| `started_at` | `timestamptz` | `NULL` 허용(투영) |
| `finished_at` | `timestamptz` | `NULL` 허용(투영) |
| `failure_reason` | `text` | `NULL` 허용(투영) |
| `trace_id` | `text` | `NULL` 허용(투영) |
| `cancel_requested_at` | `timestamptz` | `NULL` 허용 — 취소의 정본(spec 0002 D-11). worker 가 단계 사이에 읽습니다 |

이 테이블은 **선언**과 그 **투영**입니다 — "이 `Agent Version` 을 실행해 달라" 는 사건의 기록에,
`data.run_executions` 의 상태를 `aether:runs:status` 알림으로 복제한 열이 붙습니다(마이그레이션
0002, spec 0002 2.4·2.10). `GET /runs/{id}` 는 이 테이블만 읽습니다(spec 0001 D-11). 투영 열을
**쓰는** 쪽은 api(`aether_control`)뿐이고, worker 는 SELECT 만 합니다(기존 권한).

### `data.run_executions`

| 열 | 타입 | 제약 |
| --- | --- | --- |
| `id` | `uuid` | PK, 기본값 `gen_random_uuid()` |
| `run_id` | `uuid` | `NOT NULL`, `UNIQUE`(`uq_run_executions_run_id`), FK → `control.runs.id` |
| `status` | `data.run_execution_status`(enum) | `NOT NULL` |
| `started_at` | `timestamptz` | `NULL` 허용 |
| `finished_at` | `timestamptz` | `NULL` 허용 |
| `failure_reason` | `text` | `NULL` 허용 |
| `trace_id` | `text` | `NULL` 허용 |
| `lease_owner` | `text` | `NULL` 허용 — 마이그레이션 0002. 실행 권한 lease(spec 0002 D-10): 이 Run 을 지금 실행 중인 worker 의 consumer 이름 |
| `lease_until` | `timestamptz` | `NULL` 허용 — lease 만료 시각. `acquire_lease` 는 `lease_until IS NULL OR lease_until < now()` 인 행만 조건부 UPDATE 로 잡습니다(DB 시계 하나만) |

`status` enum 값: `queued`, `running`, `waiting`, `succeeded`, `failed`, `cancelled`,
`timed_out`. 전이 규칙(어떤 값에서 어떤 값으로 갈 수 있는가)은 `packages/runtime`(P1-2)이
코드로 소유합니다 — DB 는 값만 저장하고 전이를 검증하지 않습니다.

`started_at`/`finished_at` 은 spec 2.8 표에 `nullable` 표시가 없지만, 이 마이그레이션은
둘 다 nullable 로 만들었습니다. **불일치 기록**: 실행이 `queued` 로 시작하는 시점에는 아직
시작·종료 시각이 없고, 그 값을 채우는 것은 P1-2 의 상태 기계가 할 일이기 때문입니다. `run_id`
+ `status` 만으로 삽입 가능해야 한다는 완료 판정(`aether_data` 로 `data.run_executions`
INSERT 성공)과 상충하지 않으려면 `NOT NULL` 로 두고 삽입 시 기본값을 강제하는 것보다,
지금 값이 없다는 사실을 `NULL` 로 정직하게 표현하는 쪽을 택했습니다. Phase 1 에서 실제
전이 규칙이 정해지면 재검토합니다.

### `data.run_states`

| 열 | 타입 | 제약 |
| --- | --- | --- |
| `run_id` | `uuid` | PK, FK → `control.runs.id` |
| `state` | `jsonb` | `NOT NULL` — `RunState` 스냅숏(메시지 목록, 단계 번호, `Task` 목록, 마지막 이벤트 `seq`). 형태는 `packages/runtime` 의 `domain/run.py` 가 소유 |
| `updated_at` | `timestamptz` | `NOT NULL`, 기본값 `now()` |

`state` 의 형태(`aether_runtime.domain.run.RunState`, P1-2b — 이 표는 요약이고 정본은 그 pydantic 모델):

| 필드 | 타입 | 뜻 |
| --- | --- | --- |
| `run_id` | uuid(문자열) | `data.run_states.run_id` 와 같음 |
| `messages` | `[{role, content, tool_call_id?}]` | `role` ∈ system / user / assistant / tool. `tool_call_id` 는 tool 메시지에만 |
| `step` | int ≥ 0 | 진행한 단계 수 |
| `tasks` | `[{task_id, step, tool_calls: [{id, name, arguments}]}]` | 단계마다 하나(spec 0002 D-5) |
| `last_seq` | int ≥ 0 | 마지막으로 발행한 이벤트 `seq`(spec 0002 2.7). 재개 시 그 다음부터 발행 |
| `status` | `RunStatus` 값 | 스냅숏 안의 상태 표시 — 정본은 `data.run_executions.status` |
| `failure_reason` | `FailureReason` 값 또는 null | 종결 시 함께 저장(P1-4). 재개 시 재발행이 스냅숏만으로 `run.status` 를 다시 만들 수 있게 |
| `started_at`, `finished_at` | ISO 8601 또는 null | 같은 이유로 스냅숏에도 둠. `data.run_executions` 의 같은 열이 정본 |

마이그레이션 0002(P1-2a)가 만들었습니다. worker 가 단계마다 저장하고, 죽었다 살아난 worker 가 여기서
이어갑니다(spec 0002 2.4 재개). lease(`data.run_executions.lease_owner`·`lease_until`)의 판정은 어댑터의
조건부 UPDATE 한 문장(`lease_until IS NULL OR lease_until < now()`)이며 DB 시계만 씁니다(P1-2b). 접근 역할은 `aether_data` 만 전부 — `aether_control` 은 여전히 `data`
스키마에 권한이 없습니다(spec 0001 R-7 불변, `apps/api/tests/test_plane_roles.py` 의
`test_control_role_cannot_select_data_run_states`).

### `control.tool_permissions`

MCP 도구 호출의 **허용 목록**입니다(Phase 2, spec 0003 2.7·개정 4). 마이그레이션 0003(P2-2a·P2-4)이 만들었습니다.

| 열 | 타입 | 제약 |
| --- | --- | --- |
| `agent_version_id` | `uuid` | PK(복합), FK → `control.agent_versions.id` |
| `server_name` | `text` | PK(복합), `NOT NULL` |
| `tool_name` | `text` | PK(복합) |
| `decision` | `text` | `NOT NULL`, `CHECK (decision IN ('allow','deny'))` |
| `created_at` | `timestamptz` | `NOT NULL`, 기본값 `now()` |

PK 가 셋의 복합키인 이유는 MCP 에 **전역 도구 이름공간이 없다**는 것입니다 — 서버가 다르면 같은 이름의 도구가
겹칠 수 있고, `server_name` 이 키에 없으면 "Filesystem 의 `read` 는 허용, PostgreSQL 의 `read` 는 금지" 를
표현할 수 없습니다. 감사 표가 이미 `server_name` 을 담으므로 판정의 신분 기준도 같아야 합니다(spec 0003 개정 4).

**행이 없으면 deny 입니다.** 표는 명시된 행만 담고 기본값은 코드(`aether_policy` 의 `JudgeToolCallUseCase`)가
판정합니다. 도구 이름은 정확히 일치하며 정규화도 와일드카드도 없습니다(spec 0003 D-6). 쓰는 것은
`aether_control`(CLI `aether-api permissions allow|deny`, spec 0003 D-14)이고, `aether_data` 는 **SELECT 만**
합니다 — 판정이 worker 프로세스 안에서 일어나기 때문입니다(spec 0003 D-15,
`apps/api/tests/test_plane_roles.py::test_data_role_can_select_but_not_write_control_tool_permissions`).

### `data.tool_call_audit`

도구 호출 하나의 **감사 기록**입니다(Phase 2, spec 0003 2.7). 마이그레이션 0003(P2-2a)이 만들었습니다.

| 열 | 타입 | 제약 |
| --- | --- | --- |
| `id` | `uuid` | PK, 기본값 `gen_random_uuid()` |
| `run_id` | `uuid` | `NOT NULL`, FK → `control.runs.id` |
| `agent_version_id` | `uuid` | `NOT NULL`, FK → `control.agent_versions.id` |
| `server_name` | `text` | `NOT NULL` |
| `tool_name` | `text` | `NOT NULL` |
| `decision` | `text` | `NOT NULL`, `CHECK (decision IN ('allow','deny'))` |
| `outcome` | `text` | `NOT NULL`, `CHECK (outcome IN ('ok','error','denied'))` |
| `result_bytes` | `int` | `NOT NULL`, 기본값 `0` |
| `error_kind` | `text` | nullable |
| `started_at` | `timestamptz` | `NOT NULL` |
| `duration_ms` | `int` | `NOT NULL`, 기본값 `0` |

**인자와 결과의 본문은 담지 않습니다** — 크기와 종류만입니다(spec 0003 D-12). 자격증명도 들어가지
않습니다(R-11). 본문 검사·마스킹은 MCP Firewall·DLP 의 일이고 Phase 10 입니다.

**append-only 입니다.** `aether_data` 에 `INSERT`·`SELECT` 만 주고 `UPDATE`·`DELETE` 는 주지 않습니다
(spec 0003 개정 3) — 기록을 쓰는 주체가 자기 기록을 지울 수 있으면 사후 추적이 성립하지 않습니다.
`control.agent_versions` 의 불변 트리거와 같은 취급이며, 여기서는 트리거가 아니라 GRANT 로 막습니다
(`apps/api/tests/test_plane_roles.py::test_data_role_cannot_update_or_delete_tool_call_audit`).
`aether_control` 은 이 표에 여전히 아무 권한이 없습니다.

조회 경로(API·대시보드)와 보존 정책은 이번 Phase 에 없습니다 — Phase 9 입니다(spec 0003 D-3).

### `control.knowledge_sets` · `control.knowledge_ingestions`

Phase 3 의 선언 두 표입니다(spec 0004 2.8, P3-2a). `knowledge_sets` 는 Agent 가 바인딩하는
집합의 이름이고, `knowledge_ingestions` 는 적재의 **선언과 상태**입니다 — `control.runs` 와 같은
모양입니다(api 가 선언하고 worker 가 실행합니다, spec 0004 D-4). 쓰는 것은 `aether_control`
이고 `aether_data` 는 **SELECT 만** 합니다(worker 가 이름·상태를 읽어야 합니다).

### `data.knowledge_chunks` · `data.agent_memory`

실행 부산물 두 표입니다. 둘은 **별도 표·별도 인덱스**를 씁니다 —
[domain.md](domain.md) 3절이 `Memory` 와 `Knowledge` 를 한 저장소에 섞지 말라고 정했고,
섞이면 검증되지 않은 경험이 사실로 승격됩니다(spec 0004 R-10).

| 표 | 담는 것 |
| --- | --- |
| `knowledge_chunks` | 청크 본문, `embedding vector(N)`, `embed_model_id`, `embed_dim`, 출처(`source_path`·`chunk_index`) |
| `agent_memory` | Run 이 남긴 경험. 읽을 때 "검증 전" 표지가 붙어 Context 에 들어갑니다 |

둘 다 코사인 거리 HNSW 인덱스를 각자 갖습니다(spec 0004 D-2). `aether_data` 가 읽고 쓰며
`aether_control` 은 `data` 스키마에 여전히 아무 권한이 없습니다.

**벡터 차원은 `AETHER_EMBED_DIM`(기본 768)입니다** — worker 와 마이그레이션이 같은 변수를
읽습니다. 차원이 어긋난 벡터를 넣으면 PostgreSQL 이 `expected N dimensions, not M` 으로
거부합니다(타입 자체가 1차 방어선). 모델이 바뀌면 기존 벡터는 무효이므로 청크와 함께
`embed_model_id` 를 저장하고, 검색 시점에 **재적재를 요구하는 오류**로 드러냅니다(spec 0004 D-9,
그 애플리케이션 로직은 P3-2b).

**임베딩 모델은 채팅 모델과 별도로 핀합니다** — `AETHER_EMBED_MODEL_ID`(기본
`nomic-embed-text`). 그 전까지 어댑터는 채팅 모델 id 를 `/embeddings` 로 보냈고 그대로면 적재가
실패합니다(spec 0004 D-3 이 spec 0002 2.5 를 [실질] 개정).

**`agent_memory` 는 Agent 단위입니다**(P3-4). `memory_enabled` 인 Agent 의 Run 이 `succeeded`
로 종결한 뒤 Executor 가 넘긴 **마지막 assistant 본문 한 건**이 임베딩(`embed_model_id`·
`embed_dim` 포함)과 함께 적힙니다 — 요약하거나 쪼개지 않습니다(spec 0004 2.6). `run_id` 는
어느 Run 이 남겼는가이고, Run 없이 쓰인 기억에는 `NULL` 입니다.

읽을 때는 **같은 Agent·같은 임베딩 모델**의 행만 코사인 거리로 비교하고, 동점은
`created_at DESC, id ASC` 로 깨서 결정적입니다(R-1). 다른 모델로 만든 행은 **조용히
제외합니다** — 위의 Knowledge 와 다른 점입니다. Knowledge 는 조직이 소유한 사실이라
재적재를 요구하는 오류로 드러내지만, 기억은 실행 부산물이라 사람에게 요구할 것이 없습니다.

### `control.workflows` · `control.workflow_versions` · `control.workflow_runs` · `control.workflow_approvals`

Phase 4 의 Control Plane 네 표입니다(spec 0005 2.9, P4-1). 평면을 가른 규칙은 **쓰는 주체**입니다 — 정의·Version·Run 투영·**승인 기록**은 api 가 쓰므로 `control` 이고, 노드 실행 기록은 worker 가 쓰므로 `data` 입니다(spec 0005 D-5, 마이그레이션 0001 의 역할·GRANT 가 정한 규칙).

| 표 | 담는 것 | 불변성 |
| --- | --- | --- |
| `workflows` | 이름과 `current_version` | 가변 |
| `workflow_versions` | `nodes`·`edges`(jsonb), `unique(workflow_id, version)` | **트리거로 불변** |
| `workflow_runs` | 선언(`workflow_version_id`·`input`·`requested_at`·`requested_by`)과 **투영**(`status`·`status_seq`·`current_node_id`·`waiting_run_id`·`waiting_node_execution_id`·시각 열) | 가변 |
| `workflow_approvals` | `workflow_run_id`·`node_execution_id`·`approved_by`·`approved_at`·`note`, `unique(workflow_run_id, node_execution_id)`(0008 — 승인은 노드 실행당 한 건) | **트리거로 append-only** |

**상태 enum 은 새로 만들었습니다** — `control.workflow_run_status` 의 일곱 값이고 `data.run_execution_status`(0001)는 건드리지 않았습니다(spec 0005 D-1·D-2). `timed_out` 은 없습니다 — Phase 4 는 Workflow 전체 타임아웃을 만들지 않고, 자식 Agent Run 의 타임아웃은 그 Run 의 것이며 Workflow 는 그것을 `failed` 로 받습니다.

`aether_data` 는 `workflow_versions`·`workflow_runs`·**`workflow_approvals`** 에 **SELECT 만** 가집니다. 앞의 둘은 worker 가 실행할 그래프와 Run 선언을 읽기 위한 것이고, `workflow_approvals` 의 SELECT 는 **마이그레이션 0008 이 더했습니다**(P4-4, 사람 검토 H-1) — 실행기는 전진의 근거를 **저장된 사실**에서 읽어야 하고 재큐 메시지를 근거로 삼으면 떠돌이 메시지 하나가 승인 없이 전진시킵니다(spec 0005 개정 5). `workflows` 에는 **아무 권한이 없습니다** — worker 는 이름을 읽을 이유가 없습니다. `workflow_approvals` 는 승인을 **기록**만 하고 권한 판정은 하지 않습니다(spec 0005 D-6, 그 공백은 Phase 8).

`workflow_approvals.node_execution_id` 에는 **FK 를 두지 않았습니다** — `control` 에서 `data` 로의 참조는 평면 경계를 거스릅니다. 지목한 실행이 실제로 `waiting_approval` 인지는 **P4-4 의 애플리케이션 판정**입니다(spec 0005 R-12).

### `data.workflow_run_executions`

Workflow Run 의 **실행 상태와 lease** 입니다(마이그레이션 0006, spec 0005 2.9 **개정 2**, P4-2a). `workflow_run_id` 가 PK 이고 `control.workflow_runs.id` 를 참조합니다. `data.run_executions`(Agent Run)와 같은 자리·같은 모양입니다.

| 열 | 뜻 |
| --- | --- |
| `status` | `control.workflow_run_status` — **0005 의 enum 을 그대로** 씁니다. 같은 값 집합을 두 타입으로 복제하면 한쪽에만 값이 늘어 어긋납니다. `aether_data` 는 스키마 `control` 에 USAGE 가 있어 그 타입을 쓸 수 있습니다(0001) |
| `status_seq` | 이 Run 의 상태 수열. 이벤트의 `seq` 와 **같은 수열**이고 투영의 멱등 기준입니다 |
| `current_node_id`·`waiting_run_id` | 어디까지 왔는가 / 무엇을 기다리는가 |
| `lease_owner`·`lease_until` | 실행 권한. 조건부 UPDATE 한 문장과 **DB 시계**로 경합을 판정합니다(`data.run_executions` 와 같은 방식) |
| `started_at`·`finished_at`·`failure_reason`·`updated_at` | 시각과 사유 |

**왜 `control.workflow_runs` 가 아닌가.** 실행기는 worker 이고 worker 의 역할(`aether_data`)은 `control` 에 **SELECT 뿐**입니다(0001·0005 의 GRANT). GRANT 를 넓히면 평면 규칙(spec 0005 D-5)이 무너지고 그것은 권한 변경이라 사람 검토 대상입니다. 그래서 상태는 여기(`data`)에 쓰고 `control` 쪽은 `aether:workflow_runs:status` 스트림으로 api 가 투영합니다 — `data.run_executions` → `aether:runs:status` → `control.runs` 와 같은 선이고, Knowledge 적재도 같습니다([api.md](api.md) 6절).

`aether_control` 에는 이 표에 **아무 권한도 주지 않았습니다**(0001 R-7 유지 — `data` 스키마 USAGE 자체가 없습니다).

### `data.workflow_node_executions`

노드 실행 하나가 한 행입니다. `unique(workflow_run_id, node_id, iteration)` 이 **같은 노드가 두 번 전진하는 것을 DB 에서** 막습니다 — `iteration` 은 `LOOP` 가 쓰는 회차이고, 멱등 재개(spec 0005 R-8)의 마지막 방어선입니다.

자식 Agent Run 과의 연결은 **이 표의** `agent_run_id` 입니다(spec 0005 D-3). Run 쪽에 "이 Run 은 어느 Workflow 노드의 것" 을 두면 `aether_runtime` 이 workflow 를 알아야 하고 그것이 AR-13 위반입니다. cross-schema FK 의 수명은 4절과 같습니다.

`output`(jsonb)과 `output_truncated` 는 **P4-2b 가 씁니다**(2026-10-15 적용). 상한은 **직렬화된 UTF-8 바이트** 기준이고 애플리케이션이 지킵니다 — 잘렸다는 사실을 `output_truncated` 로 남깁니다(spec 0005 D-8). 출력은 이 표에만 있고 **span·감사·보고에는 넣지 않습니다**. `status` 를 enum 이 아니라 text 로 둔 것은 노드 실행 상태의 집합이 spec 에 없기 때문입니다. 집합은 P4-2a 의 실행기가 정했습니다(`aether_workflow.domain.node_execution.NodeExecutionStatus`) — 컬럼을 enum 으로 좁히는 것은 파킹이 `waiting_run` 을 더하는 **같은 단위의 두 번째 PR** 로 미룹니다(마이그레이션 하나로 끝내기 위해서입니다).

### 마이그레이션 0008 — 승인 경로

P4-4 가 요구한 넷입니다. **네 번째 줄이 사람 검토 항목(H-1)** 입니다.

| 변경 | 내용 |
| --- | --- |
| `control.workflow_runs.waiting_node_execution_id` | uuid NULL, **FK 없음**(평면을 넘는 포인터 — 0007 의 두 열과 같은 근거). api 가 R-12 의 4xx 를 내려면 "지금 어느 노드 실행을 기다리는가" 가 `control` 안에 있어야 합니다. `waiting_approval` 일 때만 값이 있습니다(상태에서 유도) |
| `data.workflow_run_executions.waiting_node_execution_id` | 같은 열의 **정본** 쪽(worker 가 씁니다) |
| `data.workflow_node_execution_status` | `waiting_approval` 추가 — 다섯 값(`running`·`waiting_run`·`waiting_approval`·`succeeded`·`failed`) |
| **`GRANT SELECT ON control.workflow_approvals TO aether_data`** | 실행기가 승인을 **저장된 사실**로 확인합니다. 0005 가 "승인 경로가 필요로 하면 그때 검토를 거쳐 더한다" 고 비워 둔 자리이고, **읽기 하나뿐**입니다(쓰기는 여전히 api 만). 열 단위 GRANT 로 더 좁히는 선택지는 마이그레이션 docstring 에 남겼습니다 |

### 마이그레이션 0007 — 요청자·노드 상태 enum·FK 둘

P4-2a 의 파킹이 요구한 셋입니다.

| 변경 | 내용 |
| --- | --- |
| `control.workflow_runs.requested_by` | uuid NULL, FK `control.api_keys(id)`. 자식 Agent Run 이 **그대로 물려받습니다** — 비우면 `GET /runs/{id}` 가 500 입니다(`RunView` 가 값을 필수로 요구). 사람 주체를 발명하지 않고 Workflow 를 시작한 주체를 넘깁니다 |
| `data.workflow_node_executions.status` | `text` → enum `data.workflow_node_execution_status`(`running`·`waiting_run`·`succeeded`·`failed`, 0008 이 `waiting_approval` 을 더해 다섯). `data.run_execution_status`(0001)와 **다른 타입**입니다 — Agent Run 의 `queued`·`timed_out` 은 노드 실행에 없습니다. 0005 가 열어 둔 자리를 실행기가 집합을 정한 뒤 좁혔습니다 |
| **FK 둘 제거** | `data.workflow_node_executions.agent_run_id` 와 `control.workflow_runs.waiting_run_id` 가 가리킨 `control.runs(id)` |

**FK 를 푼 이유**(리뷰 대상). 파킹의 순서는 ① 자식 Run 의 id 를 정해 **영속** ② api 에 선언 요청 ③ 파킹 통지입니다. ①을 ② 뒤로 미룰 수 없습니다 — 그러면 재전달에서 id 를 다시 만들어 자식 Run 이 둘이 됩니다(spec 0005 R-8). 그런데 ① 시점에는 `control.runs` 행이 아직 없어 FK 가 거부합니다. `waiting_run_id` 는 같은 경쟁입니다 — 파킹 통지와 자식 선언을 **서로 다른 api 소비자**가 받으므로 투영이 선언보다 먼저 적용될 수 있고, 그때 FK 위반은 투영 스레드를 죽입니다. 이 열들은 "무엇을 기다리는가" 를 가리키는 포인터이고, 무결성의 보증은 FK 가 아니라 **id 를 한 곳(실행기)에서 정해 멱등 선언하는 구조**가 맡습니다. `data.workflow_run_executions.waiting_run_id`(0006)가 처음부터 FK 없이 열린 것과 같은 근거이고, 4절의 cross-schema FK 수명 논의와도 같은 방향입니다.

### 마이그레이션 0009 — 시각 대기(`WAIT`)

| 대상 | 변경 |
| --- | --- |
| `control.workflow_run_status` | **`waiting_timer`** 추가 — 여덟 값 |
| `data.workflow_node_execution_status` | **`waiting_timer`** 추가 — 여섯 값 |
| `data.workflow_run_executions.wake_at` | `timestamptz NULL` — **정본**. `waiting_timer` 일 때만 값이 있습니다 |
| `control.workflow_runs.wake_at` | 같은 열의 **투영** |
| GRANT | **변경 없음** |

`downgrade()` 는 enum 값을 지울 수 없으므로 **타입을 새로 만들어 바꿔 끼웁니다**(0008 이 노드 상태에서 한 것과 같은 모양). `waiting_timer` 행은 `running` 으로 둡니다.

**왜 상태가 하나 더 필요한가.** `WAIT` 가 실제 시간을 블록하면 그것이 D-4 가 금지한 **슬롯 점유**입니다. 파킹하려면 "무엇을 기다리는가" 가 상태로 구별돼야 하고(D-2 의 규칙), 자식 Run·승인과 달리 **깨우는 외부 사건이 없으므로** 스위퍼의 `wake_at <= now()` 가지가 주 경로입니다.

### 마이그레이션 0010 — 감사의 `run_kind`

| 변경 | 내용 |
| --- | --- |
| `data.tool_call_audit.run_id` 의 FK | `tool_call_audit_run_id_fkey`(`control.runs`)를 **제거**. 열은 `NOT NULL` 그대로 |
| `data.tool_call_audit.run_kind` | `text NOT NULL DEFAULT 'agent'`, `CHECK (run_kind IN ('agent','workflow'))` |
| GRANT·Policy | **변경 없음** |

**왜.** Workflow 의 `TOOL`·`MCP` 노드가 부른 도구 호출은 `run_id` 가 **Workflow Run** 입니다. FK 가 `control.runs` 를 가리키는 한 그 행은 들어갈 수 없고, `CallToolUseCase` 는 감사 쓰기 실패를 **삼키므로**(spec 0003 D-10) 호출은 성공하고 **감사만 조용히 사라집니다**. 두 평면의 Run 을 한 열이 가리키는 것은 FK 로 표현할 수 없으므로 0007 과 같은 근거로 FK 를 풀고, 대신 `run_kind` 가 출처를 말합니다. **대가**: 감사 행의 참조 무결성을 DB 가 아니라 애플리케이션이 책임집니다. `downgrade()` 는 FK 를 되돌리려고 `run_kind='workflow'` 행을 **삭제합니다** — 되돌리기는 감사 기록을 잃습니다.

### PostgreSQL 이미지

Phase 3 부터 `pgvector/pgvector:pg16`(다이제스트 핀)입니다. 이전은 `postgres:16-alpine` 이었고,
교체로 이미지가 111 MiB → 152 MiB(+37%)가 되었습니다. `infra/docker/postgres/init/01-roles.sh` 는
그대로 씁니다 — 그 이미지에도 bash·psql 이 있고, 전용 회귀 테스트가 실제 이미지로 그것을
확인합니다(`apps/api/tests/test_roles_script_runs.py`).

## 3. 트리거

| 트리거 | 테이블 | 시점 | 동작 |
| --- | --- | --- | --- |
| `agent_versions_immutable` | `control.agent_versions` | `BEFORE UPDATE OR DELETE`, 행 단위 | `control.reject_agent_version_mutation()` 함수가 `RAISE EXCEPTION` |
| `workflow_versions_immutable` | `control.workflow_versions` | `BEFORE UPDATE OR DELETE`, 행 단위 | `control.reject_workflow_versions_mutation()` — Version 불변(spec 0005 D-12)을 앱이 아니라 DB 가 지킵니다 |
| `workflow_approvals_immutable` | `control.workflow_approvals` | `BEFORE UPDATE OR DELETE`, 행 단위 | `control.reject_workflow_approvals_mutation()` — 승인 기록은 append-only 입니다(spec 0005 2.6) |

## 4. cross-schema FK 의 수명 (spec C-8)

`data.run_executions.run_id → control.runs.id` 는 **한 PostgreSQL 인스턴스 안에서만**
성립하는 진짜 외래키입니다. 지금(Modular Monolith, DP-5)은 두 스키마가 같은 DB 에 있어서
FK 로 무결성을 얻습니다.

On-Prem 배포에서 두 Plane 이 실제로 분리되어 서로 다른 데이터센터·다른 DB 에 놓이면 이 FK
는 물리적으로 성립할 수 없습니다(PostgreSQL 은 cross-database FK 를 지원하지 않습니다).
그 전환이 오면 `run_id` 를 **soft reference**(FK 제약 없는 평범한 `uuid` 열, 참조 무결성은
애플리케이션과 Run 흐름의 통지(`aether:runs:*` 스트림)가 책임)로 바꿉니다.

D-11(Run 은 Plane 마다 기록이 하나씩)이 이 저장소 설계의 근거이고, 그 덕에 Plane 분리 시
바꿔야 할 cross-schema 참조는 **둘**뿐입니다 — `data.run_executions.run_id` 와 마이그레이션 0002 가
더한 `data.run_states.run_id`(둘 다 → `control.runs.id`). `control.agents`, `control.agent_versions`,
`control.api_keys`, `control.runs` 는 전부 `control` 스키마 안에서만 참조합니다.

## 5. 접속 문자열과 마이그레이션 실행

`Settings.database_url`(env `AETHER_DATABASE_URL`, 기본값
`postgresql+psycopg://aether:aether@localhost:5432/aether`)이 기본 접속 문자열입니다.
`apps/api/migrations/env.py` 는 `ALEMBIC_URL` 환경변수가 있으면 그것을 우선하고, 없으면
`Settings().database_url` 을 씁니다 — testcontainers 통합 테스트는 컨테이너의 동적 포트를
`ALEMBIC_URL` 로 넘겨 씁니다(`tests/support/pg.py` — P1-2a 에서 `apps/api/tests/conftest.py` 의
fixture 를 옮겨 세 앱이 공유. 루트 `conftest.py` 가 `pytest_plugins` 로 등록).

마이그레이션은 관리자 역할로 실행합니다. 관리자 역할과 `aether_control`(api 의 런타임
역할)은 다릅니다 — 배포·구성은 Control Plane 의 책임이므로 두 스키마의 마이그레이션을
`apps/api` 가 소유하는 것이 계층과 맞습니다
([architecture.md](architecture.md) 4절).

## 관련 문서

- [../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) 2.8 — 경계·역할·GRANT 의 정본
- [architecture.md](architecture.md) — Control Plane / Data Plane 구분(4절), 의존 방향(3절)
- [domain.md](domain.md) — `Agent`, `Agent Version`, `Run` 의 뜻(1절)
- [README.md](README.md) — 문서 지도
