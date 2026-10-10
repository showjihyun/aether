"""spec 0004 2.1, 2.6, AR-3 (P3-4): `AetherContextCompiler` 가 `agent_id` 를
`aether_context` 의 `CompileContextRequest` 로 그대로 옮기는가. 변환만 하는 어댑터이므로
`CompileContext` 자리에 요청을 기록하는 fake 를 꽂습니다.
"""

from __future__ import annotations

from uuid import uuid4

from aether_context.application.ports.inbound.compile_context import (
    CompileContextRequest,
    CompileContextResult,
)
from aether_context.domain.report import ContextReport as AetherContextReport
from aether_runtime.adapters.outbound.context_compiler.aether_context import AetherContextCompiler
from aether_runtime.domain.run import Message


class _RecordingCompile:
    def __init__(self) -> None:
        self.requests: list[CompileContextRequest] = []

    def __call__(self, request: CompileContextRequest) -> CompileContextResult:
        self.requests.append(request)
        return CompileContextResult(
            messages=(),
            tools=(),
            report=AetherContextReport(budget_tokens=1, source_tokens=(), total_tokens=0),
        )


def test_agent_id_is_forwarded_to_the_compile_request() -> None:
    agent_id = uuid4()
    recorder = _RecordingCompile()
    compiler = AetherContextCompiler(recorder)

    compiler.compile(
        system_prompt="s",
        conversation=(Message.user("hi"),),
        tools=(),
        budget_tokens=100,
        agent_id=agent_id,
    )
    compiler.compile(system_prompt="s", conversation=(), tools=(), budget_tokens=100)

    assert recorder.requests[0].agent_id == agent_id
    assert recorder.requests[1].agent_id is None
