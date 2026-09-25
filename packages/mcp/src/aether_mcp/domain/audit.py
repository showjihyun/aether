"""spec 0003 2.7, D-9, D-12, R-11: 감사 레코드 — 호출의 **결과**만 담습니다.

인자·결과 **본문은 넣지 않습니다** — 크기(`result_bytes`)와 종류(`error_kind`)만
남깁니다(D-12). 자격증명은 애초에 이 타입에 들어올 필드가 없습니다(R-11).

`data.tool_call_audit` 의 열과 1:1 대응합니다(spec 2.7) — `id` 는 DB 가
`gen_random_uuid()` 로 채우므로 여기 없습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

Decision = Literal["allow", "deny"]
Outcome = Literal["ok", "error", "denied"]


@dataclass(frozen=True)
class AuditRecord:
    """호출 1회의 감사 레코드. 성공·실패·거부 세 경우 모두 이 타입 하나로 남습니다."""

    run_id: UUID
    agent_version_id: UUID
    server_name: str
    tool_name: str
    decision: Decision
    outcome: Outcome
    result_bytes: int
    error_kind: str | None
    started_at: datetime
    duration_ms: int
