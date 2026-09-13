"""spec 0002 2.4, 2.6, D-5, D-6, D-10, D-11, R-14, R-15, R-16: `ExecuteRunUseCase` —
Planner/Executor 루프. `ExecuteRun`(inbound 포트) 의 유일한 구현입니다.

이 유스케이스는 이 단위(P1-4)에서 재시도·타임아웃을 하지 않습니다(P1-7 이 더합니다) —
모델 오류는 즉시 `failed(model_error)`, 도구 예외는 즉시 `failed(tool_error)`.

**전이와 종결(2.4).** 상태 기계는 `domain.run.transition` 이 소유합니다 — `queued` 에서
집었을 때 `cancel_requested_at` 이 이미 있으면 `running` 을 거치지 않고 **직접**
`cancelled` 로 갑니다(전이표, 리뷰 A). 그 밖의 실패(`definition_invalid` 포함)는
`queued -> running -> failed` 순서를 지킵니다 — `running` 이 아니면 그 전이가 전이표에
없기 때문입니다. 종결 순서는 `RunState` **저장(커밋)** → `set_status`(커밋) → lease
`release` → `StatusNotifier.notify` → `EventSink.publish(run.status)` →
`EventSink.publish(run.finished)` → 반환입니다(리뷰 B) — `save` 가 `set_status` 보다
먼저 끝나야, 그 두 커밋 사이에 죽어도 저장된 스냅숏이 이미 종결(`status`·
`failure_reason`·`started_at`/`finished_at`·`last_seq` 전부 최종값)이라 재개
(`__call__`)가 그 스냅숏을 정본으로 커밋을 마저 끝낼 수 있습니다. 반대 순서였다면
그 사이에 죽었을 때 `status()` 는 종결인데 스냅숏은 아니라서 알 수 없는 상태가
됩니다. 커밋이 전부 끝난 뒤에만 통지·발행을 하므로, 그 뒤에 죽어도
재개(`_republish_terminal`)가 저장된 `RunState` 만 보고 같은 `seq` 로 다시
통지·발행할 수 있습니다(R-16).

**`Observation` 경계(R-14, D-6).** 도구 결과는 `render_observation` 이 만든 표지 문자열로만
`role="tool"` 메시지에 실립니다 — system·user 메시지에는 어떤 도구 출력도 섞이지 않습니다.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ValidationError

from aether_runtime.application.ports.outbound.clock import Clock
from aether_runtime.application.ports.outbound.event_sink import EventSink
from aether_runtime.application.ports.outbound.model_gateway import (
    ModelError,
    ModelGateway,
    ModelRequest,
    ToolSchema,
)
from aether_runtime.application.ports.outbound.run_declaration_reader import (
    RunDeclaration,
    RunDeclarationReader,
)
from aether_runtime.application.ports.outbound.run_state_store import RunStateStore
from aether_runtime.application.ports.outbound.status_notifier import (
    StatusMessage,
    StatusNotifier,
)
from aether_runtime.application.ports.outbound.tools import ToolRegistry
from aether_runtime.application.ports.outbound.tracer import Tracer
from aether_runtime.domain.agent import AgentDefinition
from aether_runtime.domain.events import (
    EventType,
    ModelCompletedPayload,
    RunEvent,
    RunFinishedPayload,
    RunStatusPayload,
    TaskFinishedPayload,
    TaskStartedPayload,
    ToolCalledPayload,
    ToolResultPayload,
)
from aether_runtime.domain.failure import FailureReason
from aether_runtime.domain.observation import Observation, render_observation
from aether_runtime.domain.run import (
    LeaseHeld,
    Message,
    RunState,
    RunStatus,
    is_terminal,
    transition,
)
from aether_runtime.domain.task import Task
from aether_runtime.domain.tools import ToolCall

_DEFAULT_LEASE_TTL_SECONDS = 60.0
_DEFAULT_OBSERVATION_MAX_CHARS = 16_000


class ExecuteRunUseCase:
    """`ExecuteRun` 의 구현(spec 0002 2.1, 2.4, 2.6). worker 가 부르는 유일한 문입니다."""

    def __init__(
        self,
        store: RunStateStore,
        declarations: RunDeclarationReader,
        gateway: ModelGateway,
        tools: ToolRegistry,
        events: EventSink,
        notifier: StatusNotifier,
        tracer: Tracer,
        clock: Clock,
        *,
        owner: str,
        lease_ttl_seconds: float = _DEFAULT_LEASE_TTL_SECONDS,
        observation_max_chars: int = _DEFAULT_OBSERVATION_MAX_CHARS,
    ) -> None:
        self._store = store
        self._declarations = declarations
        self._gateway = gateway
        self._tools = tools
        self._events = events
        self._notifier = notifier
        self._tracer = tracer
        self._clock = clock
        self._owner = owner
        self._lease_ttl_seconds = lease_ttl_seconds
        self._observation_max_chars = observation_max_chars

    def __call__(self, run_id: UUID) -> RunStatus:
        current_status = self._store.status(run_id)
        if current_status is not None and is_terminal(current_status):
            return self._republish_terminal(run_id, current_status)

        # 리뷰 B, R-16: 종결은 두 개의 커밋(`save(state)` 먼저, `set_status` 다음)으로
        # 이루어집니다 — 그 사이에 죽으면 `status()` 는 아직 비종결인데 저장된
        # 스냅숏은 이미 종결입니다. 그 스냅숏을 정본으로 커밋을 마저 끝냅니다. 이
        # 분기는 lease 를 잡지 않습니다 — 이미 끝난 실행이므로 실행 권한이 필요 없고,
        # 원래 owner 가 아닌 다른 worker 가 재시도해도 됩니다.
        saved = self._store.load(run_id)
        if saved is not None and is_terminal(saved.status):
            return self._republish_terminal(run_id, state=saved, commit_pending=True)

        if not self._store.acquire_lease(run_id, self._owner, self._lease_ttl_seconds):
            raise LeaseHeld(run_id)

        declaration = self._declarations.declaration(run_id)
        if declaration is None:
            raise RuntimeError(f"no run declaration found for run {run_id}")

        with self._tracer.span(
            "run",
            {
                "aether.run_id": str(run_id),
                "aether.agent_version_id": str(declaration.agent_version_id),
            },
        ):
            return self._execute(run_id, declaration, saved)

    # -- 실행 -----------------------------------------------------------------

    def _execute(
        self, run_id: UUID, declaration: RunDeclaration, saved: RunState | None
    ) -> RunStatus:
        if saved is None:
            local_status = RunStatus.QUEUED
            messages: list[Message] = []
            step = 0
            tasks: list[Task] = []
            seq = 0
            started_at = None
        else:
            local_status = saved.status
            messages = list(saved.messages)
            step = saved.step
            tasks = list(saved.tasks)
            seq = saved.last_seq
            started_at = saved.started_at

        if local_status == RunStatus.QUEUED:
            # 리뷰 A, spec 0002 2.4: 집었을 때 취소가 이미 요청되어 있으면
            # `queued -> cancelled` 로 **직접** 전이합니다 — `running` 을 거치지
            # 않고, 아직 실행을 시작하지 않았으므로 `started_at` 은 `None` 그대로.
            if declaration.cancel_requested_at is not None:
                return self._finalize(
                    run_id,
                    local_status,
                    RunStatus.CANCELLED,
                    seq,
                    messages,
                    step,
                    tasks,
                    started_at,
                )
            started_at = self._clock.now()
            local_status, seq = self._announce(
                run_id, local_status, RunStatus.RUNNING, seq, started_at=started_at
            )

        raw_definition = self._declarations.definition(declaration.agent_version_id)
        try:
            definition = AgentDefinition.model_validate(raw_definition)
        except ValidationError:
            return self._finalize(
                run_id,
                local_status,
                RunStatus.FAILED,
                seq,
                messages,
                step,
                tasks,
                started_at,
                failure_reason=FailureReason.DEFINITION_INVALID,
            )

        if not messages:
            messages = [
                Message(role="system", content=definition.system_prompt),
                Message(role="user", content=declaration.input),
            ]

        try:
            tool_schemas = [self._tool_schema(name) for name in definition.tools]
        except KeyError:
            return self._finalize(
                run_id,
                local_status,
                RunStatus.FAILED,
                seq,
                messages,
                step,
                tasks,
                started_at,
                failure_reason=FailureReason.UNKNOWN_TOOL,
            )

        while True:
            fresh_declaration = self._declarations.declaration(run_id)
            if fresh_declaration is not None and fresh_declaration.cancel_requested_at is not None:
                return self._finalize(
                    run_id,
                    local_status,
                    RunStatus.CANCELLED,
                    seq,
                    messages,
                    step,
                    tasks,
                    started_at,
                )

            if step >= definition.policy.max_steps:
                return self._finalize(
                    run_id,
                    local_status,
                    RunStatus.FAILED,
                    seq,
                    messages,
                    step,
                    tasks,
                    started_at,
                    failure_reason=FailureReason.MAX_STEPS_EXCEEDED,
                )

            outcome = self._run_step(
                run_id=run_id,
                declaration=declaration,
                model_id=definition.model.id,
                tool_schemas=tool_schemas,
                allowed_tools=frozenset(definition.tools),
                local_status=local_status,
                messages=messages,
                step=step,
                tasks=tasks,
                seq=seq,
                started_at=started_at,
            )
            if outcome.finished is not None:
                return outcome.finished
            assert outcome.local_status is not None
            assert outcome.seq is not None
            local_status = outcome.local_status
            seq = outcome.seq

    def _run_step(
        self,
        *,
        run_id: UUID,
        declaration: RunDeclaration,
        model_id: str | None,
        tool_schemas: list[ToolSchema],
        allowed_tools: frozenset[str],
        local_status: RunStatus,
        messages: list[Message],
        step: int,
        tasks: list[Task],
        seq: int,
        started_at: datetime | None,
    ) -> _StepOutcome:
        step += 1
        task_id = f"task-{step}"
        base_attrs = {
            "aether.run_id": str(run_id),
            "aether.agent_version_id": str(declaration.agent_version_id),
            "aether.task_id": task_id,
        }

        with self._tracer.span("task", base_attrs):
            seq += 1
            self._publish(
                run_id, seq, "task.started", TaskStartedPayload(task_id=task_id, step=step)
            )

            with self._tracer.span(
                "model.complete", {**base_attrs, "aether.model.id": model_id or "default"}
            ):
                try:
                    response = self._gateway.complete(
                        ModelRequest(messages=messages, tools=tool_schemas, model_id=model_id)
                    )
                except ModelError:
                    return _StepOutcome(
                        finished=self._finalize(
                            run_id,
                            local_status,
                            RunStatus.FAILED,
                            seq,
                            messages,
                            step,
                            tasks,
                            started_at,
                            failure_reason=FailureReason.MODEL_ERROR,
                        )
                    )

            messages.append(Message(role="assistant", content=response.text))
            seq += 1
            self._publish(
                run_id,
                seq,
                "model.completed",
                ModelCompletedPayload(finish_reason=response.finish_reason, usage=response.usage),
            )

            if not response.tool_calls:
                # 리뷰 D, spec 0002 D-5: `Task` 는 모델 호출마다 하나 — 도구 호출이
                # 없어도 (빈 `tool_calls` 로) 기록합니다.
                tasks.append(Task(task_id=task_id, step=step, tool_calls=[]))
                seq += 1
                self._publish(run_id, seq, "task.finished", TaskFinishedPayload(task_id=task_id))
                return _StepOutcome(
                    finished=self._finalize(
                        run_id,
                        local_status,
                        RunStatus.SUCCEEDED,
                        seq,
                        messages,
                        step,
                        tasks,
                        started_at,
                    )
                )

            # 리뷰 C, spec 0002 2.6, 2.8: 허용 집합은 **`definition.tools`** 입니다 —
            # 레지스트리에 등록되어 있어도 정의가 허용하지 않은 도구를 모델이 부르면
            # `unknown_tool` 입니다(레지스트리 부재는 `_tool_schema` 가 이미 잡습니다).
            unknown = sorted({call.name for call in response.tool_calls} - allowed_tools)
            if unknown:
                return _StepOutcome(
                    finished=self._finalize(
                        run_id,
                        local_status,
                        RunStatus.FAILED,
                        seq,
                        messages,
                        step,
                        tasks,
                        started_at,
                        failure_reason=FailureReason.UNKNOWN_TOOL,
                    )
                )

            local_status, seq = self._announce(run_id, local_status, RunStatus.WAITING, seq)
            tasks.append(Task(task_id=task_id, step=step, tool_calls=list(response.tool_calls)))

            for call in response.tool_calls:
                tool_outcome = self._run_tool_call(
                    run_id=run_id,
                    task_id=task_id,
                    call=call,
                    base_attrs=base_attrs,
                    local_status=local_status,
                    messages=messages,
                    step=step,
                    tasks=tasks,
                    seq=seq,
                    started_at=started_at,
                )
                if tool_outcome.finished is not None:
                    return tool_outcome
                assert tool_outcome.seq is not None
                seq = tool_outcome.seq

            seq += 1
            self._publish(run_id, seq, "task.finished", TaskFinishedPayload(task_id=task_id))
            local_status, seq = self._announce(run_id, local_status, RunStatus.RUNNING, seq)

        state = RunState(
            run_id=run_id,
            messages=messages,
            step=step,
            tasks=tasks,
            last_seq=seq,
            status=local_status,
            started_at=started_at,
        )
        self._store.save(state)
        self._store.renew_lease(run_id, self._owner, self._lease_ttl_seconds)
        return _StepOutcome(local_status=local_status, seq=seq)

    def _run_tool_call(
        self,
        *,
        run_id: UUID,
        task_id: str,
        call: ToolCall,
        base_attrs: dict[str, str],
        local_status: RunStatus,
        messages: list[Message],
        step: int,
        tasks: list[Task],
        seq: int,
        started_at: datetime | None,
    ) -> _StepOutcome:
        seq += 1
        self._publish(
            run_id,
            seq,
            "tool.called",
            ToolCalledPayload(
                task_id=task_id, tool_call_id=call.id, name=call.name, arguments=call.arguments
            ),
        )

        with self._tracer.span("tool.run", {**base_attrs, "aether.tool.name": call.name}):
            try:
                tool = self._tools.get(call.name)
                result = tool.run(call.arguments)
            except Exception:  # noqa: BLE001 -- 도구 예외는 전부 tool_error 로 흡수(2.8)
                return _StepOutcome(
                    finished=self._finalize(
                        run_id,
                        local_status,
                        RunStatus.FAILED,
                        seq,
                        messages,
                        step,
                        tasks,
                        started_at,
                        failure_reason=FailureReason.TOOL_ERROR,
                    )
                )

        content = result.content
        truncated = False
        if len(content) > self._observation_max_chars:
            content = content[: self._observation_max_chars]
            truncated = True

        seq += 1
        self._publish(
            run_id,
            seq,
            "tool.result",
            ToolResultPayload(
                task_id=task_id,
                tool_call_id=call.id,
                name=call.name,
                is_error=result.is_error,
                content=content,
                truncated=truncated,
            ),
        )

        observation = Observation(
            tool_call_id=call.id,
            tool=call.name,
            content=content,
            is_error=result.is_error,
            truncated=truncated,
        )
        messages.append(
            Message(role="tool", tool_call_id=call.id, content=render_observation(observation))
        )
        return _StepOutcome(seq=seq)

    def _tool_schema(self, name: str) -> ToolSchema:
        tool = self._tools.get(name)
        return ToolSchema(
            name=tool.name, description=tool.description, input_schema=tool.input_schema
        )

    # -- 전이·종결 --------------------------------------------------------------

    def _announce(
        self,
        run_id: UUID,
        current: RunStatus,
        target: RunStatus,
        seq: int,
        *,
        started_at: datetime | None = None,
    ) -> tuple[RunStatus, int]:
        new_status = transition(current, target)
        seq += 1
        trace_id = self._tracer.current_trace_id()
        self._store.set_status(run_id, new_status, trace_id=trace_id, started_at=started_at)
        self._notifier.notify(
            StatusMessage(
                run_id=run_id,
                seq=seq,
                status=new_status,
                at=self._clock.now(),
                started_at=started_at,
                trace_id=trace_id,
            )
        )
        self._publish(run_id, seq, "run.status", RunStatusPayload(status=new_status.value))
        return new_status, seq

    def _finalize(
        self,
        run_id: UUID,
        current: RunStatus,
        target: RunStatus,
        seq: int,
        messages: list[Message],
        step: int,
        tasks: list[Task],
        started_at: datetime | None,
        *,
        failure_reason: FailureReason | None = None,
    ) -> RunStatus:
        new_status = transition(current, target)
        finished_at = self._clock.now()
        trace_id = self._tracer.current_trace_id()
        status_seq = seq + 1
        finished_seq = status_seq + 1

        # 리뷰 B, R-16: `save(state)` 를 **먼저** 커밋합니다. 그래야 그 뒤
        # `set_status`/`release` 사이에 죽어도 `load()` 의 스냅숏이 이미 종결(status·
        # failure_reason·started_at/finished_at·last_seq 전부 최종값)이라, `__call__`
        # 이 그 스냅숏을 정본으로 커밋을 마저 끝낼 수 있습니다(`_republish_terminal`
        # 의 `commit_pending`). 반대 순서(set_status 먼저)면 그 사이에 죽었을 때
        # `status()` 는 종결인데 스냅숏은 종결 전이라 재개가 낡은 seq 로 재발행합니다.
        state = RunState(
            run_id=run_id,
            messages=messages,
            step=step,
            tasks=tasks,
            last_seq=finished_seq,
            status=new_status,
            failure_reason=failure_reason,
            started_at=started_at,
            finished_at=finished_at,
        )
        self._store.save(state)
        self._store.set_status(
            run_id,
            new_status,
            failure_reason=failure_reason,
            trace_id=trace_id,
            started_at=started_at,
            finished_at=finished_at,
        )
        self._store.release(run_id, self._owner)

        self._notifier.notify(
            StatusMessage(
                run_id=run_id,
                seq=status_seq,
                status=new_status,
                at=self._clock.now(),
                started_at=started_at,
                finished_at=finished_at,
                failure_reason=failure_reason,
                trace_id=trace_id,
            )
        )
        self._publish(
            run_id,
            status_seq,
            "run.status",
            RunStatusPayload(
                status=new_status.value,
                failure_reason=failure_reason.value if failure_reason is not None else None,
            ),
        )
        self._publish(
            run_id, finished_seq, "run.finished", RunFinishedPayload(status=new_status.value)
        )
        return new_status

    def _republish_terminal(
        self,
        run_id: UUID,
        fallback_status: RunStatus | None = None,
        *,
        state: RunState | None = None,
        commit_pending: bool = False,
    ) -> RunStatus:
        """spec 0002 R-16(리뷰 B): 종결의 두 커밋(`save(state)` 먼저, `set_status` 다음)
        사이·`set_status` 뒤 통지·발행 사이, 어느 쪽에서 죽어도 닫습니다.

        `commit_pending=True` 는 `save(state)` 는 끝났지만 `set_status`/`release` 가
        아직인 경우입니다 — 그 스냅숏(`state`)을 정본으로 커밋을 마저 끝냅니다.
        `trace_id` 는 넘기지 않습니다 — 이전 단계의 `_announce`/`_finalize` 가 이미
        채워 둔 값을 COALESCE 가 보존하게 하려는 것으로, 재개하는(다른 owner일 수
        있는) worker 의 새 trace_id 로 덮어쓰지 않기 위해서입니다.

        어느 경우든 저장된 `RunState` 만으로 원래의 `run.status`/`run.finished` 를
        **같은 seq** 로 다시 만듭니다(`run.status` 의 seq 는 항상 `run.finished`
        바로 앞, 즉 `last_seq - 1` 입니다 — `_finalize` 가 그렇게만 발급하기
        때문입니다)."""
        if state is None:
            state = self._store.load(run_id)
        if state is None:
            return fallback_status if fallback_status is not None else RunStatus.FAILED

        if commit_pending:
            self._store.set_status(
                run_id,
                state.status,
                failure_reason=state.failure_reason,
                started_at=state.started_at,
                finished_at=state.finished_at,
            )
            self._store.release(run_id, self._owner)

        finished_seq = state.last_seq
        status_seq = finished_seq - 1
        trace_id = self._tracer.current_trace_id()

        self._notifier.notify(
            StatusMessage(
                run_id=run_id,
                seq=status_seq,
                status=state.status,
                at=self._clock.now(),
                started_at=state.started_at,
                finished_at=state.finished_at,
                failure_reason=state.failure_reason,
                trace_id=trace_id,
            )
        )
        self._publish(
            run_id,
            status_seq,
            "run.status",
            RunStatusPayload(
                status=state.status.value,
                failure_reason=(
                    state.failure_reason.value if state.failure_reason is not None else None
                ),
            ),
        )
        self._publish(
            run_id, finished_seq, "run.finished", RunFinishedPayload(status=state.status.value)
        )
        return state.status

    def _publish(self, run_id: UUID, seq: int, event_type: EventType, payload: BaseModel) -> None:
        event = RunEvent(
            run_id=run_id,
            seq=seq,
            at=self._clock.now(),
            type=event_type,
            payload=payload.model_dump(exclude_none=True),
        )
        self._events.publish(event)


class _StepOutcome:
    """`_run_step`/`_run_tool_call` 의 내부 반환값 — 종결됐으면 `finished` 에 최종
    `RunStatus`, 계속 진행하면 `local_status`/`seq` 에 다음 반복이 이어받을 값."""

    __slots__ = ("finished", "local_status", "seq")

    def __init__(
        self,
        *,
        finished: RunStatus | None = None,
        local_status: RunStatus | None = None,
        seq: int | None = None,
    ) -> None:
        self.finished = finished
        self.local_status = local_status
        self.seq = seq
