"""spec 0005 2.8 개정 9, R-14 (P4-5): `ModelInvoker` - `LLM` 노드가 모델을 **한 번** 부르는 포트.

모델은 `ModelGateway`(AR-5)를 지납니다. `aether_workflow` 는 그 게이트웨이도, `httpx`·벤더 SDK 도
import 하지 않고 이 포트만 선언합니다 - 조립은 worker 의 `main.py` 가 합니다(AR-10). 어댑터는 호출이
실패하면 예외를 그대로 냅니다(실행기가 `model_call_failed` 로 노드를 실패시킵니다).

반환은 본문과 종료 사유 둘뿐입니다. 본문은 `data` 의 노드 실행 기록에만 두고 span·감사·보고에는
넣지 않습니다(spec 0005 2.4, C-3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelAnswer:
    text: str
    finish_reason: str


class ModelInvoker(Protocol):
    def invoke(self, prompt: str, model_id: str | None) -> ModelAnswer:
        """프롬프트 하나로 모델을 한 번 부릅니다. `model_id` 가 `None` 이면 배포 기본 모델."""
        ...
