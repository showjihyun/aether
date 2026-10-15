"""spec 0005 2.6 개정 5 (3), C-4 (P4-4): 실행기가 읽는 **저장된 승인** 의 값 객체.

승인 기록의 정본은 `control.workflow_approvals` 이고 쓰는 쪽은 api 뿐입니다. 실행기는 그 표를
SELECT 로 읽어 "이 노드 실행에 승인이 저장돼 있는가" 만 확인합니다 - 전진의 근거는 저장된 사실이어야
하고 재큐 메시지여서는 안 됩니다(떠돌이 메시지 하나가 승인 없이 전진시키면 R-12 가 무너집니다).

**`approved_by` 를 담지 않습니다.** 실행기는 누가 승인했는지 모르고, 물을 필요도 없습니다. 승인자
권한 모델은 이 spec 이 만들지 않는 것이고(C-4, Phase 8 의 자리) 값 객체에 주체가 없으면 그 판정이
들어갈 자리도 없습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Approval:
    node_execution_id: UUID
    approved_at: datetime
