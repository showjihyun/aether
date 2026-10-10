"""spec 0004 2.1, D-5, R-8, R-9 (P3-3): `aether_worker.main._build_production_handler`
가 `AetherContextCompiler(CompileContextUseCase(CharApproxTokenCounter(),
PostgresKnowledgeSearch(...)))` 를 `ExecuteRunUseCase` 에 꽂는지.

`packages/runtime/tests/test_execute_run_knowledge_in_context_integration.py` 가
그 파이프라인 **자체**(실제 조립을 손으로 반복)가 올바른지 증명했으므로, 여기서는
"worker 의 실제 조립 함수가 passthrough 가 아니라 그 파이프라인을 실제로 쓰는가"
만 봅니다 — `_PassthroughContextCompiler`(spec R-3 기본값, Knowledge 를 모름)가
그대로 남아 있으면 이 단위는 R-8·R-9 를 만족할 수 없습니다(실측, 작업 전 사실
확인 2절)."""

from __future__ import annotations

from collections.abc import Callable

import psycopg
import pytest
from aether_context.adapters.outbound.knowledge_search.postgres import PostgresKnowledgeSearch
from aether_runtime.adapters.outbound.context_compiler.aether_context import AetherContextCompiler
from aether_worker.main import _build_production_handler
from aether_worker.settings import Settings
from redis import Redis

pytestmark = pytest.mark.integration


def test_production_handler_wires_aether_context_compiler_with_knowledge_search(
    control_database_url: str,
    redis_client: Redis,
    data_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    settings = Settings(database_url=control_database_url)

    handler = _build_production_handler(settings, redis_client)

    execute_run = handler._execute_run  # type: ignore[attr-defined]
    context_compiler = execute_run._context_compiler
    assert isinstance(context_compiler, AetherContextCompiler)

    compile_context = context_compiler._compile_context
    knowledge_search = compile_context._knowledge_search  # type: ignore[attr-defined]
    assert isinstance(knowledge_search, PostgresKnowledgeSearch)
