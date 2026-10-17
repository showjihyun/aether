"""D-8 (spec 0006 2.8): 키는 `AETHER_API_KEY` 환경변수로만, 출력·오류 어디에도 싣지 않는다."""

from __future__ import annotations

import pytest
from aether_cli.transport import ApiError, ConnectionFailed

from apps.cli.tests.fakes_aether_cli import (
    AGENT_ID,
    API_KEY,
    RUN_ID,
    FakeTransport,
    invoke,
)

COMMANDS = [
    ["agent", "create", "--name", "a"],
    ["agent", "list"],
    ["run", AGENT_ID, "--input", "x"],
    ["runs", "get", RUN_ID],
]


@pytest.mark.parametrize("argv", COMMANDS)
def test_missing_key_exits_two_and_sends_no_request(argv: list[str]) -> None:
    """D-8: 키가 없으면 요청을 보내지 않고 exit 2, 어느 변수를 설정할지 알려 준다."""
    transport = FakeTransport()

    result = invoke(argv, transport, env={})

    assert result.code == 2
    assert "AETHER_API_KEY" in result.err
    assert transport.calls == []
    assert result.factory_calls == []


def test_blank_key_counts_as_missing() -> None:
    """공백뿐인 키도 없는 것이다 - 빈 `Authorization` 을 보내지 않는다."""
    transport = FakeTransport()

    result = invoke(["agent", "list"], transport, env={"AETHER_API_KEY": "   "})

    assert result.code == 2
    assert transport.calls == []


@pytest.mark.parametrize(
    "failure",
    [ApiError(401, "unauthorized"), ConnectionFailed("연결하지 못했습니다")],
)
def test_the_key_never_appears_in_output_or_errors(failure: Exception) -> None:
    """D-8: 성공·실패 어느 경로에서도 키 원문이 stdout·stderr 에 없다."""
    transport = FakeTransport(responses={("GET", "/agents"): failure})

    result = invoke(["agent", "list"], transport)

    assert result.code == 1
    assert API_KEY not in result.out
    assert API_KEY not in result.err
    assert result.factory_calls[0][1] == API_KEY  # 전달은 되었다 - 테스트의 전제


def test_missing_key_message_does_not_echo_a_partial_value() -> None:
    """키가 없다는 오류에도 (공백 키를 포함해) 입력값을 되풀이하지 않는다."""
    result = invoke(["agent", "list"], env={"AETHER_API_KEY": " "})

    assert API_KEY not in result.err
    assert "'   '" not in result.err


def test_usage_errors_exit_two() -> None:
    """argparse 사용 오류(명령 누락·필수 인자 누락)도 exit 2 이고 요청이 없다."""
    for argv in ([], ["run", AGENT_ID], ["agent", "create"], ["bogus"]):
        transport = FakeTransport()
        result = invoke(argv, transport)
        assert result.code == 2, argv
        assert transport.calls == [], argv
