# 데이터 모델 v1

이 문서는 PostgreSQL 스키마의 **열 단위 정본**입니다. 경계와 제약의 개요는
[../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) 2.8 이 정하고,
이 문서는 그 표를 열 단위로 확장합니다. 둘이 어긋나면 스키마·역할·GRANT 의 경계는
spec 2.8 이, 열의 세부(타입·기본값·제약 이름)는 이 문서가 정본입니다. 실체는
`apps/api/migrations/versions/0001_schemas_and_roles_grants.py` 코드입니다 — 이 문서가
그 코드와 갈라지면 코드가 이깁니다.

용어(`Agent`, `Agent Version`, `Run`)는 [domain.md](domain.md) 1절이 정의합니다. 여기서는
그 정의를 저장소로 어떻게 표현하는지만 다룹니다.

## 1. 스키마와 역할

| 스키마 | 소유(Plane) | 테이블 | 접근 역할과 권한 |
| --- | --- | --- | --- |
| `control` | Control Plane(`apps/api`) | `agents`, `agent_versions`, `api_keys`, `runs` | `aether_control`: `USAGE` + 테이블 전부 |
| `data` | Data Plane(`apps/worker`, `packages/runtime`) | `run_executions` | `aether_data`: `USAGE` + 테이블 전부, 그리고 `control` 스키마 `USAGE` + `control.agent_versions`·`control.runs` **SELECT 만** |

`aether_control` 은 `data` 스키마에 **아무 권한이 없습니다** — `USAGE` 조차 없습니다. `SELECT`
를 시도하면 relation 이 아니라 스키마 단계에서 `permission denied for schema data` 로
거부됩니다([../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) R-7,
`apps/api/tests/test_plane_roles.py`). `aether_data` 가 `control` 의 두 테이블을 읽는 것은
의도된 허용입니다 — Control Plane 이 **선언**하고(`control.runs`), Data Plane 이 그 선언을
읽어 **실행**합니다([../docs/architecture.md](architecture.md) 4절, AR-7).

역할 자체(`CREATE ROLE`)는 클러스터 수준이라 마이그레이션이 만들 수 없습니다.
`infra/docker/postgres/init/01-roles.sh` 가 두 역할만 만들고, 스키마·테이블·트리거·GRANT
는 `apps/api/migrations/versions/0001_schemas_and_roles_grants.py` 가 전부 소유합니다.
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

`Agent` 는 정의이지 실행이 아닙니다([domain.md](domain.md) 1절). `updated_at` 을 앱이 갱신하는
로직은 Phase 1 이 만듭니다 — Phase 0 은 열만 확보합니다.

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

이 테이블은 **선언**만 합니다 — "이 `Agent Version` 을 실행해 달라" 는 사건의 기록입니다.
Phase 1(P1-5)이 투영 열(`status`, `finished_at` 등, `data.run_executions` 로부터 복제)을
더해 `GET /runs/{id}` 가 `control.runs` 만 읽고도 답할 수 있게 합니다. Phase 0 에는 그
투영 열이 없습니다 — 지금 미리 만들지 않습니다.

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
바꿔야 할 cross-schema 참조가 이 FK **하나뿐**입니다 — `control.agents`, `control.agent_versions`,
`control.api_keys`, `control.runs` 는 전부 `control` 스키마 안에서만 참조하고, `data.run_executions`
가 유일하게 스키마 경계를 넘는 FK 를 가진 테이블입니다.

## 5. 접속 문자열과 마이그레이션 실행

`Settings.database_url`(env `AETHER_DATABASE_URL`, 기본값
`postgresql+psycopg://aether:aether@localhost:5432/aether`)이 기본 접속 문자열입니다.
`apps/api/migrations/env.py` 는 `ALEMBIC_URL` 환경변수가 있으면 그것을 우선하고, 없으면
`Settings().database_url` 을 씁니다 — testcontainers 통합 테스트는 컨테이너의 동적 포트를
`ALEMBIC_URL` 로 넘겨 씁니다(`apps/api/tests/conftest.py`).

마이그레이션은 관리자 역할로 실행합니다. 관리자 역할과 `aether_control`(api 의 런타임
역할)은 다릅니다 — 배포·구성은 Control Plane 의 책임이므로 두 스키마의 마이그레이션을
`apps/api` 가 소유하는 것이 계층과 맞습니다
([architecture.md](architecture.md) 4절).

## 관련 문서

- [../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) 2.8 — 경계·역할·GRANT 의 정본
- [architecture.md](architecture.md) — Control Plane / Data Plane 구분(4절), 의존 방향(3절)
- [domain.md](domain.md) — `Agent`, `Agent Version`, `Run` 의 뜻(1절)
- [README.md](README.md) — 문서 지도
