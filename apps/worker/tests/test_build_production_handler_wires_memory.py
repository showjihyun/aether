"""spec 0004 2.1, 2.6, D-5 (P3-4): `aether_worker.main._build_production_handler` 가 Memory 의
읽기(Compiler 쪽 `MemoryReader`)와 쓰기(Executor 쪽 `MemoryWriter`) 를 모두 꽂는지.

`test_memory_end_to_end_integration.py` 가 손으로 반복한 조립이 올바른지 증명하므로, 여기서는
"worker 의 실제 조립 함수가 두 포트를 실제로 꽂는가" 만 봅니다. 꽂지 않으면 `memory_enabled`
가 참이어도 아무것도 남지 않고 읽히지도 않습니다(조용한 무동작).
"""

from __future__ import annotations

import pytest
from aether_memory.application.usecases.write_agent_memory import WriteAgentMemoryUseCase
from aether_runtime.adapters.outbound.context_compiler.aether_context import AetherContextCompiler
from aether_worker.adapters.outbound.memory.reader import MemoryReaderAdapter
from aether_worker.main import _build_production_handler
from aether_worker.settings import Settings
from redis import Redis

pytestmark = pytest.mark.integration


def test_production_handler_wires_memory_reader_and_writer(
    control_database_url: str, redis_client: Redis
) -> None:
    settings = Settings(database_url=control_database_url)

    handler = _build_production_handler(settings, redis_client)

    execute_run = handler._execute_run  # type: ignore[attr-defined]
    assert isinstance(execute_run._memory_writer, WriteAgentMemoryUseCase)
    context_compiler = execute_run._context_compiler
    assert isinstance(context_compiler, AetherContextCompiler)
    assert isinstance(context_compiler._compile_context._memory_reader, MemoryReaderAdapter)  # type: ignore[attr-defined]
