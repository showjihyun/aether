"""spec 0004 2.4 (P3-2b): `FilesystemConnector` 가 디렉터리를 결정적(정렬된) 순서로
읽는 것 — 집합·정렬 없는 순회를 쓰면 청크 순서가 실행마다 달라집니다(P3-1 에서
배운 함정과 같습니다).

구현 뒤에 작성됐습니다(red→green 순서 위반, 보고에 기록).
"""

from __future__ import annotations

from pathlib import Path

from aether_context.adapters.outbound.connector.filesystem import FilesystemConnector


def test_list_documents_returns_sorted_paths(tmp_path: Path) -> None:
    (tmp_path / "zeta.txt").write_text("z", encoding="utf-8")
    (tmp_path / "alpha.txt").write_text("a", encoding="utf-8")
    sub = tmp_path / "mid"
    sub.mkdir()
    (sub / "beta.txt").write_text("b", encoding="utf-8")

    connector = FilesystemConnector()
    documents = connector.list_documents(str(tmp_path))

    assert [d.path for d in documents] == ["alpha.txt", "mid/beta.txt", "zeta.txt"]
    assert [d.content for d in documents] == ["a", "b", "z"]


def test_list_documents_is_deterministic_across_repeats(tmp_path: Path) -> None:
    for name in ["c.txt", "a.txt", "b.txt"]:
        (tmp_path / name).write_text(name, encoding="utf-8")

    connector = FilesystemConnector()
    first = connector.list_documents(str(tmp_path))
    second = connector.list_documents(str(tmp_path))
    assert first == second


def test_list_documents_empty_directory(tmp_path: Path) -> None:
    connector = FilesystemConnector()
    assert connector.list_documents(str(tmp_path)) == ()
