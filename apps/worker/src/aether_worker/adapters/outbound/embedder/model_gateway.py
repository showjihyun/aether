"""spec 0004 2.1, D-3, D-9: `ModelGatewayEmbedder` — `aether_context.Embedder` 포트를
`aether_runtime.ModelGateway.embed` 로 구현합니다.

이 어댑터는 `aether_worker`(조립 지점, AR-10)에만 있습니다 — `aether_context` 는
`aether_runtime` 을 import 하지 않으므로(AR-3) 이 변환을 그 패키지 안에 둘 수 없고,
`main.py` 가 `aether_runtime` 의 gateway 를 이 어댑터 뒤에 꽂아 `IngestKnowledgeUseCase`
에 건넵니다.
"""

from __future__ import annotations

from aether_runtime.application.ports.outbound.model_gateway import ModelGateway


class ModelGatewayEmbedder:
    """`aether_context.application.ports.outbound.embedder.Embedder` 의 구현."""

    def __init__(self, gateway: ModelGateway, *, model_id: str, dim: int) -> None:
        self._gateway = gateway
        self._model_id = model_id
        self._dim = dim

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._gateway.embed(texts)
