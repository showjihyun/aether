"""spec 0003 2.1, 2.4, 2.5, D-9, R-6: `ToolGateway` — runtime 이 도구를 부르는
**유일한** outbound 포트.

`ToolRegistry`(spec 0002, P1-4)를 대체합니다 — 도구는 더 이상 프로세스 내부
레지스트리가 아니라 `aether_mcp` 의 Gateway 유스케이스(`CallTool`)를 지납니다
(AR-6, AR-12). runtime 은 `aether_mcp` 의 **inbound 포트 타입만** 보는 어댑터
(`adapters/outbound/tool_gateway/mcp.py`)를 통해서만 이 포트를 구현합니다 — 이
포트 자체와 이 모듈의 예외는 `aether_mcp` 를 import 하지 않습니다(Executor 가
`aether_mcp` 를 몰라도 되게 하기 위해서).

세 예외는 `aether_mcp.domain.errors` 의 `ToolCallDenied`·`ToolCallFailed`·
`ToolNotFound` 와 같은 의미로, 어댑터가 변환해 다시 던집니다(spec 2.4, 2.5, D-16).
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from aether_runtime.application.ports.outbound.model_gateway import ToolSchema
from aether_runtime.domain.tools import ToolResult


class ToolCallDenied(Exception):
    """spec 2.4: 정책 판정이 deny 를 돌려줘 도구를 부르지 않은 경우(R-4)."""


class ToolCallFailed(Exception):
    """spec 2.4: Gateway 호출이 실패한 경우(연결 실패·타임아웃 포함). 원인은 감사에만
    남고 이 예외 메시지에는 담기지 않습니다."""


class ToolNotFound(Exception):
    """spec 2.5, D-16: 이름이 어느 바인딩된 서버에도 없거나 그 서버가 연결 실패로
    제거된 경우. 생성 시 정적 검증은 없으므로 이 예외가 Run 시점의 유일한 판정입니다."""


class ToolGateway(Protocol):
    """spec 2.1 도해의 `runtime → mcp` 경계. Executor 는 이 포트만 압니다."""

    def discover(self) -> tuple[ToolSchema, ...]:
        """Run 에 연결된 서버들이 내놓는 도구 스키마 전체(모델에 알려줄 것들)."""
        ...

    def call(
        self, run_id: UUID, agent_version_id: UUID, name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        """spec 2.4 의 판정 → 호출 → 감사 순서로 도구 하나를 부릅니다.

        거부는 `ToolCallDenied`, 없는 도구는 `ToolNotFound`, 그 밖의 실패는
        `ToolCallFailed` 를 올립니다.
        """
        ...
