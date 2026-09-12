"""spec 0002 2.1, 2.8: `FailureReason` — Run 이 `failed` 로 끝난 이유.

`data.run_executions.failure_reason`, `control.runs.failure_reason`(투영), `run.status`
이벤트의 `failure_reason` 에 같은 문자열이 실립니다.
"""

from __future__ import annotations

from enum import StrEnum


class FailureReason(StrEnum):
    MODEL_ERROR = "model_error"
    TOOL_ERROR = "tool_error"
    MAX_STEPS_EXCEEDED = "max_steps_exceeded"
    UNKNOWN_TOOL = "unknown_tool"
    DEFINITION_INVALID = "definition_invalid"
    INTERNAL = "internal"
