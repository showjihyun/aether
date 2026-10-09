"""spec 0004 2.4 (P3-2b): `Connector` 포트의 Filesystem 구현.

`pathlib` 만 씁니다(표준 라이브러리, AR-5·AR-9 에 걸리지 않습니다). `source` 아래의
파일을 **경로 문자열 오름차순으로 정렬**해 읽습니다 — `os.walk`/`Path.rglob` 의
순회 순서는 파일시스템에 따라 달라질 수 있으므로, 정렬 없이 그대로 쓰면 청크
순서가 실행마다 달라질 수 있습니다(결정성, P3-1 에서 같은 함정을 봤습니다).
"""

from __future__ import annotations

from pathlib import Path

from aether_context.domain.knowledge import Document


class FilesystemConnector:
    """`Connector` 포트의 Filesystem 구현 — 디렉터리 하나를 재귀적으로 읽습니다."""

    def list_documents(self, source: str) -> tuple[Document, ...]:
        root = Path(source)
        paths = sorted(
            (path for path in root.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(root).as_posix(),
        )
        return tuple(
            Document(
                path=path.relative_to(root).as_posix(),
                content=path.read_text(encoding="utf-8"),
            )
            for path in paths
        )
