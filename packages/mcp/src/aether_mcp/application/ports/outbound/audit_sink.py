"""spec 0003 2.4, D-9: `AuditSink` outbound 포트.

Gateway 유스케이스(P2-2b)가 판정·호출 뒤 부르는 계약입니다. 세 결과(성공·실패·거부)
모두 이 포트를 통해 1건씩 기록됩니다. 기록 실패는 호출 결과를 바꾸지 않습니다(D-10)
— 그 결정은 이 포트를 부르는 쪽(Gateway)의 책임이고, 포트 자체는 실패를 그대로
전파합니다(호출자가 잡을지 말지 결정).
"""

from __future__ import annotations

from typing import Protocol

from aether_mcp.domain.audit import AuditRecord


class AuditSink(Protocol):
    def record(self, record: AuditRecord) -> None:
        """`record` 를 감사 저장소에 1건 남깁니다."""
        ...
