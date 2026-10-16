"""spec 0005 2.8 개정 9, R-14, AR-5 (P4-5): `ModelGatewayInvoker` - `aether_workflow` 의
`ModelInvoker` 포트를 runtime 의 `ModelGateway` 로 구현합니다.

어댑터는 `aether_worker` 에 둡니다 - `aether_workflow` 는 `aether_runtime` 을 import 하지 않으므로
(AR-13) 변환을 그 패키지 안에 둘 수 없습니다(`ModelGatewayEmbedder` 와 같은 자리, 같은
이유). 새 모델 통로를 만들지 않습니다: 프롬프트는 `user` 메시지 하나로 **기존 게이트웨이**를
한 번 지납니다. 도구는 알리지 않으므로 모델은 도구 호출을 요청하지 않습니다. 실패(`ModelError`
등)는 삼키지 않고 그대로 올립니다 - 실행기가 `model_call_failed` 로 노드를 실패시킵니다.
"""

from __future__ import annotations

from aether_runtime.application.ports.outbound.model_gateway import ModelGateway, ModelRequest
from aether_runtime.domain.run import Message
from aether_workflow.application.ports.outbound.model_invoker import ModelAnswer


class ModelGatewayInvoker:
    """`aether_workflow.application.ports.outbound.model_invoker.ModelInvoker` 의 구현."""

    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway

    def invoke(self, prompt: str, model_id: str | None) -> ModelAnswer:
        response = self._gateway.complete(
            ModelRequest(messages=[Message(role="user", content=prompt)], model_id=model_id)
        )
        return ModelAnswer(text=response.text, finish_reason=response.finish_reason)
