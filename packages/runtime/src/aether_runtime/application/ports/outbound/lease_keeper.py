"""spec 0002 C-13, D-10 (P1-7): `LeaseKeeper` — 오래 걸리는 모델·도구 호출 동안 실행
권한(lease)을 갱신하는 outbound 포트.

`AETHER_WORKER_LEASE_SECONDS`(기본 60초)는 한 단계의 최대 길이(모델 호출 타임아웃
잔여)보다 짧을 수 있으므로, `ExecuteRunUseCase` 는 모델·도구 호출을 이 포트의
`keep(...)` 컨텍스트로 감쌉니다. 호출이 진행되는 동안 별도 스레드가 주기적으로
`RunStateStore.renew_lease` 를 부르고, 갱신이 실패(DB 단절 등)하면 `LeaseStatus.lost`
가 참이 됩니다 — 유스케이스는 그 호출이 끝난 뒤 `lost` 를 확인해 참이면 결과를
버리고 `LeaseHeld` 로 물러납니다(다른 worker 가 이미 이 Run 을 가져갔을 수 있으므로
쓰지 않습니다).

`LeaseStatus` 는 `keep(...)` 컨텍스트가 끝난 뒤(스레드가 멈추고 join 된 뒤)에도 마지막
값을 그대로 들고 있습니다 — 호출부는 `with` 블록 밖에서 안전하게 `lost` 를 읽습니다.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol
from uuid import UUID


class LeaseStatus(Protocol):
    @property
    def lost(self) -> bool:
        """갱신이 한 번이라도 실패(또는 예외)했으면 참. 읽기 전용입니다."""
        ...


class LeaseKeeper(Protocol):
    def keep(
        self, run_id: UUID, owner: str, ttl_seconds: float
    ) -> AbstractContextManager[LeaseStatus]:
        """`with keeper.keep(run_id, owner, ttl_seconds) as status:` 동안 lease 를
        주기적으로 갱신합니다. 컨텍스트를 벗어나면 갱신을 멈춥니다."""
        ...
