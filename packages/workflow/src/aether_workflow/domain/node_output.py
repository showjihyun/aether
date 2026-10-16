"""spec 0005 2.4 개정 4, D-8 (P4-2b): 노드 출력 - JSON 객체, **직렬화된 바이트** 기준 상한.

상한을 넘기면 자르고 `truncated` 를 **함께** 참으로 둡니다(조용히 자르지 않습니다). 자르는 단위는
`str` 의 코드 포인트라서 UTF-8 한 글자를 반으로 가르지 않습니다 - 바이트를 자르고 디코딩 오류를
무시하는 방식은 쓰지 않습니다.

출력은 `data` 의 노드 실행 기록에만 두고 span·감사·보고에는 넣지 않습니다(C-3,
`tests/arch/test_workflow_output_stays_in_data.py`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NodeOutput:
    value: dict[str, Any]
    truncated: bool = False


def serialized_size(value: dict[str, Any]) -> int:
    """상한이 재는 크기: compact JSON 을 UTF-8 로 쓴 바이트 수."""
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _capped_text_output(
    text_key: str, text: str, fixed: dict[str, Any], max_bytes: int
) -> NodeOutput:
    """`{text_key: <본문>, **fixed}` 를 상한 안에 넣습니다 - 본문만 자르고 `fixed`(판정에 쓰이는 값)
    는 줄이지 않습니다. 상한이 틀(본문이 빈 채의 직렬화)보다 작으면 본문은 빈 문자열이고 그래도
    `truncated` 입니다."""
    whole = {text_key: text, **fixed}
    if serialized_size(whole) <= max_bytes:
        return NodeOutput(whole)
    # 접두사 길이에 대해 크기가 단조 증가하므로 이진 탐색으로 가장 긴 접두사를 찾는다.
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if serialized_size({text_key: text[:middle], **fixed}) <= max_bytes:
            low = middle
        else:
            high = middle - 1
    return NodeOutput({text_key: text[:low], **fixed}, truncated=True)


def agent_output(text: str, status: str, max_bytes: int) -> NodeOutput:
    """`AGENT` 노드의 출력: `{"text": <마지막 assistant 본문, 상한까지>, "status": <종결 상태>}`.

    본문만 자릅니다 - `status` 는 판정에 쓰이므로 줄이지 않습니다.
    """
    return _capped_text_output("text", text, {"status": status}, max_bytes)


def llm_output(text: str, finish_reason: str, max_bytes: int) -> NodeOutput:
    """`LLM` 노드의 출력(spec 0005 2.8 개정 9 (5)): `{"text", "finish_reason"}` - `AGENT` 와 같은
    상한·같은 잘림 표시. 본문만 자릅니다."""
    return _capped_text_output("text", text, {"finish_reason": finish_reason}, max_bytes)


def tool_output(content: str, is_error: bool, max_bytes: int) -> NodeOutput:
    """`TOOL`·`MCP` 노드의 출력(개정 9 (5)): `{"content", "is_error"}` - 같은 상한·같은 잘림 표시.
    본문(`content`)만 자르고 `is_error` 는 줄이지 않습니다."""
    return _capped_text_output("content", content, {"is_error": is_error}, max_bytes)


def join_output(branches: Mapping[str, Any], max_bytes: int) -> NodeOutput:
    """`JOIN` 노드의 출력: `{"branches": {"<들어오는 노드 id>": <그 노드의 출력 또는 null>}}`
    (spec 0005 2.7 개정 7 (3)).

    같은 상한(`serialized_size`)과 같은 잘림 표시를 씁니다. 넘으면 **가장 큰 분기 출력부터**
    `null` 로
    바꿔 상한 안에 들어올 때까지 줄이고 `truncated` 를 함께 참으로 둡니다(크기가 같으면 id 순). 분기
    id 는 줄이지 않으므로 상한이 id 들의 틀보다 작으면 틀이 그대로 남고 그래도 `truncated` 입니다.
    """
    kept: dict[str, Any] = dict(branches)
    whole = {"branches": kept}
    if serialized_size(whole) <= max_bytes:
        return NodeOutput(whole)
    by_size = sorted(
        (key for key, value in kept.items() if value is not None),
        key=lambda key: (-serialized_size({"branches": {key: kept[key]}}), key),
    )
    for key in by_size:
        kept[key] = None
        if serialized_size({"branches": kept}) <= max_bytes:
            break
    return NodeOutput({"branches": kept}, truncated=True)
