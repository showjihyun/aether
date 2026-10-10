"""spec 0004 2.4, D-9: Knowledge 적재 파이프라인의 값 타입.

`Connector(Filesystem) -> Indexer(청크) -> Embedder -> KnowledgeStore` 네 단계가
주고받는 값들입니다. 표준 `dataclass`/`uuid.UUID` 만 씁니다(AR-9 — domain 은
프레임워크·I/O 를 쓰지 않습니다).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    """`Connector` 가 돌려주는 문서 하나. `path` 는 적재 소스 루트에 대한 상대
    경로입니다 — 출처(spec 2.5)로 그대로 쓰입니다."""

    path: str
    content: str


@dataclass(frozen=True)
class Chunk:
    """`Indexer` 가 문서 하나를 쪼갠 조각 하나. `chunk_index` 는 그 문서 안에서
    0부터 시작하는 순서입니다(결정성, R-1 과 같은 이유)."""

    source_path: str
    chunk_index: int
    content: str


@dataclass(frozen=True)
class EmbeddedChunk:
    """`Embedder` 를 지난 뒤의 청크 — 임베딩과 함께 **모델 id·차원**을 싣습니다
    (D-9). `KnowledgeStore.replace_chunks` 가 그대로 저장합니다."""

    source_path: str
    chunk_index: int
    content: str
    embedding: tuple[float, ...]
    embed_model_id: str
    embed_dim: int


@dataclass(frozen=True)
class SearchResult:
    """`KnowledgeStore.search` 한 건. `score` 는 코사인 거리(D-2) — 작을수록
    가깝습니다. 출처 없는 결과는 없습니다(`source_path`·`chunk_index` 가 항상
    채워집니다, spec 2.5)."""

    source_path: str
    chunk_index: int
    content: str
    score: float


def render_knowledge_block(result: SearchResult) -> str:
    """spec 2.5, D-8: `SearchResult` 하나를 전용 블록으로 렌더링합니다 — `aether_runtime.
    domain.observation.render_observation` 과 같은 모양(표지 `trust=untrusted` +
    출처). `CompileContextUseCase` 가 이 문자열을 system·conversation 과 **분리된**
    독립 메시지 하나로 넣습니다 — system 메시지에 이어 붙이지 않습니다(R-8)."""
    return (
        f"[knowledge source={result.source_path} chunk={result.chunk_index} trust=untrusted]"
        f"{result.content}"
        "[/knowledge]"
    )
