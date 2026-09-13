"""spec 0002 2.1, 2.4, D-11: `RunDeclarationReader` — `control.runs`·
`control.agent_versions.definition` 읽기. `aether_data` 의 SELECT 권한이 그 실체입니다.

**취소의 정본은 `control.runs.cancel_requested_at` 하나입니다**(D-11) — 유스케이스는
단계 시작마다 `declaration(run_id)` 를 다시 불러 그 열을 관측합니다. 취소 스트림은
없습니다.

`definition` 은 raw jsonb 를 그대로 돌려줍니다 — 검증(`AgentDefinition.model_validate`)
은 유스케이스의 일이고, 실패하면 `failed(definition_invalid)` 입니다(2.8).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel


class RunDeclaration(BaseModel):
    run_id: UUID
    agent_version_id: UUID
    input: str
    cancel_requested_at: datetime | None = None


class RunDeclarationReader(Protocol):
    def declaration(self, run_id: UUID) -> RunDeclaration | None: ...

    def definition(self, agent_version_id: UUID) -> dict[str, Any]: ...
