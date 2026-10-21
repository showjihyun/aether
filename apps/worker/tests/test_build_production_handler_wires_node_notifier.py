"""spec 0007 2.3, D-3 (P5-1): worker 의 **프로덕션 조립**이 노드 상태 통지자를 실제로 꽂는지.

`node_notifier` 의 기본값은 `None` 이고 `None` 이면 실행기가 조용히 건너뜁니다 - 조립에서 그 인자가
빠지면 호출은 성공하는데 투영만 멈춥니다(spec 0005 개정 10 의 모양). 이 파일이 그 침묵을 실패로
바꿉니다. 연결은 지연되므로(`connect` 팩토리, Redis 클라이언트는 열지 않음) 컨테이너 없이 돕니다.
"""

from __future__ import annotations

from aether_worker.main import _build_production_workflow_handler
from aether_worker.settings import Settings
from aether_workflow.adapters.outbound.redis.workflow_node_status_notifier import (
    RedisWorkflowNodeStatusNotifier,
)
from aether_workflow.application.usecases.advance_workflow_run import AdvanceWorkflowRunUseCase
from redis import Redis


def test_production_workflow_handler_wires_the_node_status_notifier() -> None:
    settings = Settings(workflow_node_status_stream="x:node-states")

    handler = _build_production_workflow_handler(settings, Redis())  # 연결은 열지 않는다

    advance = handler._advance  # type: ignore[attr-defined]
    assert isinstance(advance, AdvanceWorkflowRunUseCase)
    assert isinstance(advance._node_notifier, RedisWorkflowNodeStatusNotifier)
    assert advance._node_notifier._stream == "x:node-states"
