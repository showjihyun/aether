"""spec 0005 2.4 개정 4, D-8 (P4-2b): 노드 출력 - JSON 객체, **직렬화된 바이트** 기준 상한.

상한을 넘기면 자르고 `truncated` 를 **함께** 참으로 둡니다(조용히 자르지 않습니다). 자르는 단위는
`str` 의 코드 포인트라서 UTF-8 한 글자를 반으로 가르지 않습니다 - 바이트를 자르고 디코딩 오류를
무시하는 방식은 쓰지 않습니다.

출력은 `data` 의 노드 실행 기록에만 두고 span·감사·보고에는 넣지 않습니다(C-3,
`tests/arch/test_workflow_output_stays_in_data.py`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NodeOutput:
    value: dict[str, Any]
    truncated: bool = False


def serialized_size(value: dict[str, Any]) -> int:
    """상한이 재는 크기: compact JSON 을 UTF-8 로 쓴 바이트 수."""
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def agent_output(text: str, status: str, max_bytes: int) -> NodeOutput:
    """`AGENT` 노드의 출력: `{"text": <마지막 assistant 본문, 상한까지>, "status": <종결 상태>}`.

    본문만 자릅니다 - `status` 는 판정에 쓰이므로 줄이지 않습니다. 상한이 틀(`text` 가 빈 채의
    직렬화)보다 작으면 본문은 빈 문자열이고 그래도 `truncated` 입니다.
    """
    whole = {"text": text, "status": status}
    if serialized_size(whole) <= max_bytes:
        return NodeOutput(whole)
    # 접두사 길이에 대해 크기가 단조 증가하므로 이진 탐색으로 가장 긴 접두사를 찾는다.
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if serialized_size({"text": text[:middle], "status": status}) <= max_bytes:
            low = middle
        else:
            high = middle - 1
    return NodeOutput({"text": text[:low], "status": status}, truncated=True)
