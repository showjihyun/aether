"""spec 0001 2.9: API 키 도메인 규칙 — 형식, 해시, 생성. 표준 라이브러리만 사용합니다(AR-9).

이 모듈은 `control.api_keys` 의 불변식을 코드로 고정합니다: 원문은 저장하지 않고
(``key_hash`` 만), 키는 ``aeth_`` 접두사 + 256-bit 난수(base64url, 패딩 없음)이며,
해시는 salt 없는 SHA-256 입니다(D-3 — 256-bit 난수라 사전 공격이 성립하지 않는다는
전제. 그 전제가 바뀌면 이 결정도 바뀝니다).
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

KEY_PREFIX = "aeth_"

# 256-bit(32byte) 난수를 base64url 로 인코딩하면 패딩 없이 43자입니다.
_RAW_TOKEN_LENGTH = 43
_KEY_PATTERN = re.compile(rf"^{re.escape(KEY_PREFIX)}[A-Za-z0-9_-]{{{_RAW_TOKEN_LENGTH}}}$")


def is_well_formed(raw: str) -> bool:
    """`aeth_` 접두사 + base64url(패딩 없음) 43자인지만 봅니다. 등록 여부는 보지 않습니다."""
    return bool(_KEY_PATTERN.fullmatch(raw))


def hash_key(raw: str) -> str:
    """salt 없는 SHA-256 hex 다이제스트. `control.api_keys.key_hash` 에 저장하는 값과 같습니다."""
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def generate_raw_key(rand: Callable[[int], bytes] = secrets.token_bytes) -> str:
    """`aeth_` + 256-bit 난수(base64url, 패딩 없음)를 생성합니다.

    `rand` 를 주입할 수 있게 한 것은 테스트 결정성을 위해서입니다 — 실제 발급 경로는
    기본값(`secrets.token_bytes`, CSPRNG)을 그대로 씁니다.
    """
    token = base64.urlsafe_b64encode(rand(32)).rstrip(b"=").decode("ascii")
    return f"{KEY_PREFIX}{token}"


@dataclass(frozen=True)
class ApiKey:
    """`control.api_keys` 한 행에 대응하는 값 객체. 원문(raw key)은 담지 않습니다."""

    id: UUID
    label: str
    key_hash: str
    created_at: datetime
    revoked_at: datetime | None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


@dataclass(frozen=True)
class Principal:
    """인증에 성공한 요청이 얻는 신원. 사용자·조직·역할은 없습니다(spec 2.9 범위)."""

    key_id: UUID
    label: str


class Unauthenticated(Exception):
    """인증 실패. 이유 문자열은 로그용이며 HTTP 응답에는 노출하지 않습니다."""
