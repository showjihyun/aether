"""Server-Sent Events 줄 파서 (HTML SSE 스펙의 필요한 부분만)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class SseEvent:
    event: str
    data: str
    id: str | None = None


def parse_sse(lines: Iterable[bytes]) -> Iterator[SseEvent]:
    """바이트 줄(개행 포함 가능)을 이벤트로 바꿉니다. **줄이 오는 대로** 하나씩 내보냅니다.

    빈 줄이 이벤트 하나를 닫습니다. `:` 로 시작하는 줄(keep-alive 주석)은 무시합니다. `data:`
    가 여러 줄이면 개행으로 잇습니다. 스트림이 빈 줄 없이 끝나면 닫히지 않은 이벤트는
    버립니다(스펙).
    """
    event = "message"
    event_id: str | None = None
    data: list[str] = []
    for raw in lines:
        line = raw.decode("utf-8").rstrip("\r\n")
        if line == "":
            if data:
                yield SseEvent(event=event, data="\n".join(data), id=event_id)
            event, event_id, data = "message", None, []
            continue
        if line.startswith(":"):
            continue
        name, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if name == "event":
            event = value
        elif name == "data":
            data.append(value)
        elif name == "id":
            event_id = value
