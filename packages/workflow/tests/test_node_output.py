"""spec 0005 2.4 개정 4, D-8 (P4-2b): 노드 출력의 상한 - 순수 함수, 컨테이너·DB 없음(AR-9).

증명하는 것: 상한은 **직렬화된 바이트** 기준이다 /
넘기면 자르고 `truncated` 를 **함께** 참으로 한다 /
자르는 경계가 UTF-8 안전(한국어) / 상한 안에 들어오면 그대로 두고 잘림 표시도 없다.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from aether_workflow.domain.node_output import agent_output


def _size(value: Mapping[str, object]) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def test_an_output_within_the_limit_is_kept_whole_and_not_marked() -> None:
    out = agent_output("hello", "succeeded", 8192)
    assert out.value == {"text": "hello", "status": "succeeded"}
    assert out.truncated is False


def test_one_byte_over_the_limit_is_cut_and_marked_together() -> None:
    """spec 개정 4 (4): 상한 + 1 바이트는 잘리고 플래그가 함께 남는다."""
    exact = _size({"text": "", "status": "succeeded"})
    limit = exact + 100
    fits = agent_output("x" * 100, "succeeded", limit)
    assert fits.truncated is False
    assert _size(fits.value) == limit

    over = agent_output("x" * 101, "succeeded", limit)
    assert over.truncated is True
    assert _size(over.value) <= limit
    assert over.value["text"] == "x" * 100
    assert over.value["status"] == "succeeded"


def test_the_cut_boundary_is_utf8_safe_for_korean() -> None:
    """한 글자는 3 바이트다 - 바이트 한가운데서 자르면 디코딩이 깨진다."""
    text = "안녕하세요 " * 400
    limit = 200
    out = agent_output(text, "succeeded", limit)

    assert out.truncated is True
    cut = out.value["text"]
    assert isinstance(cut, str)
    assert text.startswith(cut)
    encoded = json.dumps(out.value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert encoded.decode("utf-8")  # 디코딩이 깨지지 않는다 (strict)
    assert len(encoded) <= limit
    # 다음 글자 하나를 더 넣으면 상한을 넘는다 - 필요 이상으로 자르지 않는다.
    longer = {"text": text[: len(cut) + 1], "status": "succeeded"}
    assert _size(longer) > limit


def test_the_limit_counts_serialized_bytes_not_characters() -> None:
    """따옴표·개행 이스케이프는 직렬화된 바이트를 늘린다."""
    text = '"\n' * 100  # 200 자, 직렬화하면 400 바이트
    out = agent_output(text, "succeeded", 150)
    assert out.truncated is True
    assert _size(out.value) <= 150


def test_a_non_succeeded_status_is_carried() -> None:
    assert agent_output("", "failed", 8192).value == {"text": "", "status": "failed"}
