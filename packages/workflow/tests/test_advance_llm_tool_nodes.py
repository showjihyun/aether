"""spec 0005 2.8 개정 9, R-14 (P4-5): `LLM`·`TOOL`·`MCP` 노드 - fake 포트로, 컨테이너 없이(AR-9).

증명하는 것: 세 종류는 **파킹하지 않고** 한 번 부르고 끝난다 / 프롬프트는 경로 값을 뒤에 덧붙이고
인자는 병합한다(경로 값이 이긴다) / 없는 경로·객체가 아닌 인자 경로는 호출 **전에** 실패한다 /
`TOOL`·`MCP` 는 `agent_id` 가 가리키는 Version 의 권한으로 부른다(없으면 호출하지 않는다) /
도구 결과의 `is_error`·거부·호출 예외·모델 예외는 각각 구별되는 사유로 노드가 실패한다 / 출력은
P4-2b 의 상한과 잘림 표시를 받는다 / `CONDITION` 이 그 출력으로 분기한다 / 이미 마친 노드는
다시 부르지 않는다 / 포트가 꽂히지 않은 종류는 `unsupported_node_kind`.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from aether_workflow.application.ports.outbound.model_invoker import ModelAnswer
from aether_workflow.application.ports.outbound.tool_invoker import (
    ToolInvocationDenied,
    ToolInvocationFailed,
    ToolOutcome,
)
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from aether_workflow.domain.condition import ConditionOperator
from aether_workflow.domain.failure import WorkflowFailureReason
from aether_workflow.domain.node import Edge, Node, NodeKind
from aether_workflow.domain.node_execution import NodeExecutionRecord, NodeExecutionStatus
from aether_workflow.domain.run_status import WorkflowRunStatus

from packages.workflow.tests.fakes import (
    REQUESTER,
    FakeAgentRunLauncher,
    FakeAgentRunReader,
    FakeApprovalReader,
    FakeWorkflowClock,
    FakeWorkflowEventSink,
    FakeWorkflowModelInvoker,
    FakeWorkflowRunDeclarationReader,
    FakeWorkflowRunStateStore,
    FakeWorkflowStatusNotifier,
    FakeWorkflowToolInvoker,
)

_AGENT = UUID("00000000-0000-0000-0000-0000000000a1")


class _Rig:
    def __init__(
        self,
        *,
        output_max_bytes: int = 8192,
        models: FakeWorkflowModelInvoker | None = None,
        tools: FakeWorkflowToolInvoker | None = None,
        wire: bool = True,
    ) -> None:
        self.store = FakeWorkflowRunStateStore()
        self.reader = FakeWorkflowRunDeclarationReader()
        self.sink = FakeWorkflowEventSink()
        self.notifier = FakeWorkflowStatusNotifier()
        self.agent_runs = FakeAgentRunReader()
        self.models = models or FakeWorkflowModelInvoker()
        self.tools = tools or FakeWorkflowToolInvoker()
        self.version = self.agent_runs.add_version(_AGENT, None)
        self.pinned = self.agent_runs.add_version(_AGENT, 3)
        self.advance = AdvanceWorkflowRunUseCase(
            self.store,
            self.reader,
            self.sink,
            self.notifier,
            FakeWorkflowClock(),
            agent_runs=self.agent_runs,
            approvals=FakeApprovalReader(),
            launcher=FakeAgentRunLauncher(self.store),
            owner="worker-a",
            lease_ttl_seconds=60.0,
            output_max_bytes=output_max_bytes,
            models=self.models if wire else None,
            tools=self.tools if wire else None,
        )

    def chain(self, *middle: Node, input: dict[str, Any] | None = None) -> UUID:
        nodes = (Node("start", NodeKind.START), *middle, Node("end", NodeKind.END))
        ids = [n.id for n in nodes]
        edges = tuple(Edge(a, b) for a, b in zip(ids, ids[1:], strict=False))
        return self.reader.add(nodes, edges, input=input, requested_by=REQUESTER)

    def record(self, run_id: UUID, node_id: str) -> NodeExecutionRecord:
        (record,) = (r for r in self.store.node_executions(run_id) if r.node_id == node_id)
        return record


def _llm(node_id: str = "ask", **kw: Any) -> Node:
    return Node(node_id, NodeKind.LLM, **{"llm_prompt": "say hi", **kw})


def _tool(node_id: str = "calc", kind: NodeKind = NodeKind.TOOL, **kw: Any) -> Node:
    return Node(
        node_id,
        kind,
        **{
            "agent_id": _AGENT,
            "tool_server": "builtin",
            "tool_name": "calculator",
            "tool_arguments": {"expression": "2+2"},
            **kw,
        },
    )


# --- LLM ----------------------------------------------------------------------------------


def test_llm_node_calls_the_model_once_and_the_run_succeeds_without_parking() -> None:
    """spec 0005 2.8 개정 9 (5): 한 번 부르고 끝난다 - 자식 Run 도 파킹도 없다."""
    rig = _Rig()
    run_id = rig.chain(_llm())

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert rig.models.calls == [("say hi", None)]
    assert rig.record(run_id, "ask").agent_run_id is None
    statuses = [e.payload.get("status") for e in rig.sink.events if e.type == "workflow.status"]
    assert all(s in {"running", "succeeded"} for s in statuses)


def test_llm_output_is_text_and_finish_reason() -> None:
    """spec 0005 2.8 개정 9 (5): `LLM` 의 출력은 `{"text", "finish_reason"}`."""
    rig = _Rig(models=FakeWorkflowModelInvoker(ModelAnswer(text="hello", finish_reason="length")))
    run_id = rig.chain(_llm())

    rig.advance(run_id)

    record = rig.record(run_id, "ask")
    assert record.status is NodeExecutionStatus.SUCCEEDED
    assert record.output == {"text": "hello", "finish_reason": "length"}
    assert record.output_truncated is False


@pytest.mark.parametrize(
    ("value", "expected_tail"),
    [("ctx", "ctx"), (42, "42"), ({"k": "v"}, '{"k": "v"}')],
)
def test_llm_prompt_path_value_is_appended_after_the_literal(
    value: object, expected_tail: str
) -> None:
    """spec 0005 2.8 개정 9 (3): 프롬프트는 경로 값을 **뒤에 덧붙인다**. 문자열 아니면 JSON."""
    rig = _Rig()
    run_id = rig.chain(_llm(llm_prompt_path="input.doc"), input={"doc": value})

    rig.advance(run_id)

    assert rig.models.calls == [(f"say hi\n{expected_tail}", None)]


def test_llm_prompt_path_can_point_at_an_earlier_node_output() -> None:
    """spec 0005 2.8 개정 9 (3): 경로는 `CONDITION` 과 같은 맥락(`nodes.<id>`)을 가리킨다."""
    rig = _Rig()
    run_id = rig.chain(
        _llm("first", llm_prompt="one"), _llm("second", llm_prompt_path="nodes.first.text")
    )

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert [c[0] for c in rig.models.calls] == ["one", "say hi\necho"]


def test_llm_missing_prompt_path_fails_the_node_before_calling_the_model() -> None:
    """spec 0005 2.8 개정 9 (3): 없는 경로는 `CONDITION` 과 같은 규칙 - 시끄럽게 실패."""
    rig = _Rig()
    run_id = rig.chain(_llm(llm_prompt_path="input.nope"), input={"doc": "x"})

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.models.calls == []
    record = rig.record(run_id, "ask")
    assert record.status is NodeExecutionStatus.FAILED
    assert record.failure_reason == WorkflowFailureReason.CONDITION_PATH_MISSING.value


def test_llm_model_exception_fails_the_node_with_model_call_failed() -> None:
    """spec 0005 2.8 개정 9 (5) / 실행기 4: 모델 호출이 예외를 내면 노드 실패."""
    rig = _Rig(models=FakeWorkflowModelInvoker(fail_with=ConnectionError("down")))
    run_id = rig.chain(_llm())

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.record(run_id, "ask").failure_reason == "model_call_failed"
    assert rig.store.executions[run_id].failure_reason == "model_call_failed"


def test_llm_output_is_capped_with_the_truncation_flag() -> None:
    """spec 0005 2.4 개정 4 (4), 2.8 개정 9 (5): P4-2b 의 상한과 잘림 표시를 그대로 받는다."""
    rig = _Rig(
        output_max_bytes=64,
        models=FakeWorkflowModelInvoker(ModelAnswer(text="가" * 500, finish_reason="stop")),
    )
    run_id = rig.chain(_llm())

    rig.advance(run_id)

    record = rig.record(run_id, "ask")
    assert record.output_truncated is True
    assert record.output is not None
    assert record.output["finish_reason"] == "stop"
    assert len(record.output["text"]) < 500
    assert len(str(record.output).encode("utf-8")) < 200


# --- TOOL / MCP ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", [NodeKind.TOOL, NodeKind.MCP])
def test_tool_and_mcp_nodes_call_with_the_agent_versions_authority(kind: NodeKind) -> None:
    """spec 0005 2.8 개정 9 (1)(2): 두 종류는 같다. 권한 주체는 `agent_id` 의 최신 Version."""
    rig = _Rig()
    run_id = rig.chain(_tool(kind=kind))

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert rig.tools.calls == [
        (run_id, rig.version.agent_version_id, "builtin", "calculator", {"expression": "2+2"})
    ]
    record = rig.record(run_id, "calc")
    assert record.output == {"content": "4", "is_error": False}
    assert record.agent_run_id is None


def test_tool_node_pinned_agent_version_is_resolved_through_the_reader() -> None:
    """spec 0005 2.8 개정 9 (1): `agent_version` 이 있으면 그 Version - `version_for` 사용."""
    rig = _Rig()
    run_id = rig.chain(_tool(agent_version=3))

    rig.advance(run_id)

    assert rig.agent_runs.version_lookups == [(_AGENT, 3)]
    assert rig.tools.calls[0][1] == rig.pinned.agent_version_id


def test_tool_node_without_a_resolvable_version_fails_without_calling() -> None:
    """spec 0005 2.8 개정 9 (1): Version 이 없으면 노드 실패 + 기존 사유."""
    rig = _Rig()
    run_id = rig.chain(_tool(agent_version=99))

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.tools.calls == []
    assert rig.record(run_id, "calc").failure_reason == "agent_version_not_found"


def test_tool_arguments_path_object_is_merged_over_the_literal() -> None:
    """spec 0005 2.8 개정 9 (3): 인자는 **병합**한다 - 경로 값이 이긴다."""
    rig = _Rig()
    run_id = rig.chain(
        _tool(
            tool_arguments={"a": 1, "b": 2},
            tool_arguments_path="input.args",
        ),
        input={"args": {"b": 3, "c": 4}},
    )

    rig.advance(run_id)

    assert rig.tools.calls[0][4] == {"a": 1, "b": 3, "c": 4}


def test_tool_arguments_path_alone_is_enough() -> None:
    """spec 0005 2.8 개정 9 (3): 리터럴 인자는 선택이다."""
    rig = _Rig()
    run_id = rig.chain(
        _tool(tool_arguments=None, tool_arguments_path="input.args"),
        input={"args": {"expression": "1+1"}},
    )

    rig.advance(run_id)

    assert rig.tools.calls[0][4] == {"expression": "1+1"}


def test_tool_node_without_any_arguments_calls_with_an_empty_object() -> None:
    """spec 0005 2.8 개정 9 (3): 둘 다 없으면 빈 객체."""
    rig = _Rig()
    run_id = rig.chain(_tool(tool_arguments=None))

    rig.advance(run_id)

    assert rig.tools.calls[0][4] == {}


def test_tool_arguments_path_that_is_not_an_object_fails_before_the_call() -> None:
    """spec 0005 2.8 개정 9 (3): 병합할 수 없는 값은 노드 실패(`condition_type_mismatch` 재사용)."""
    rig = _Rig()
    run_id = rig.chain(_tool(tool_arguments_path="input.args"), input={"args": [1, 2]})

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.tools.calls == []
    assert rig.record(run_id, "calc").failure_reason == "condition_type_mismatch"


def test_tool_arguments_missing_path_fails_before_the_call() -> None:
    """spec 0005 2.8 개정 9 (3): 없는 경로는 `condition_path_missing`."""
    rig = _Rig()
    run_id = rig.chain(_tool(tool_arguments_path="input.nope"), input={"args": {}})

    rig.advance(run_id)

    assert rig.tools.calls == []
    assert rig.record(run_id, "calc").failure_reason == "condition_path_missing"


def test_tool_result_with_is_error_fails_the_node_but_keeps_the_output() -> None:
    """spec 0005 2.8 개정 9 (5) / 실행기 4: `is_error` 는 노드 실패(`tool_call_failed`)."""
    rig = _Rig(tools=FakeWorkflowToolInvoker(ToolOutcome(content="boom", is_error=True)))
    run_id = rig.chain(_tool())

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    record = rig.record(run_id, "calc")
    assert record.status is NodeExecutionStatus.FAILED
    assert record.failure_reason == "tool_call_failed"
    assert record.output == {"content": "boom", "is_error": True}
    assert rig.store.executions[run_id].failure_reason == "tool_call_failed"


def test_denied_tool_call_fails_the_node_with_its_own_reason() -> None:
    """spec 0005 2.8 개정 9 (1), AR-6: 기본 deny - 조용히 넘어가지 않고 `tool_call_denied`."""
    rig = _Rig(tools=FakeWorkflowToolInvoker(fail_with=ToolInvocationDenied("builtin/calculator")))
    run_id = rig.chain(_tool())

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.record(run_id, "calc").failure_reason == "tool_call_denied"


@pytest.mark.parametrize("error", [ToolInvocationFailed("x"), RuntimeError("x")])
def test_tool_call_exception_fails_the_node_with_tool_call_failed(error: Exception) -> None:
    """spec 0005 2.8 개정 9 / 실행기 4: 호출이 실패(없는 도구·연결 실패 포함)하면 노드 실패."""
    rig = _Rig(tools=FakeWorkflowToolInvoker(fail_with=error))
    run_id = rig.chain(_tool())

    rig.advance(run_id)

    assert rig.record(run_id, "calc").failure_reason == "tool_call_failed"


def test_tool_output_is_capped_with_the_truncation_flag() -> None:
    """spec 0005 2.4 개정 4 (4), 2.8 개정 9 (5): 도구 출력도 같은 상한."""
    rig = _Rig(
        output_max_bytes=64,
        tools=FakeWorkflowToolInvoker(ToolOutcome(content="x" * 1000, is_error=False)),
    )
    run_id = rig.chain(_tool())

    rig.advance(run_id)

    record = rig.record(run_id, "calc")
    assert record.output_truncated is True
    assert record.output is not None
    assert record.output["is_error"] is False
    assert len(record.output["content"]) < 1000


# --- 맥락 / 멱등 / 배선 ----------------------------------------------------------------------


def test_condition_branches_on_an_llm_output() -> None:
    """spec 0005 2.8 개정 9 (5): `CONDITION` 이 그 출력으로 분기할 수 있다."""
    rig = _Rig(models=FakeWorkflowModelInvoker(ModelAnswer(text="yes", finish_reason="stop")))
    nodes = (
        Node("start", NodeKind.START),
        _llm(),
        Node(
            "cond",
            NodeKind.CONDITION,
            condition_path="nodes.ask.text",
            condition_operator=ConditionOperator.EQUALS,
            condition_value="yes",
        ),
        Node("end_true", NodeKind.END),
        Node("end_false", NodeKind.END),
    )
    edges = (
        Edge("start", "ask"),
        Edge("ask", "cond"),
        Edge("cond", "end_true", "true"),
        Edge("cond", "end_false", "false"),
    )
    run_id = rig.reader.add(nodes, edges, requested_by=REQUESTER)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert rig.store.executions[run_id].current_node_id == "end_true"


def test_a_node_already_finished_is_not_called_again() -> None:
    """R-6, R-8: 기록이 이미 마쳤다고 말하면 모델·도구를 다시 부르지 않는다."""
    rig = _Rig()
    run_id = rig.chain(_llm(), _tool())
    rig.store.seed(run_id, status=WorkflowRunStatus.RUNNING, status_seq=3, current_node_id="start")
    rig.store.seed_node(run_id, "start", NodeExecutionStatus.SUCCEEDED)
    rig.store.seed_node(
        run_id, "ask", NodeExecutionStatus.SUCCEEDED, output={"text": "t", "finish_reason": "stop"}
    )
    rig.store.seed_node(
        run_id, "calc", NodeExecutionStatus.SUCCEEDED, output={"content": "4", "is_error": False}
    )

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.SUCCEEDED
    assert rig.models.calls == []
    assert rig.tools.calls == []


def test_node_events_carry_no_output_and_no_prompt() -> None:
    """spec 0005 2.4, C-3: 이벤트에는 출력도 프롬프트도 도구 인자도 없다."""
    rig = _Rig(
        models=FakeWorkflowModelInvoker(ModelAnswer(text="SECRET-ANSWER", finish_reason="stop")),
        tools=FakeWorkflowToolInvoker(ToolOutcome(content="SECRET-RESULT", is_error=False)),
    )
    run_id = rig.chain(_llm(llm_prompt="SECRET-PROMPT"), _tool(tool_arguments={"k": "SECRET-ARG"}))

    rig.advance(run_id)

    dumped = repr([e.payload for e in rig.sink.events]) + repr(
        [m.model_dump() for m in rig.notifier.messages]
    )
    for secret in ("SECRET-ANSWER", "SECRET-RESULT", "SECRET-PROMPT", "SECRET-ARG"):
        assert secret not in dumped


@pytest.mark.parametrize("kind", [NodeKind.LLM, NodeKind.TOOL, NodeKind.MCP])
def test_a_kind_without_its_port_wired_is_unsupported(kind: NodeKind) -> None:
    """포트가 꽂히지 않은 종류는 절반만 만든 노드를 두지 않고 `unsupported_node_kind`."""
    rig = _Rig(wire=False)
    node = _llm() if kind is NodeKind.LLM else _tool(kind=kind)
    run_id = rig.chain(node)

    status = rig.advance(run_id)

    assert status is WorkflowRunStatus.FAILED
    assert rig.store.executions[run_id].failure_reason == "unsupported_node_kind"
