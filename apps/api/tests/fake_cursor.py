"""fake 저장소의 커서 - 정렬된 목록의 정수 오프셋을 문자열로 감쌉니다(불투명 계약만 지킵니다).

깨진 커서는 PostgreSQL 어댑터와 같이 `InvalidCursor` 를 던집니다(spec 0006 2.3). 테스트 지원
코드이며 제품 코드가 아닙니다.
"""

from __future__ import annotations

from aether_api.domain.cursor import InvalidCursor


def offset_of(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        offset = int(cursor)
    except ValueError:
        raise InvalidCursor(cursor) from None
    if offset < 0:
        raise InvalidCursor(cursor)
    return offset
