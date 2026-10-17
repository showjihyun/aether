"""spec 0006 D-3: 목록 커서 - `(시각, id)` 를 `|` 로 이어 base64url 로 감싼 불투명 문자열.

`agent_repository.py` 의 커서와 같은 모양입니다(그 모듈은 바꾸지 않습니다, D-11). 정렬 키가
`(시각, id)` 오름차순이므로 다음 쪽은 `(시각, id) > (커서의 시각, 커서의 id)` 입니다.
"""

from __future__ import annotations

import base64
from datetime import datetime
from uuid import UUID

from aether_api.domain.cursor import InvalidCursor


def encode_cursor(at: datetime, row_id: UUID) -> str:
    raw = f"{at.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        at_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(at_str), UUID(id_str)
    except ValueError:  # base64·utf-8·형식·날짜·UUID 해독 실패는 모두 ValueError 계열
        raise InvalidCursor(cursor) from None
