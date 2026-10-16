"""spec 0005 2.8 개정 9 (3)(4)(5), R-1, R-2 (P4-5): `LLM`·`TOOL`·`MCP` 노드의 도메인 -
직렬화·저장 때 거부·입력 조립·출력 모양. I/O 없는 순수 함수(AR-9)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from aether_workflow.domain.condition import ConditionFailure
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_input import build_arguments, build_prompt
from aether_workflow.domain.node_output import llm_output, serialized_size, tool_output
from aether_workflow.domain.serialization import serialize_version
from aether_workflow.domain.validation import Reason, Violation, validate_version
from aether_workflow.domain.workflow_version import WorkflowVersion

_AGENT = UUID("00000000-0000-0000-0000-0000000000a1")


def _version(*middle: Node) -> WorkflowVersion:
    nodes = (Node("s", NodeKind.START), *middle, Node("e", NodeKind.END))
    ids = [n.id for n in nodes]
    return WorkflowVersion(
        number=1, nodes=nodes, edges=tuple(Edge(a, b) for a, b in zip(ids, ids[1:], strict=False))
    )


def _bytes(node: Node) -> bytes:
    return serialize_version(_version(node))


# --- 직렬화 (R-2): 키마다 바이트가 바뀐다 ----------------------------------------------------

_LLM = Node("n", NodeKind.LLM, llm_prompt="p")
_TOOL = Node(
    "n",
    NodeKind.TOOL,
    agent_id=_AGENT,
    tool_server="builtin",
    tool_name="clock",
    tool_arguments={"a": 1},
    tool_arguments_path="input.args",
)


@pytest.mark.parametrize(
    ("base", "changed"),
    [
        (_LLM, Node("n", NodeKind.LLM, llm_prompt="other")),
        (_LLM, Node("n", NodeKind.LLM, llm_prompt="p", llm_prompt_path="input.x")),
        (_TOOL, Node(**{**_TOOL.__dict__, "tool_server": "other"})),
        (_TOOL, Node(**{**_TOOL.__dict__, "tool_name": "calculator"})),
        (_TOOL, Node(**{**_TOOL.__dict__, "tool_arguments": {"a": 2}})),
        (_TOOL, Node(**{**_TOOL.__dict__, "tool_arguments": None})),
        (_TOOL, Node(**{**_TOOL.__dict__, "tool_arguments_path": "input.other"})),
        (_TOOL, Node(**{**_TOOL.__dict__, "tool_arguments_path": None})),
    ],
)
def test_every_new_node_key_changes_the_serialized_bytes(base: Node, changed: Node) -> None:
    """spec 0005 R-2: 직렬화에서 빠진 키가 있으면 두 정의가 같은 바이트를 낸다."""
    assert _bytes(base) != _bytes(changed)


def test_argument_key_order_does_not_change_the_serialized_bytes() -> None:
    """spec 0005 R-2: 인자 객체의 키 순서에 기대지 않는다."""
    a = Node("n", NodeKind.TOOL, agent_id=_AGENT, tool_arguments={"a": 1, "b": 2})
    b = Node("n", NodeKind.TOOL, agent_id=_AGENT, tool_arguments={"b": 2, "a": 1})
    assert _bytes(a) == _bytes(b)


# --- 저장 때 거부 (개정 9 (4)) ------------------------------------------------------------


def test_llm_node_without_prompt_is_rejected() -> None:
    """spec 0005 2.8 개정 9 (4): 프롬프트 리터럴이 없는 `LLM` 은 `llm_node_without_prompt`."""
    violations = validate_version(_version(Node("n", NodeKind.LLM)))
    assert violations == (Violation(Reason.LLM_NODE_WITHOUT_PROMPT, "n"),)


def test_llm_node_with_blank_prompt_is_rejected() -> None:
    """spec 0005 2.8 개정 9 (4): 빈 문자열은 없는 것과 같다."""
    violations = validate_version(_version(Node("n", NodeKind.LLM, llm_prompt="")))
    assert [v.reason for v in violations] == [Reason.LLM_NODE_WITHOUT_PROMPT]


def test_llm_node_with_prompt_is_accepted() -> None:
    """spec 0005 2.8 개정 9 (4)."""
    assert validate_version(_version(_LLM)) == ()


@pytest.mark.parametrize("kind", [NodeKind.TOOL, NodeKind.MCP])
@pytest.mark.parametrize(
    "missing", [{"tool_server": None}, {"tool_name": None}, {"tool_server": "", "tool_name": ""}]
)
def test_tool_and_mcp_node_without_server_or_name_is_rejected(
    kind: NodeKind, missing: dict[str, Any]
) -> None:
    """spec 0005 2.8 개정 9 (4): 서버 또는 도구 이름이 없으면 `tool_node_without_target`."""
    node = Node(**{**_TOOL.__dict__, "kind": kind, **missing})
    violations = validate_version(_version(node))
    assert violations == (Violation(Reason.TOOL_NODE_WITHOUT_TARGET, "n"),)


@pytest.mark.parametrize("kind", [NodeKind.TOOL, NodeKind.MCP])
def test_tool_and_mcp_node_without_agent_reuses_agent_node_without_agent(kind: NodeKind) -> None:
    """spec 0005 2.8 개정 9 (4): Agent 참조가 없으면 **기존** 사유를 재사용한다."""
    node = Node(**{**_TOOL.__dict__, "kind": kind, "agent_id": None})
    violations = validate_version(_version(node))
    assert violations == (Violation(Reason.AGENT_NODE_WITHOUT_AGENT, "n"),)


@pytest.mark.parametrize("kind", [NodeKind.TOOL, NodeKind.MCP])
def test_a_fully_specified_tool_node_is_accepted(kind: NodeKind) -> None:
    """spec 0005 2.8 개정 9 (4)."""
    assert validate_version(_version(Node(**{**_TOOL.__dict__, "kind": kind}))) == ()


def test_tool_keys_on_other_kinds_are_ignored() -> None:
    """spec 0005 2.2 개정 3 의 규칙 그대로: 다른 종류의 노드에 있는 값은 거부하지 않고 무시."""
    node = Node("n", NodeKind.AGENT, agent_id=_AGENT, tool_server="x", llm_prompt="y")
    assert validate_version(_version(node)) == ()


# --- 입력 조립 (개정 9 (3)) ---------------------------------------------------------------

_CTX: dict[str, Any] = {"input": {"s": "doc", "n": 7, "o": {"b": 3, "c": 4}}, "nodes": {}}


def test_prompt_without_a_path_is_the_literal() -> None:
    """spec 0005 2.8 개정 9 (3)."""
    assert build_prompt("hi", None, _CTX) == "hi"


def test_prompt_appends_a_string_value_after_a_newline() -> None:
    """spec 0005 2.8 개정 9 (3): 뒤에 덧붙인다."""
    assert build_prompt("hi", "input.s", _CTX) == "hi\ndoc"


def test_prompt_appends_a_non_string_value_as_json() -> None:
    """spec 0005 2.8 개정 9 (3): 문자열이 아니면 JSON 직렬화."""
    assert build_prompt("hi", "input.n", _CTX) == "hi\n7"
    assert build_prompt("hi", "input.o", _CTX) == 'hi\n{"b": 3, "c": 4}'


def test_prompt_missing_path_is_condition_path_missing() -> None:
    """spec 0005 2.8 개정 9 (3): 없는 경로는 `CONDITION` 과 같은 규칙."""
    with pytest.raises(ConditionFailure) as raised:
        build_prompt("hi", "input.nope", _CTX)
    assert raised.value.reason is WorkflowFailureReason.CONDITION_PATH_MISSING


def test_arguments_without_anything_is_an_empty_object() -> None:
    """spec 0005 2.8 개정 9 (3)."""
    assert build_arguments(None, None, _CTX) == {}


def test_arguments_merge_lets_the_path_value_win_and_does_not_mutate_the_literal() -> None:
    """spec 0005 2.8 개정 9 (3): 경로 값이 이긴다. 리터럴(노드 정의)은 바뀌지 않는다."""
    literal = {"a": 1, "b": 2}
    assert build_arguments(literal, "input.o", _CTX) == {"a": 1, "b": 3, "c": 4}
    assert literal == {"a": 1, "b": 2}


def test_arguments_path_to_a_non_object_is_a_type_mismatch() -> None:
    """spec 0005 2.8 개정 9 (3): 병합할 수 없는 값은 `condition_type_mismatch`."""
    with pytest.raises(ConditionFailure) as raised:
        build_arguments({"a": 1}, "input.s", _CTX)
    assert raised.value.reason is WorkflowFailureReason.CONDITION_TYPE_MISMATCH


def test_arguments_missing_path_is_condition_path_missing() -> None:
    """spec 0005 2.8 개정 9 (3)."""
    with pytest.raises(ConditionFailure) as raised:
        build_arguments({"a": 1}, "input.nope", _CTX)
    assert raised.value.reason is WorkflowFailureReason.CONDITION_PATH_MISSING


# --- 출력 모양과 상한 (개정 9 (5)) ----------------------------------------------------------


def test_llm_output_shape_and_untruncated() -> None:
    """spec 0005 2.8 개정 9 (5)."""
    out = llm_output("hello", "stop", 8192)
    assert out.value == {"text": "hello", "finish_reason": "stop"}
    assert out.truncated is False


def test_tool_output_shape_and_untruncated() -> None:
    """spec 0005 2.8 개정 9 (5)."""
    out = tool_output("4", False, 8192)
    assert out.value == {"content": "4", "is_error": False}
    assert out.truncated is False


@pytest.mark.parametrize("limit", [40, 64, 200])
def test_llm_output_is_cut_to_the_byte_limit_with_the_flag(limit: int) -> None:
    """spec 0005 2.4 개정 4 (4): 상한은 직렬화된 UTF-8 바이트, 자르면 잘림 표시."""
    out = llm_output("가" * 500, "stop", limit)
    assert out.truncated is True
    assert serialized_size(out.value) <= limit
    assert out.value["finish_reason"] == "stop"
    assert out.value["text"].startswith("가")


@pytest.mark.parametrize("limit", [40, 64, 200])
def test_tool_output_is_cut_to_the_byte_limit_and_keeps_is_error(limit: int) -> None:
    """spec 0005 2.4 개정 4 (4): 판정에 쓰이는 `is_error` 는 줄이지 않는다."""
    out = tool_output("x" * 500, True, limit)
    assert out.truncated is True
    assert serialized_size(out.value) <= limit
    assert out.value["is_error"] is True
