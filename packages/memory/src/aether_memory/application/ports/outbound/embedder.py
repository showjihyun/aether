"""spec 0004 2.1, D-3, D-9 (P3-4): `Embedder` outbound 포트.

`aether_context` 의 `Embedder` 와 **같은 모양**을 이 패키지에 따로 선언합니다 —
`aether_memory` 는 `aether_runtime`(모델 게이트웨이)을 import 하지 않으므로(AR-3 과
같은 이유, P3-2b 선례) worker 의 `main` 이 gateway 를 이 포트 뒤에 꽂습니다. Knowledge 와
**같은 임베딩 모델**을 씁니다(`AETHER_EMBED_MODEL_ID`·`AETHER_EMBED_DIM`).
"""

from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    @property
    def model_id(self) -> str:
        """임베딩 모델 id. 저장되어 읽을 때 같은 모델의 기억만 비교하게 합니다."""
        ...

    @property
    def dim(self) -> int:
        """임베딩 벡터의 차원."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """`texts` 와 같은 길이·순서의 임베딩 벡터 목록."""
        ...
