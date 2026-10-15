"""spec 0005 2.4 개정 4, C-3, D-8 (P4-2b): 노드 출력은 `data` 의 노드 실행 기록에만 두고
span·감사·보고에 나타나지 않으며, 출력을 읽는 곳은 `CONDITION` 하나뿐이다.

C-3 는 노드 출력을 "새 제품 표면" 이라 부르고 되돌리는 조건을 걸어 두었습니다. 되돌리기가 싸려면
**출력이 어디로 흘러가는지**가 코드에서 읽혀야 합니다. 문자열 검색은 docstring 의 설명 문장에
오탐하므로
(`test_execute_run_uses_context_compiler.py` 의 교훈) AST 로 **호출 인자**를 봅니다.

판정 둘:

1. 실행기(`advance_workflow_run.py`)에서 출력에서 파생된 값(출력을 만드는 함수의 반환, `.output`
   속성, 그 값에서 대입된 이름)이 **발행·통지·페이로드·로깅 호출의 인자**로 들어가지 않는다.
2. 출력을 읽는 속성(`.output`·`.output_truncated`)과 본문을 읽는 문(`last_assistant_text`)은
   제품 코드에서 정해진 자리에만 나타난다 - 소비자 목록이 고정된다.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = (
    REPO_ROOT
    / "packages"
    / "workflow"
    / "src"
    / "aether_workflow"
    / "application"
    / "usecases"
    / "advance_workflow_run.py"
)

# 출력(또는 그 재료)을 만들어 내는 호출
_PRODUCERS = frozenset({"agent_output", "last_assistant_text"})
# 출력을 읽는 속성
_OUTPUT_ATTRIBUTES = frozenset({"output", "output_truncated"})
# 실행기 밖으로 나가는 문 - 이벤트·통지·페이로드·로깅·표준 출력
_SINKS = frozenset(
    {
        "publish",
        "notify",
        "_publish",
        "_emit_node_event",
        "NodeStartedPayload",
        "NodeFinishedPayload",
        "WorkflowStatusPayload",
        "WorkflowFinishedPayload",
        "WorkflowStatusMessage",
        "WorkflowEvent",
        "model_dump",
        "print",
        "debug",
        "info",
        "warning",
        "error",
        "exception",
        "critical",
        "log",
        "set_attribute",
        "set_attributes",
        "add_event",
        "record_exception",
    }
)


def _callee(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _is_output_derived(expr: ast.AST, tainted: set[str]) -> bool:
    for node in ast.walk(expr):
        if isinstance(node, ast.Call) and _callee(node) in _PRODUCERS:
            return True
        if isinstance(node, ast.Attribute) and node.attr in _OUTPUT_ATTRIBUTES:
            return True
        if isinstance(node, ast.Name) and node.id in tainted:
            return True
    return False


def _tainted_names(function: ast.AST) -> set[str]:
    """출력에서 파생된 지역 이름 - 고정점까지 전파한다."""
    tainted: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(function):
            targets: list[ast.expr] = []
            value: ast.AST | None = None
            if isinstance(node, ast.Assign):
                targets, value = list(node.targets), node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            elif isinstance(node, ast.For):
                targets, value = [node.target], node.iter
            if value is None or not _is_output_derived(value, tainted):
                continue
            for target in targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name) and name.id not in tainted:
                        tainted.add(name.id)
                        changed = True
    return tainted


def output_leaks(source: str) -> list[str]:
    """출력에서 파생된 값이 `_SINKS` 호출의 인자로 들어가는 곳을 `함수:줄` 로 돌려준다."""
    leaks: list[str] = []
    for function in ast.walk(ast.parse(source)):
        if not isinstance(function, ast.FunctionDef):
            continue
        tainted = _tainted_names(function)
        for call in ast.walk(function):
            if not isinstance(call, ast.Call) or _callee(call) not in _SINKS:
                continue
            arguments = [*call.args, *(k.value for k in call.keywords)]
            if any(_is_output_derived(a, tainted) for a in arguments):
                leaks.append(f"{function.name}:{call.lineno} {_callee(call)}")
    return leaks


# --- 판정기 자체가 공허하지 않은지 (양성 대조) ----------------------------------------------


def test_the_detector_finds_a_direct_leak() -> None:
    bad = "def f(self, record):\n    self._sink.publish(record.output)\n"
    assert output_leaks(bad) == ["f:2 publish"]


def test_the_detector_follows_an_assignment_into_a_payload() -> None:
    bad = (
        "def f(self, run_id):\n"
        "    text = self._agent_runs.last_assistant_text(run_id)\n"
        "    shaped = agent_output(text or '', 'ok', 10)\n"
        "    NodeFinishedPayload(node_id='n', iteration=0, status=shaped).model_dump()\n"
    )
    assert output_leaks(bad) == ["f:4 NodeFinishedPayload"]


def test_the_detector_finds_a_log_call_and_ignores_a_store_write() -> None:
    bad = (
        "def f(self, node_execution_id, record):\n"
        "    out = agent_output('x', 'ok', 10)\n"
        "    self._store.finish_node(node_execution_id, 1, 2, None, out)\n"
        "    logger.info('done %s', out)\n"
    )
    assert output_leaks(bad) == ["f:4 info"]


# --- 판정 1: 실행기는 출력을 밖으로 내보내지 않는다 ---------------------------------------


def test_the_executor_never_passes_output_to_an_event_a_notification_or_a_log() -> None:
    leaks = output_leaks(EXECUTOR.read_text(encoding="utf-8"))
    assert leaks == [], (
        "노드 출력이 이벤트·통지·로그로 흘러갑니다(spec 0005 2.4: 출력은 data 에만 둔다, "
        f"span·감사·보고에는 넣지 않는다): {leaks}"
    )


def test_the_workflow_package_has_no_tracing_or_logging_import() -> None:
    """실행기 쪽에는 출력이 흘러 들어갈 수 있는 관측 도구 자체가 없다 (trace context 는 worker
    의 `OtelTraceContext` 가 감싼다)."""
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "packages" / "workflow" / "src").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                modules = [node.module]
            offenders += [
                f"{path.name}: {m}"
                for m in modules
                if m.split(".")[0] in {"logging", "opentelemetry", "structlog"}
            ]
    assert offenders == []


def test_event_payload_models_have_no_output_field() -> None:
    """페이로드 모델의 필드 이름 수준에서도 출력이 들어갈 자리가 없다."""
    from aether_workflow.application.ports.outbound.workflow_status_notifier import (
        WorkflowStatusMessage,
    )
    from aether_workflow.domain import events

    names: set[str] = set(WorkflowStatusMessage.model_fields)
    for model in (
        events.NodeStartedPayload,
        events.NodeFinishedPayload,
        events.WorkflowStatusPayload,
        events.WorkflowFinishedPayload,
    ):
        names |= set(model.model_fields)
    assert not {n for n in names if "output" in n or n in {"text", "body", "content"}}


# --- 판정 2: 출력을 읽는 곳은 한 곳이다 ------------------------------------------------------


def _attribute_reads(path: Path) -> list[tuple[str, str]]:
    """`(함수 이름, 속성)` - 출력 속성을 **읽는** 곳(대입 대상 제외)."""
    reads: list[tuple[str, str]] = []
    for function in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Attribute)
                and node.attr in _OUTPUT_ATTRIBUTES
                and isinstance(node.ctx, ast.Load)
            ):
                reads.append((function.name, node.attr))
    return reads


def _product_sources() -> list[Path]:
    roots = [
        REPO_ROOT / "packages" / "workflow" / "src",
        REPO_ROOT / "apps" / "api" / "src",
        REPO_ROOT / "apps" / "worker" / "src",
    ]
    return sorted(p for root in roots for p in root.rglob("*.py"))


def test_node_output_is_read_by_exactly_one_consumer_the_condition_context() -> None:
    """C-3: 출력의 소비자는 `CONDITION` 하나다. 세 번째 소비자(조회 API, 보고)가 생기면 이 목록이
    바뀌고, 그것이 되돌릴 때 뜯어야 할 곳의 전부다."""
    reads = {
        (path.name, function, attribute)
        for path in _product_sources()
        for function, attribute in _attribute_reads(path)
    }
    assert reads == {("advance_workflow_run.py", "_condition_context", "output")}


def test_the_assistant_text_is_read_only_by_the_executor() -> None:
    callers = {
        path.name
        for path in _product_sources()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and _callee(node) == "last_assistant_text"
    }
    assert callers == {"advance_workflow_run.py"}


def test_the_api_never_touches_the_node_execution_output() -> None:
    """api 역할은 `data` 에 권한이 없다(0001 R-7) - 코드에서도 그 표를 이름으로 부르지 않는다."""
    offenders = [
        p.name
        for p in (REPO_ROOT / "apps" / "api" / "src").rglob("*.py")
        if "workflow_node_executions" in ast.dump(ast.parse(p.read_text(encoding="utf-8")))
    ]
    assert offenders == []
