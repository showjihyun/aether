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
| `tools` | 중복 없음, 전부 내장 도구 이름(`clock`, `calculator`) 안 — 밖이면 `422` |
| `policy` | `timeout_seconds` 1~3600, `max_steps` 1~64, `model_retries`·`tool_retries` 0~10, `backoff.base_seconds` > 0, `max_seconds ≥ base_seconds` |

## 4. Run (P1-5b 에서 채움)

`POST /agents/{id}/run`, `GET /runs/{id}`, `POST /runs/{id}/cancel` — spec 0002 2.2. 이 절은 P1-5b 가 계약을 커밋할 때 채웁니다.

## 5. 이벤트 스트림

`GET /runs/{id}/events`(SSE) 는 P1-6 이 붙입니다. 이벤트 모델은 P1-4 가 `packages/runtime/src/aether_runtime/domain/events.py` 에 정했고, JSON Schema 파일(`packages/sdk/events.schema.json`)은 P1-6 이 커밋합니다(spec 0002 2.7, D-4).

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

## 6. Plane 사이의 스트림 계약 (P1-5a·5b 에서 채움)

`aether:runs:requested`, `aether:runs:status`, `aether:runs:{run_id}:events` — spec 0002 2.18.

## 관련 문서

- [README.md](README.md) — 문서 지도
- [architecture.md](architecture.md) — AR-7(Control Plane 은 선언만), DP-1(API-first)
- [data-model.md](data-model.md) — 이 계약이 저장되는 테이블
- [../specs/0002-phase-1-agent-runtime.md](../specs/0002-phase-1-agent-runtime.md) — 결정의 정본
