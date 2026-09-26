"""spec 0003 2.4, D-9, 2.5, D-16: Gateway 유스케이스가 올리는 예외 셋.

이 모듈은 표준 라이브러리만 씁니다(AR-9). 세 예외는 판정(deny)·호출 실패·없는
도구의 세 경로에 각각 대응하고, 셋 모두 그 시도가 감사에 남은 **뒤** 올라갑니다
(spec 2.4 D-9, 2.5).
"""

from __future__ import annotations


class ToolCallDenied(Exception):
    """판정이 deny 를 돌려줘 MCP 클라이언트를 부르지 않은 경우(R-4)."""


class ToolCallFailed(Exception):
    """MCP 클라이언트 호출이 예외로 끝난 경우(연결 실패·타임아웃 포함). 원인 메시지는
    감사에만 남고 이 예외 메시지에는 담지 않습니다(spec 2.4)."""


class ToolNotFound(Exception):
    """`server_name` 에 `tool_name` 이 없거나 그 서버가 연결 실패로 제거된 경우
    (spec 2.5, D-16)."""
