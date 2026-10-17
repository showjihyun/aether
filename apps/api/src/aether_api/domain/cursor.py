"""spec 0006 2.3: 목록 `cursor` 가 해독되지 않을 때의 도메인 예외.

커서는 클라이언트가 돌려보내는 입력이므로 깨진 값은 서버 오류가 아니라 요청 오류입니다 -
HTTP 어댑터가 422 로 바꿉니다(여섯 목록 경로 공통).
"""

from __future__ import annotations


class InvalidCursor(Exception):
    """`cursor` 가 이 서버가 만든 형식이 아닙니다."""
