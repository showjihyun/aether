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
| `control` | Control Plane(`apps/api`) | `agents`, `agent_versions`, `api_keys`, `runs`, `tool_permissions` | `aether_control`: `USAGE` + 테이블 전부 |
| `data` | Data Plane(`apps/worker`, `packages/runtime`, `packages/mcp`) | `run_executions`, `run_states`, `tool_call_audit` | `aether_data`: `USAGE` + `run_executions`·`run_states` 전부, `tool_call_audit` 은 **`INSERT`·`SELECT` 만**(append-only). 그리고 `control` 스키마 `USAGE` + `control.agent_versions`·`control.runs`·`control.tool_permissions` **SELECT 만** |

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

## 3. 트리거

| 트리거 | 테이블 | 시점 | 동작 |
| --- | --- | --- | --- |
| `agent_versions_immutable` | `control.agent_versions` | `BEFORE UPDATE OR DELETE`, 행 단위 | `control.reject_agent_version_mutation()` 함수가 `RAISE EXCEPTION` |

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
