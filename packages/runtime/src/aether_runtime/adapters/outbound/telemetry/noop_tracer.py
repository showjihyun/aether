"""spec 0002 2.1, 2.9, AR-9 (P1-5a): `NoopTracer` — `Tracer` 포트의 프로덕션 no-op
구현. worker `main.py` 가 P1-8 전까지 조립에 씁니다(테스트는
`packages/runtime/tests/fakes.py` 의 `InMemoryTracer` 를 씁니다 — 그것은 부모–자식을
기록하지만 이것은 아무것도 기록하지 않습니다).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager


class NoopTracer:
    """span 을 기록하지 않고 본문만 실행합니다. `current_trace_id` 는 항상 `None`."""

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, str]) -> Iterator[None]:
        del name, attributes
        yield

    def current_trace_id(self) -> str | None:
        return None
