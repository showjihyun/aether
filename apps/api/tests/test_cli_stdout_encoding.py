"""CLI 의 JSON 출력은 **stdout 의 로케일 인코딩과 무관하게** UTF-8 로 나간다.

2026-10-13 P4-1 에서 관측한 것: Windows 에서 `uv run aether-api openapi > openapi.json`
이 `UnicodeEncodeError: 'cp949' codec can't encode character '\\u2014'` 로 실패합니다.
`sys.stdout.write()` 가 쓰는 인코딩은 **실행 환경의 로케일**이 정하고, 이 저장소의
스키마는 한국어 설명과 em dash(`—`)를 담고 있어 cp949 로 인코딩되지 않습니다.
`PYTHONUTF8=1` 로 우회할 수 있지만, 그러면 **그 변수를 아는 사람만** 재생성할 수
있습니다 — `packages/sdk/openapi.json` 의 드리프트 테스트가 재생성을 요구하므로
우회 지식이 없는 사람은 통과시킬 방법이 없습니다.

On-Prem·Air-Gapped 가 제품 요구이므로 "내 셸에서는 된다" 는 근거가 되지 않습니다
([../../../AGENTS.md](../../../AGENTS.md) Trust). 출력 인코딩을 로케일에 맡기지 않고
코드가 정합니다.
"""

from __future__ import annotations

import io
import json
import sys
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from aether_api.adapters.inbound.cli import events_schema, keys_create, openapi
from aether_api.application.ports.inbound.issue_api_key import IssuedApiKey
from aether_api.domain.api_key import ApiKey, hash_key
from aether_api.main import app


class _Cp949Stdout(io.TextIOWrapper):
    """cp949 콘솔을 흉내 냅니다 — Windows 한국어 로케일의 기본 stdout 입니다.

    `TextIOWrapper` 를 쓰는 이유: 실제 `sys.stdout` 과 같은 모양(`.write` 는 str,
    `.buffer` 는 bytes)이어야 고치는 쪽이 `.buffer` 로 우회하는 것을 테스트가
    확인할 수 있습니다. `io.StringIO` 는 `.buffer` 가 없어 이 실패를 재현하지
    못합니다.
    """

    def __init__(self) -> None:
        self._raw = io.BytesIO()
        super().__init__(self._raw, encoding="cp949", newline="")

    def written_bytes(self) -> bytes:
        self.flush()
        return self._raw.getvalue()


def _cp949_stdout(monkeypatch: pytest.MonkeyPatch) -> _Cp949Stdout:
    """**fixture 로 두지 않습니다.** pytest 의 전역 캡처가 fixture setup **뒤**에
    `resume_global_capture()` 로 `sys.stdout` 을 자기 객체로 다시 꽂으므로, fixture 에서
    monkeypatch 하면 테스트 본문이 돌 때는 이미 덮여 있습니다(2026-10-13 확인: 교체가
    먹지 않아 출력이 pytest 캡처로 갔고 이 스트림은 비어 있었습니다). 본문에서
    부릅니다."""
    stream = _Cp949Stdout()
    monkeypatch.setattr(sys, "stdout", stream)
    return stream


def test_openapi_is_written_as_utf8_on_a_cp949_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    """`openapi` 가 cp949 stdout 에서도 UTF-8 바이트를 낸다."""
    stream = _cp949_stdout(monkeypatch)

    openapi(app)

    raw = stream.written_bytes()
    schema = json.loads(raw.decode("utf-8"))

    assert schema["openapi"].startswith("3."), schema.get("openapi")
    assert "—".encode() in raw or "—" in raw.decode("utf-8"), (
        "이 테스트의 전제가 깨졌습니다 — 스키마에 cp949 로 인코딩되지 않는 문자가 "
        "하나도 없으면 이 테스트는 공허하게 통과합니다. 전제를 다시 확인하십시오."
    )


def test_events_schema_is_written_as_utf8_on_a_cp949_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`events-schema` 도 같은 경로를 씁니다 — 한 곳만 고치고 넘어가지 않습니다."""
    stream = _cp949_stdout(monkeypatch)

    events_schema()

    schema = json.loads(stream.written_bytes().decode("utf-8"))

    assert schema["title"] == "RunEvent"


def test_stderr_metadata_with_a_non_ascii_label_is_written_as_utf8(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stderr 도 같은 경로입니다 — `keys create --label` 의 라벨은 사용자 입력입니다.

    stdout 만 고치면 한국어 라벨로 키를 발급할 때 **메타데이터 한 줄 때문에** 명령이
    죽습니다. 원문(stdout)은 이미 나간 뒤이므로 더 나쁩니다 — 키는 발급됐는데 명령은
    실패한 것으로 보입니다.
    """
    issued = IssuedApiKey(
        key=ApiKey(
            id=uuid4(),
            label="운영 — 서울",
            key_hash=hash_key("x"),
            created_at=datetime.now(UTC),
            revoked_at=None,
        ),
        raw_key="aether_sk_test",
    )
    stream = _cp949_stdout(monkeypatch)
    monkeypatch.setattr(sys, "stderr", stream)

    keys_create(lambda label: issued, "운영 — 서울")

    written = stream.written_bytes().decode("utf-8")
    assert "aether_sk_test" in written
    assert "운영 — 서울" in written


def test_stdout_without_a_buffer_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """`sys.stdout` 에 `.buffer` 가 없는 환경(일부 캡처·래퍼)에서도 출력이 나간다.

    `.buffer` 로만 쓰도록 고치면 `.buffer` 가 없는 stdout 에서 `AttributeError` 로
    죽습니다. 그 환경은 UTF-8 보장을 받지 못하지만, **죽는 것보다 낫습니다.**
    """
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)

    events_schema()

    assert json.loads(stream.getvalue())["title"] == "RunEvent"
