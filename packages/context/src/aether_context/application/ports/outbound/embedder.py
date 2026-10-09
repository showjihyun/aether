"""spec 0004 2.1, 2.4, D-3, D-9, R-6: `Embedder` outbound 포트.

`aether_context` 는 `aether_runtime.ModelGateway` 를 직접 보지 않습니다(AR-3) —
worker 의 `main` 이 `aether_runtime` 의 gateway 를 이 포트 뒤에 꽂습니다. `model_id`·
`dim` 은 임베딩에 쓰인 모델의 정체와 차원이고, `IngestKnowledgeUseCase` 가 그대로
`EmbeddedChunk` 에 실어(D-9) 재적재 요구 오류(C-3)의 근거로 씁니다.
"""

from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    @property
    def model_id(self) -> str:
        """이 `Embedder` 가 쓰는 임베딩 모델 id(spec D-3, `AETHER_EMBED_MODEL_ID`)."""
        ...

    @property
    def dim(self) -> int:
        """임베딩 벡터의 차원(spec D-9, `AETHER_EMBED_DIM`)."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """`texts` 와 같은 길이·순서의 임베딩 벡터 목록을 돌려줍니다."""
        ...
