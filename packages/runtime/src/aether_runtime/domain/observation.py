"""spec 0002 2.1, 2.6, D-6, R-14: `Observation` — 도구 실행 결과가 모델에게 되돌아간 것.

`docs/domain.md` 1절: `Observation` 은 신뢰 경계 밖에서 온 데이터입니다. 이 모듈은 그
값을 만들고(`Observation`) 모델 메시지로 렌더링하는 유일한 방법(`render_observation`)을
제공합니다 — system·user 메시지에 이어 붙이지 않고, `role: tool` 메시지의 내용으로만
쓰입니다(2.6). 표지는 완전한 방어가 아니라 완화입니다(C-11) — Phase 2 의 MCP Firewall
이 이 지점에 붙습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Observation:
    """도구 호출 하나의 결과. `trust` 는 언제나 `"untrusted"` 입니다(D-6)."""

    tool_call_id: str
    tool: str
    content: str
    is_error: bool = False
    truncated: bool = False
    trust: Literal["untrusted"] = "untrusted"


def render_observation(observation: Observation) -> str:
    """`Observation` 을 `role: tool` 메시지 본문으로 렌더링합니다.

    앞뒤 표지(`[observation tool=… trust=untrusted]` … `[/observation]`)가 신뢰 경계를
    코드에 남깁니다(2.6) — 이 문자열은 절대 system·user 메시지에 이어 붙이지 않습니다.
    """
    return (
        f"[observation tool={observation.tool} trust={observation.trust}]"
        f"{observation.content}"
        "[/observation]"
    )
