"""CLI 가 쓰는 HTTP 경로와 메서드를 **한 곳에** 모읍니다 (spec 0006 C-1).

경로를 다른 모듈에 문자열로 흩뿌리지 않습니다. 이 표 전부가 `packages/sdk/openapi.json` 에
실재하는지 `tests/test_aether_cli_contract_drift.py` 가 확인합니다 - 계약이 TS SDK 와 이 CLI
두 곳에서 구현되므로 드리프트를 테스트로 잡습니다. 경로 매개변수 이름은 openapi 의 것
(`{agent_id}`, `{run_id}`)과 같게 둡니다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str

    def render(self, **params: str) -> str:
        """`{name}` 자리를 채운 실제 경로. 빠진 매개변수는 `KeyError`."""
        return self.path.format(**params)


CREATE_AGENT = Endpoint("POST", "/agents")
LIST_AGENTS = Endpoint("GET", "/agents")
RUN_AGENT = Endpoint("POST", "/agents/{agent_id}/run")
GET_RUN = Endpoint("GET", "/runs/{run_id}")
RUN_EVENTS = Endpoint("GET", "/runs/{run_id}/events")

ALL_ENDPOINTS: tuple[Endpoint, ...] = (CREATE_AGENT, LIST_AGENTS, RUN_AGENT, GET_RUN, RUN_EVENTS)
