"""spec 0005 2.4 개정 4, D-9, R-5 (P4-2b): `CONDITION` 의 판정 - **순수 함수**(I/O 없음, AR-9).

판정 대상은 선언된 맥락 하나입니다:
`{"input": <Workflow Run 의 입력>, "nodes": {"<노드 id>": <그 노드의 출력>}}`. 경로는 점 표기
(`nodes.ask.text`·`input.q`)이고 객체의 키만 따라갑니다. "직전 노드" 같은 암묵 규칙은 없습니다.
(노드 id 에 `.` 이 들어 있으면 그 노드의 출력은 경로로 가리킬 수 없습니다 - 모호함을 만들지 않으려고
경로 문법을 더 늘리지 않았습니다.)

연산자는 여섯으로 닫습니다. 임의 표현식을 평가하지 않고 모델에게 묻지 않습니다(D-9).

**없는 경로는 조용한 거짓이 아닙니다.** `exists` 만 거짓이고 나머지는 `ConditionFailure(
condition_path_missing)` 입니다. 비교할 수 없는 타입(`gt`·`lt` 에 숫자가 아닌 값, `contains` 에
담을 수 없는 타입)은 `condition_type_mismatch` 입니다. 실행기가 이 예외를 노드 실패로 옮깁니다.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from aether_workflow.domain.failure import WorkflowFailureReason


class ConditionOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    GT = "gt"
    LT = "lt"
    EXISTS = "exists"


class ConditionFailure(Exception):
    """판정할 수 없다 - 거짓이 아니라 실행 실패입니다."""

    def __init__(self, reason: WorkflowFailureReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


_MISSING = object()


def _resolve(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return _MISSING
        current = current[segment]
    return current


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _equal(actual: Any, expected: Any) -> bool:
    # Python 의 `True == 1` 이 판정에 새지 않게 bool 은 bool 끼리만 같다.
    if isinstance(actual, bool) != isinstance(expected, bool):
        return False
    return bool(actual == expected)


def _contains(actual: Any, expected: Any) -> bool:
    """경로의 값(`actual`) 안에 `expected` 가 있는가."""
    if isinstance(actual, str):
        if not isinstance(expected, str):
            raise ConditionFailure(WorkflowFailureReason.CONDITION_TYPE_MISMATCH)
        return expected in actual
    if isinstance(actual, list):
        return any(_equal(item, expected) for item in actual)
    if isinstance(actual, dict):
        if not isinstance(expected, str):
            raise ConditionFailure(WorkflowFailureReason.CONDITION_TYPE_MISMATCH)
        return expected in actual
    raise ConditionFailure(WorkflowFailureReason.CONDITION_TYPE_MISMATCH)


def evaluate_condition(
    context: dict[str, Any], path: str, operator: ConditionOperator, value: Any
) -> bool:
    actual = _resolve(context, path)
    if operator is ConditionOperator.EXISTS:
        return actual is not _MISSING
    if actual is _MISSING:
        raise ConditionFailure(WorkflowFailureReason.CONDITION_PATH_MISSING)
    if operator is ConditionOperator.EQUALS:
        return _equal(actual, value)
    if operator is ConditionOperator.NOT_EQUALS:
        return not _equal(actual, value)
    if operator is ConditionOperator.CONTAINS:
        return _contains(actual, value)
    if not (_is_number(actual) and _is_number(value)):
        raise ConditionFailure(WorkflowFailureReason.CONDITION_TYPE_MISMATCH)
    return bool(actual > value) if operator is ConditionOperator.GT else bool(actual < value)
