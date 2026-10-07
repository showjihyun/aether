"""spec 0004 2.2: `aether_context` 자신의 도구 스키마 값 타입 — `aether_runtime
.application.ports.outbound.model_gateway.ToolSchema` 와 같은 모양이지만 AR-3
때문에 따로 둡니다(message.py 와 같은 이유)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextToolSchema:
    """모델에 알려줄 도구 하나의 스키마. 예산 초과 시 `description` 만 비워질 수
    있습니다(spec D-7) — `name`·`input_schema` 는 항상 유지합니다."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
