"""spec 0005 2.5 개정 3 (P4-2a B1): `WorkflowAgentRunRequest` — `aether:workflow:agent_runs:
requested` 로 들어오는 자식 Agent Run 선언 요청의 api 쪽 값 객체.

worker 는 `control.runs` 에 INSERT 할 수 없으므로(0001 GRANT) 실행기가 **자식 Run 의 id 를
정해** 이 스트림에 싣고, api 가 그 id 로 선언을 만듭니다. 스트림 필드가 계약의 정본입니다 —
worker 와 api 가 서로의 코드를 import 하지 않고 각자 구현합니다(`workflow_run_status_message`
와 같은 선).

| 필드 | 뜻 |
| --- | --- |
| `agent_run_id` | 실행기가 정한 자식 Run 의 id. 멱등의 축 |
| `agent_version_id` | 실행기가 `control.agent_versions` 에서 해석한 Version 의 id |
| `input` | 자식 Run 의 입력 문자열(`control.runs.input` 은 `text` NOT NULL) |
| `traceparent` | 없으면 빈 문자열(`RedisRunNotifier` 와 같은 규칙) |
| `requested_by` | Workflow 를 시작한 주체(`control.api_keys.id`). 자식 Run 이 그대로 물려받는다 --
비우면 `GET /runs/{id}` 가 500 이다. 비어 있으면(빈 문자열·없음) `None` |
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, field_validator


class WorkflowAgentRunRequest(BaseModel):
    """`aether:workflow:agent_runs:requested` 필드 — 소비자가 파싱한 값."""

    agent_run_id: UUID
    agent_version_id: UUID
    input: str
    traceparent: str = ""
    requested_by: UUID | None = None

    @field_validator("requested_by", mode="before")
    @classmethod
    def _empty_means_none(cls, value: object) -> object:
        return None if value == "" else value
