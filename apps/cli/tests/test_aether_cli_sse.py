"""SSE 줄 파서 - 서버(`_format_sse`)와 같은 모양, 주석, 여러 줄 data, 닫히지 않은 이벤트."""

from __future__ import annotations

from aether_cli.sse import SseEvent, parse_sse


def test_parses_id_event_and_data() -> None:
    """spec 0002 2.7 SSE 필드 `id`·`event`·`data` 를 읽는다."""
    lines = [b"id: 7\n", b"event: run.status\n", b'data: {"x": 1}\n', b"\n"]

    assert list(parse_sse(lines)) == [SseEvent(event="run.status", data='{"x": 1}', id="7")]


def test_ignores_comments_and_handles_crlf_and_multiline_data() -> None:
    """keep-alive 주석은 이벤트가 아니다. CRLF 와 여러 줄 data 를 잇는다."""
    lines = [b": keep-alive\r\n", b"\r\n", b"data: a\r\n", b"data: b\r\n", b"\r\n"]

    assert [e.data for e in parse_sse(lines)] == ["a\nb"]


def test_unterminated_event_is_dropped() -> None:
    """빈 줄 없이 끝난 이벤트는 버린다(끊김을 완성된 이벤트로 오해하지 않는다)."""
    assert list(parse_sse([b"event: run.finished\n", b'data: {"status": "x"}\n'])) == []
