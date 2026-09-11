"""spec 0001 D-3 · 2.9: 새 API 키를 발급하는 inbound 포트.

CLI 어댑터(`aether-api keys create --label`)가 이 포트 타입만 보고 부릅니다(AR-12).
원문 키는 `IssuedApiKey.raw_key` 에만 존재하며, 발급 이 순간에만 호출부에 노출됩니다
(spec 2.9 발급 행) — 저장소에는 해시만 남습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from aether_api.domain.api_key import ApiKey


@dataclass(frozen=True)
class IssuedApiKey:
    """발급 직후 한 번만 존재하는 원문과, 영속화된 `ApiKey`(해시만 가짐)의 짝."""

    raw_key: str
    key: ApiKey


class IssueApiKey(Protocol):
    """`label` 로 새 키를 만들어 원문과 저장된 레코드를 함께 반환합니다."""

    def __call__(self, label: str) -> IssuedApiKey: ...
