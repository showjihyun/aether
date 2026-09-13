"""spec 0002 2.1, 2.7(개정 2): `EventSink` — Run 이벤트 발행.

계약: **같은 `seq` 의 재발행은 성공으로 취급**합니다(2.4 의 재개, R-16). Redis 어댑터는
explicit ID `<seq>-0` 를 top ID 이하로 XADD 할 때 Redis 가 내는
`ERR The ID specified in XADD is equal or smaller` 를 흡수해 이 계약을 지킵니다
(P1-5a) — fake 는 애초에 그런 거부가 없으므로 그대로 계약대로 성공합니다.
"""

from __future__ import annotations

from typing import Protocol

from aether_runtime.domain.events import RunEvent


class EventSink(Protocol):
    def publish(self, event: RunEvent) -> None: ...
