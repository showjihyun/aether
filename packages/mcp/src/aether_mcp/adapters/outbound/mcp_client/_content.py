"""SDK `CallToolResult` → 우리 `ToolResult.content`(str) 변환. `stdio.py`·`http.py` 공용.

SDK 타입을 이 어댑터 패키지 밖으로 내보내지 않기 위해 변환을 한 곳에 모읍니다(AR-6).
"""

from __future__ import annotations

from typing import Any


def extract_text(result: Any) -> str:
    texts = [block.text for block in result.content if getattr(block, "type", None) == "text"]
    if texts:
        return "\n".join(texts)
    if result.structured_content is not None:
        return str(result.structured_content)
    return ""
