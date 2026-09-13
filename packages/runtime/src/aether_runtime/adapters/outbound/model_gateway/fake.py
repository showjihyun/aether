"""spec 0002 2.5 (P1-3, P1-5a): `FakeModelGateway` — 스크립트된 응답 열을 소비하는
테스트용 어댑터. 전 테스트와 `smoke` 의 기본입니다(`AETHER_MODEL_ADAPTER=fake`).

시나리오 항목은 텍스트 응답 / 도구 호출 응답(`tool_calls`) / `reasoning` 포함 응답
(전부 `ModelResponse`) 또는 예외(`ModelError`)입니다. `complete` 호출마다 하나씩,
등록된 순서대로 소비합니다. `calls` 에 호출된 `ModelRequest` 를 그대로 쌓아 두어
테스트가 요청 구조(메시지·도구·`tool_call_id`)를 단언할 수 있게 합니다.

시나리오가 비면 기본은 여전히 `ModelError`(protocol) 이지만, `default` 를 주면
그 응답을 계속 돌려주고, `echo()` 는 마지막 `user` 메시지를 그대로 돌려주는(도구
호출 없음) 동적 기본 응답입니다 — compose 의 `AETHER_MODEL_ADAPTER=fake` 가 실제
모델 없이도 무한히 `succeeded` 로 끝나는 Run 을 만들 수 있게 합니다(P1-5a).
"""

from __future__ import annotations

import hashlib
from collections import deque
from collections.abc import Iterator, Sequence

from aether_runtime.application.ports.outbound.model_gateway import (
    ModelDelta,
    ModelError,
    ModelRequest,
    ModelResponse,
)

_EMBEDDING_DIMENSIONS = 8


def _hash_vector(text: str, dimensions: int = _EMBEDDING_DIMENSIONS) -> list[float]:
    """결정적 벡터 — 같은 텍스트는 항상 같은 벡터(문자열 해시 기반, Phase 3 소비 전까지
    값 자체의 의미는 없습니다)."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [digest[index] / 255.0 for index in range(dimensions)]


class FakeModelGateway:
    """`ModelGateway` 포트의 인메모리 구현(spec 0002 2.5)."""

    def __init__(
        self,
        scenario: Sequence[ModelResponse | ModelError] = (),
        *,
        default: ModelResponse | None = None,
    ) -> None:
        self._scenario: deque[ModelResponse | ModelError] = deque(scenario)
        self._default = default
        self._echo = False
        self.calls: list[ModelRequest] = []

    @classmethod
    def echo(cls) -> FakeModelGateway:
        """spec 0002 2.5 (P1-5a): 마지막 `user` 메시지를 그대로 돌려주는 기본 응답
        (도구 호출 없음). `default` 와 달리 요청마다 내용이 달라야 하므로 정적
        `ModelResponse` 로 표현할 수 없어 별도 플래그로 처리합니다."""
        gateway = cls()
        gateway._echo = True
        return gateway

    def _consume(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        if self._scenario:
            item = self._scenario.popleft()
            if isinstance(item, ModelError):
                raise item
            return item
        if self._echo:
            last_user = next(
                (
                    message.content
                    for message in reversed(request.messages)
                    if message.role == "user"
                ),
                "",
            )
            return ModelResponse(text=last_user, finish_reason="stop")
        if self._default is not None:
            return self._default
        raise ModelError(kind="protocol", message="FakeModelGateway scenario exhausted")

    def complete(self, request: ModelRequest) -> ModelResponse:
        return self._consume(request)

    def stream(self, request: ModelRequest) -> Iterator[ModelDelta]:
        """같은 응답을 delta 로 쪼개 냅니다 — reasoning → text(어절 단위) → 도구 호출 →
        `done=True` 마감 조각 순서입니다."""
        response = self._consume(request)
        if response.reasoning:
            yield ModelDelta(reasoning=response.reasoning)
        if response.text:
            words = response.text.split(" ")
            for index, word in enumerate(words):
                chunk = word if index == len(words) - 1 else word + " "
                yield ModelDelta(text=chunk)
        for tool_call in response.tool_calls:
            yield ModelDelta(tool_call=tool_call)
        yield ModelDelta(done=True)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_hash_vector(text) for text in texts]
