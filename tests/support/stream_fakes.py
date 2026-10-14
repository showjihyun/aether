"""소비자 단위 테스트용 스트림 fake — `tests/support/` 에 **한 벌만** 둡니다.

`tests/arch/test_fake_duplication.py` 가 같은 이름의 fake 가 `tests/support/` 밖에서 둘
이상 정의되는 것을 막습니다(근거: `improvement-log/2026-09-28-001` — 같은 포트의 fake 가
갈라지면 한쪽만 고쳐지고 다른 쪽이 조용히 낡습니다). api 의 투영 소비자와 자식 Run 선언
소비자가 같은 모양(`XREADGROUP` → `XACK`)을 쓰므로 그 fake 는 여기 있습니다.
"""

from __future__ import annotations

from collections.abc import Mapping
from threading import Event
from typing import Any

StreamEntry = tuple[str, dict[str, str]]


class FakeStreamClient:
    """`XREADGROUP`·`XACK` 만 흉내 내는 최소 fake. 새 메시지가 바닥나면 `stop` 을 set 해서
    `run_until` 이 스스로 끝나게 합니다(sleep 없이)."""

    def __init__(self, stop: Event, *, pending: list[StreamEntry], new: list[StreamEntry]) -> None:
        self._stop = stop
        self._pending = list(pending)
        self._new = list(new)
        self.acked: list[str] = []
        self.group_args: list[tuple[str, str, str]] = []

    def xreadgroup(
        self,
        *,
        groupname: str,
        consumername: str,
        streams: Mapping[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> Any:
        del count, block
        (stream, start) = next(iter(streams.items()))
        self.group_args.append((groupname, consumername, start))
        source = self._pending if start == "0" else self._new
        if source:
            return [(stream, [source.pop(0)])]
        if start != "0":
            self._stop.set()
        return []

    def xack(self, stream: str, group: str, message_id: str) -> int:
        del stream, group
        self.acked.append(message_id)
        return 1
