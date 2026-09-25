"""spec 0003 2.7, D-12, R-11: `AuditRecord` 는 인자·결과 본문과 자격증명을 담지 않습니다.

`domain.audit` 는 표준 라이브러리만 씁니다(AR-9) — `mcp` SDK 나 DB 라이브러리를
import 하지 않습니다.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from uuid import uuid4

from aether_mcp.domain.audit import AuditRecord

_FORBIDDEN_FIELD_NAMES = {
    "arguments",
    "result",
    "result_content",
    "content",
    "credentials",
    "credential",
    "env",
    "headers",
    "password",
    "token",
    "secret",
}


def test_audit_record_fields_do_not_include_bodies_or_credentials() -> None:
    field_names = {f.name for f in dataclasses.fields(AuditRecord)}
    assert field_names.isdisjoint(_FORBIDDEN_FIELD_NAMES)
    assert "result_bytes" in field_names
    assert "error_kind" in field_names


def test_audit_record_serialization_has_no_forbidden_keys() -> None:
    record = AuditRecord(
        run_id=uuid4(),
        agent_version_id=uuid4(),
        server_name="echo",
        tool_name="echo",
        decision="allow",
        outcome="ok",
        result_bytes=42,
        error_kind=None,
        started_at=datetime.now(UTC),
        duration_ms=7,
    )
    serialized = dataclasses.asdict(record)
    assert _FORBIDDEN_FIELD_NAMES.isdisjoint(serialized.keys())
    # 값 내용도 문자열로 새지 않는지(예: 실수로 결과를 문자열 필드에 욱여넣는 경우) 확인.
    assert all(not isinstance(v, str) or len(v) < 256 for v in serialized.values())
