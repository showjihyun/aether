"""spec 0005 2.4 개정 4, D-9, R-5 (P4-2b): `CONDITION` 판정 - 순수 함수, 컨테이너·DB 없음(AR-9).

증명하는 것: 연산자는 여섯으로 닫혀 있다 / 각 연산자의 참·거짓 / 없는 경로는 `exists` 만 거짓이고
나머지는 `condition_path_missing` / 비교할 수 없는 타입은 `condition_type_mismatch`.
"""

from __future__ import annotations

from typing import Any

import pytest
from aether_workflow.domain.condition import (
    ConditionFailure,
    ConditionOperator,
    evaluate_condition,
)
from aether_workflow.domain.failure import WorkflowFailureReason

_CONTEXT: dict[str, Any] = {
    "input": {"q": "hello", "n": 5, "flag": True, "tags": ["a", "b"], "none": None},
    "nodes": {"ask": {"text": "the answer is yes", "status": "succeeded"}},
}

_O = ConditionOperator


def test_the_operators_are_exactly_six() -> None:
    """spec D-9: 연산자는 여섯으로 닫는다 - 임의 표현식을 평가하지 않는다."""
    assert {o.value for o in _O} == {"equals", "not_equals", "contains", "gt", "lt", "exists"}


@pytest.mark.parametrize(
    ("path", "operator", "value", "expected"),
    [
        ("input.q", _O.EQUALS, "hello", True),
        ("input.q", _O.EQUALS, "bye", False),
        ("input.n", _O.EQUALS, 5, True),
        ("input.n", _O.EQUALS, 6, False),
        ("input.q", _O.NOT_EQUALS, "bye", True),
        ("input.q", _O.NOT_EQUALS, "hello", False),
        ("nodes.ask.text", _O.CONTAINS, "yes", True),
        ("nodes.ask.text", _O.CONTAINS, "no way", False),
        ("input.tags", _O.CONTAINS, "a", True),
        ("input.tags", _O.CONTAINS, "z", False),
        ("input.n", _O.GT, 4, True),
        ("input.n", _O.GT, 5, False),
        ("input.n", _O.LT, 6, True),
        ("input.n", _O.LT, 5, False),
        ("input.q", _O.EXISTS, None, True),
        ("input.none", _O.EXISTS, None, True),
    ],
)
def test_each_operator_has_a_true_and_a_false_case(
    path: str, operator: ConditionOperator, value: Any, expected: bool
) -> None:
    assert evaluate_condition(_CONTEXT, path, operator, value) is expected


def test_contains_asks_whether_the_actual_value_holds_the_expected_one() -> None:
    """방향: `condition_value` 가 경로의 값 안에 있는가 (반대가 아니다)."""
    context = {"input": {"q": "yes"}}
    assert evaluate_condition(context, "input.q", _O.CONTAINS, "yes, indeed") is False
    assert evaluate_condition({"input": {"q": "yes, indeed"}}, "input.q", _O.CONTAINS, "yes")


def test_a_boolean_is_not_equal_to_a_number() -> None:
    """Python 의 `True == 1` 이 판정에 새지 않는다."""
    assert evaluate_condition(_CONTEXT, "input.flag", _O.EQUALS, 1) is False
    assert evaluate_condition(_CONTEXT, "input.flag", _O.EQUALS, True) is True


def test_exists_is_false_for_a_missing_path() -> None:
    assert evaluate_condition(_CONTEXT, "input.nope", _O.EXISTS, None) is False
    assert evaluate_condition(_CONTEXT, "nodes.ghost.text", _O.EXISTS, None) is False
    # 중간이 객체가 아니어도 없는 것이다.
    assert evaluate_condition(_CONTEXT, "input.q.deeper", _O.EXISTS, None) is False


@pytest.mark.parametrize(
    "operator", [_O.EQUALS, _O.NOT_EQUALS, _O.CONTAINS, _O.GT, _O.LT], ids=lambda o: o.value
)
def test_a_missing_path_is_an_execution_failure_for_every_other_operator(
    operator: ConditionOperator,
) -> None:
    """spec 개정 4 (2): 조용한 거짓이 아니다."""
    with pytest.raises(ConditionFailure) as raised:
        evaluate_condition(_CONTEXT, "nodes.ghost.text", operator, "x")
    assert raised.value.reason is WorkflowFailureReason.CONDITION_PATH_MISSING


@pytest.mark.parametrize(
    ("path", "operator", "value"),
    [
        ("input.q", _O.GT, 1),  # 실제 값이 문자열
        ("input.q", _O.LT, 1),
        ("input.n", _O.GT, "3"),  # 기대 값이 문자열
        ("input.n", _O.LT, "3"),
        ("input.flag", _O.GT, 0),  # bool 은 숫자가 아니다
        ("input.n", _O.CONTAINS, 5),  # 숫자는 담는 값이 아니다
        ("input.q", _O.CONTAINS, 1),  # 문자열은 문자열만 담는다
    ],
)
def test_incomparable_types_fail_as_a_type_mismatch(
    path: str, operator: ConditionOperator, value: Any
) -> None:
    with pytest.raises(ConditionFailure) as raised:
        evaluate_condition(_CONTEXT, path, operator, value)
    assert raised.value.reason is WorkflowFailureReason.CONDITION_TYPE_MISMATCH


def test_the_two_failure_reasons_are_distinct_values() -> None:
    assert WorkflowFailureReason.CONDITION_PATH_MISSING.value == "condition_path_missing"
    assert WorkflowFailureReason.CONDITION_TYPE_MISMATCH.value == "condition_type_mismatch"
    values = {
        WorkflowFailureReason.CONDITION_PATH_MISSING.value,
        WorkflowFailureReason.CONDITION_TYPE_MISMATCH.value,
    }
    assert len(values) == 2
