"""spec 0002 2.1, 2.8: `FailureReason` — Run 이 `failed` 로 끝난 이유.

`data.run_executions.failure_reason`, `control.runs.failure_reason`(투영), `run.status`
이벤트의 `failure_reason` 에 같은 문자열이 실립니다.
"""

from __future__ import annotations

from enum import StrEnum


class FailureReason(StrEnum):
    MODEL_ERROR = "model_error"
    TOOL_ERROR = "tool_error"
    TOOL_DENIED = "tool_denied"
    """spec 0003 R-4: `ToolGateway.call` 이 판정 거부(`ToolCallDenied`)를 올렸을 때
    — 재시도 없이 즉시 `failed`(판정은 결정적이므로 4xx 와 같은 취급)."""
    MAX_STEPS_EXCEEDED = "max_steps_exceeded"
    UNKNOWN_TOOL = "unknown_tool"
    DEFINITION_INVALID = "definition_invalid"
    INTERNAL = "internal"
