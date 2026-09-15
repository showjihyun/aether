"""spec 0002 2.7, 2.18, D-4, R-3: `RunEventReader` 포트의 `redis.asyncio` 구현.

**동기 `redis.Redis` 를 쓰지 않습니다** — 동기 클라이언트로 블록 `XREAD` 를 돌리면
스레드풀 스레드 하나를 점유한 채 멈추고, 클라이언트가 끊겨도 그 스레드를 취소할
방법이 없습니다(R-3, C-4). `redis.asyncio.Redis` 는 소켓 I/O 를 이벤트 루프에
맡기므로 바깥의 `asyncio.Task.cancel()` 이 블록된 `XREAD` 대기를 즉시 풀어 줍니다
(확인함 — 취소 요청 후 0초 안에 `CancelledError` 로 돌아옵니다).

`aether:runs:{run_id}:events` 는 consumer group 없이 여러 독자가 `XREAD` 로
읽습니다(2.7) — worker 의 `RequestedConsumer`/api 의 `StatusConsumer` 와 달리
`XREADGROUP`/`XACK` 가 없습니다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import redis.asyncio as redis
from aether_runtime.domain.events import RunEvent


def _stream_key(run_id: UUID) -> str:
    return f"aether:runs:{run_id}:events"


class RedisRunEventReader:
    """`RunEventReader` 포트의 `redis.asyncio` 구현(spec 0002 2.7).

    `client` 는 `decode_responses=True` 로 만들어져야 합니다 — 필드 값을 `str`
    로 받아 `RunEvent.model_validate_json` 에 그대로 넘깁니다.
    """

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    async def stream_exists(self, run_id: UUID) -> bool:
        return bool(await self._client.exists(_stream_key(run_id)))

    async def read(
        self, run_id: UUID, after_seq: int | None, block_ms: int
    ) -> AsyncIterator[RunEvent]:
        stream = _stream_key(run_id)
        last_id = f"{after_seq}-0" if after_seq is not None else "0-0"
        while True:
            response = await self._client.xread({stream: last_id}, block=block_ms)
            if not response:
                continue  # block_ms 동안 아무것도 없었습니다 — 다시 블록합니다(취소 지점).
            # `redis-py` 의 `XReadResponse` 스텁은 `decode_responses` 여부에 따라 갈리는
            # 넓은 union 입니다 — `client` 가 `decode_responses=True` 라는 이 어댑터의
            # 전제(클래스 docstring)를 실측으로 좁힙니다(`test_run_notifier.py` 와 같은
            # 패턴). `mypy ignore` 를 쓰지 않고 실제로 형태를 확인합니다.
            assert isinstance(response, list), (
                f"RedisRunEventReader: 예상치 못한 XREAD 응답 형태: {type(response)!r} "
                "(decode_responses=True 로 접속했는지 확인하십시오)"
            )
            _stream_name, entries = response[0]
            for entry_id, fields in entries:
                assert isinstance(entry_id, str)
                assert fields is not None
                last_id = entry_id
                yield RunEvent.model_validate_json(fields["data"])
