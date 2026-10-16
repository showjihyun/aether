"""spec 0005 2.8 개정 9 (3) (P4-5): `LLM` 의 프롬프트와 `TOOL`·`MCP` 의 인자를 맥락에서 조립합니다 -
**순수 함수**(I/O 없음, AR-9).

경로는 `CONDITION` 과 같은 맥락(`{"input": ..., "nodes": {"<id>": <출력>}}`)을 가리키고
같은 규칙으로 읽습니다: 없는 경로는 `ConditionFailure(condition_path_missing)`.
**템플릿 언어를 만들지 않습니다** - 프롬프트는 경로 값을 리터럴 **뒤에 덧붙이고**, 인자는
경로 값(객체)을 리터럴 위에 **병합**합니다(경로 값이 이깁니다). 임의 표현식을 평가하지 않는다는
D-9 의 정신 그대로입니다.

인자 경로의 값이 객체가 아니면 병합할 수 없으므로 `condition_type_mismatch` 를 재사용합니다 - 새
사유를 만들지 않고, 뜻은 "그 경로의 값이 노드가 기대한 타입이 아님" 입니다.
"""

from __future__ import annotations

import json
from typing import Any

from aether_workflow.domain.condition import ConditionFailure, resolve_path
from aether_workflow.domain.failure import WorkflowFailureReason


def build_prompt(literal: str | None, path: str | None, context: dict[str, Any]) -> str:
    """리터럴 프롬프트 뒤에 줄바꿈 하나와 경로 값을 덧붙입니다. 값이 문자열이 아니면 JSON 으로
    직렬화합니다. 경로가 없으면 리터럴 그대로입니다."""
    base = literal or ""
    if path is None:
        return base
    value = resolve_path(context, path)
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return f"{base}\n{text}" if base else text


def build_arguments(
    literal: dict[str, Any] | None, path: str | None, context: dict[str, Any]
) -> dict[str, Any]:
    """리터럴 인자 위에 경로의 객체를 병합합니다(경로 값이 이김). 노드 정의의 리터럴은 바꾸지
    않고 새 객체를 돌려줍니다."""
    merged: dict[str, Any] = dict(literal) if literal else {}
    if path is None:
        return merged
    value = resolve_path(context, path)
    if not isinstance(value, dict):
        raise ConditionFailure(WorkflowFailureReason.CONDITION_TYPE_MISMATCH)
    merged.update(value)
    return merged
