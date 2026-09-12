"""spec 0002 2.1, 2.6, D-5: `Task` — 모델 호출 1회와 그에 딸린 도구 호출들.

단계(step)마다 하나씩 생기고, span 트리의 `task` 와 1:1 입니다(2.9).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aether_runtime.domain.tools import ToolCall


class Task(BaseModel):
    task_id: str
    step: int = Field(ge=0)
    tool_calls: list[ToolCall] = Field(default_factory=list)
