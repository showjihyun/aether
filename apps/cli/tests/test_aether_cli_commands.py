"""`aether agent create|list`, `aether run`, `aether runs get` - fake HTTP 계층, 컨테이너 없이."""

from __future__ import annotations

from collections.abc import Iterator

from aether_cli.main import main
from aether_cli.transport import ApiError, ConnectionFailed

from apps.cli.tests.fakes_aether_cli import (
    AGENT_ID,
    API_KEY,
    RUN_ID,
    Cp949Console,
    FakeTransport,
    event,
    invoke,
    sse_lines,
)

RUN_RESPONSE = {
    "run_id": RUN_ID,
    "agent_id": AGENT_ID,
    "agent_version": 1,
    "status": "queued",
    "requested_at": "2026-10-17T00:00:00Z",
    "requested_by": "33333333-3333-3333-3333-333333333333",
}
RUN_POST = ("POST", f"/agents/{AGENT_ID}/run")
RUN_GET = ("GET", f"/runs/{RUN_ID}")


def _finished(status: str, seq: int = 3) -> dict[str, object]:
    return event(seq, "run.finished", {"status": status})


def _run_transport(*events: dict[str, object]) -> FakeTransport:
    return FakeTransport(
        responses={RUN_POST: RUN_RESPONSE},
        stream_factory=lambda: iter(sse_lines(*events)),
    )


def test_agent_create_posts_name_and_definition_and_prints_only_the_id() -> None:
    """spec 0006 R-1 / openapi `POST /agents`: 이름과 정의를 보내고 id 한 줄만 출력한다."""
    transport = FakeTransport(
        responses={("POST", "/agents"): {"id": AGENT_ID, "name": "a", "current_version": 1}}
    )

    result = invoke(["agent", "create", "--name", "a", "--prompt", "친절하게"], transport)

    assert result.code == 0, result.err
    assert [(c.method, c.path) for c in transport.calls] == [("POST", "/agents")]
    assert transport.calls[0].body == {
        "name": "a",
        "definition": {"schema_version": 1, "system_prompt": "친절하게"},
    }
    assert result.out == AGENT_ID + "\n"


def test_agent_create_without_prompt_still_sends_a_system_prompt() -> None:
    """openapi `AgentDefinition.required`: `--prompt` 를 생략해도 `system_prompt` 문자열은 간다."""
    transport = FakeTransport(responses={("POST", "/agents"): {"id": AGENT_ID}})

    result = invoke(["agent", "create", "--name", "a"], transport)

    assert result.code == 0, result.err
    definition = transport.calls[0].body["definition"]  # type: ignore[index]
    assert isinstance(definition["system_prompt"], str)


def test_agent_list_prints_a_table_and_follows_the_cursor() -> None:
    """spec 0006 MVP-1 `agent list`: 이름·current_version·updated_at 표, 모든 페이지를 훑는다."""
    page1 = {
        "items": [
            {"id": AGENT_ID, "name": "첫째 — 에이전트", "current_version": 2, "updated_at": "T1"}
        ],
        "next_cursor": "CUR",
    }
    page2 = {
        "items": [{"id": "id-2", "name": "둘째", "current_version": 1, "updated_at": "T2"}],
        "next_cursor": None,
    }
    transport = FakeTransport(responses={("GET", "/agents"): [page1, page2]})

    result = invoke(["agent", "list"], transport)

    assert result.code == 0, result.err
    assert [c.query for c in transport.calls][1] is not None
    assert (transport.calls[1].query or {}).get("cursor") == "CUR"
    header = result.out.splitlines()[0]
    assert "NAME" in header and "CURRENT_VERSION" in header and "UPDATED_AT" in header
    assert "첫째 — 에이전트" in result.out
    assert "둘째" in result.out
    assert "T1" in result.out and "T2" in result.out


def test_run_posts_the_input_then_reads_events_of_that_run() -> None:
    """spec 0006 R-1: `run` 은 POST /agents/{id}/run 뒤에 그 run 의 이벤트 경로를 연다."""
    transport = _run_transport(
        event(1, "run.status", {"status": "running"}), _finished("succeeded", 2)
    )

    result = invoke(["run", AGENT_ID, "--input", "안녕"], transport)

    assert result.code == 0, result.err
    assert [(c.method, c.path) for c in transport.calls] == [
        RUN_POST,
        ("GET", f"/runs/{RUN_ID}/events"),
    ]
    assert transport.calls[0].body == {"input": "안녕"}
    assert RUN_ID in result.out
    assert "run.status" in result.out and "run.finished" in result.out


def test_run_prints_each_event_as_it_arrives_not_all_at_the_end() -> None:
    """spec 0006 R-1 (스트림 출력): 다음 이벤트를 읽기 **전에** 앞 이벤트가 이미 출력돼 있다."""
    out, err = Cp949Console(), Cp949Console()
    seen: list[str] = []

    def stream() -> Iterator[bytes]:
        for line in sse_lines(
            event(1, "run.status", {"status": "FIRST-MARK"}), _finished("succeeded", 2)
        ):
            if line.startswith(b"id: 2"):
                seen.append(out.text())
            yield line

    transport = FakeTransport(responses={RUN_POST: RUN_RESPONSE}, stream_factory=stream)

    code = main(
        ["run", AGENT_ID, "--input", "x"],
        env={"AETHER_API_KEY": API_KEY},
        stdout=out,
        stderr=err,
        transport_factory=lambda url, key: transport,
    )

    assert code == 0, err.text()
    assert seen, "두 번째 이벤트까지 읽지 못했습니다"
    assert "FIRST-MARK" in seen[0], (
        f"앞 이벤트가 뒤 이벤트를 읽기 전에 출력돼야 합니다: {seen[0]!r}"
    )


def test_run_stops_reading_at_run_finished() -> None:
    """spec 0006 R-1: `run.finished` 는 항상 마지막 - 그 뒤는 읽지 않고 끝낸다."""

    def stream() -> Iterator[bytes]:
        yield from sse_lines(_finished("succeeded", 1))
        raise AssertionError("run.finished 뒤의 스트림을 계속 읽었습니다")

    transport = FakeTransport(responses={RUN_POST: RUN_RESPONSE}, stream_factory=stream)

    result = invoke(["run", AGENT_ID, "--input", "x"], transport)

    assert result.code == 0, result.err


def test_run_exits_nonzero_and_explains_when_the_run_failed() -> None:
    """spec 0006 MVP-1 (종결 상태로 끝): 실패하면 exit != 0 이고 사유를 보여 준다."""
    transport = _run_transport(_finished("failed", 1))
    transport.responses[RUN_GET] = {
        "run_id": RUN_ID,
        "status": "failed",
        "failure_reason": "model_error",
    }

    result = invoke(["run", AGENT_ID, "--input", "x"], transport)

    assert result.code == 1
    assert "failed" in result.out
    assert "model_error" in result.out + result.err


def test_run_exits_nonzero_for_every_non_succeeded_terminal_status() -> None:
    """`cancelled`·`timed_out` 도 성공이 아니다."""
    for status in ("failed", "cancelled", "timed_out"):
        transport = _run_transport(_finished(status, 1))
        transport.responses[RUN_GET] = {"run_id": RUN_ID, "status": status, "failure_reason": None}
        assert invoke(["run", AGENT_ID, "--input", "x"], transport).code == 1, status


def test_run_reports_a_stream_that_ends_without_run_finished() -> None:
    """spec 0006 요구 6: 연결이 끊기면 그 사실을 출력하고 0 이 아닌 코드로 끝난다."""
    transport = _run_transport(event(1, "run.status", {"status": "running"}))

    result = invoke(["run", AGENT_ID, "--input", "x"], transport)

    assert result.code == 1
    assert "run.finished" in result.err or "끊" in result.err


def test_run_reports_a_connection_error_in_the_middle_of_the_stream() -> None:
    """스트림 도중 `ConnectionFailed` 도 같은 처리 - 0 이 아닌 코드."""

    def stream() -> Iterator[bytes]:
        yield from sse_lines(event(1, "run.status", {"status": "running"}))
        raise ConnectionFailed("스트림 연결이 끊어졌습니다")

    transport = FakeTransport(responses={RUN_POST: RUN_RESPONSE}, stream_factory=stream)

    result = invoke(["run", AGENT_ID, "--input", "x"], transport)

    assert result.code == 1
    assert "끊" in result.err


def test_runs_get_prints_status_times_and_failure_reason() -> None:
    """spec 0006 MVP-1 `runs get`: GET /runs/{id} 의 상태·시각·실패 사유."""
    transport = FakeTransport(
        responses={
            RUN_GET: {
                "run_id": RUN_ID,
                "agent_id": AGENT_ID,
                "agent_version": 3,
                "status": "failed",
                "requested_at": "REQ-T",
                "started_at": "START-T",
                "finished_at": None,
                "failure_reason": "tool_denied",
                "trace_id": "TRACE",
            }
        }
    )

    result = invoke(["runs", "get", RUN_ID], transport)

    assert result.code == 0, result.err
    assert [(c.method, c.path) for c in transport.calls] == [RUN_GET]
    for expected in (RUN_ID, "failed", "REQ-T", "START-T", "tool_denied", "TRACE"):
        assert expected in result.out, expected


def test_api_errors_exit_one_with_the_status_on_stderr() -> None:
    """404 같은 서버 오류는 exit 1, stderr 에 상태와 사유."""
    transport = FakeTransport(responses={RUN_GET: ApiError(404, "run_not_found")})

    result = invoke(["runs", "get", RUN_ID], transport)

    assert result.code == 1
    assert "404" in result.err and "run_not_found" in result.err


def test_unreachable_server_exits_one() -> None:
    """서버에 닿지 못하면 exit 1 과 안내."""
    transport = FakeTransport(responses={RUN_GET: ConnectionFailed("연결하지 못했습니다")})

    result = invoke(["runs", "get", RUN_ID], transport)

    assert result.code == 1
    assert "연결" in result.err


def test_non_ascii_output_is_utf8_on_a_cp949_console() -> None:
    """improvement-log 2026-09-11-005: em dash·한국어가 cp949 콘솔에서도 UTF-8 로 나간다."""
    transport = _run_transport(
        event(1, "model.completed", {"text": "서울 — 맑음"}), _finished("succeeded", 2)
    )

    result = invoke(["run", AGENT_ID, "--input", "날씨 — 서울"], transport)

    assert result.code == 0, result.err
    assert "서울 — 맑음" in result.out


def test_server_url_defaults_to_localhost_and_follows_the_env_var() -> None:
    """spec 0006 2.9: `AETHER_API_URL`, 기본 `http://localhost:8000`."""
    transport = FakeTransport(responses={RUN_GET: {"run_id": RUN_ID, "status": "queued"}})
    default = invoke(["runs", "get", RUN_ID], transport)
    assert default.factory_calls == [("http://localhost:8000", API_KEY)]

    custom = invoke(
        ["runs", "get", RUN_ID],
        FakeTransport(responses={RUN_GET: {"run_id": RUN_ID, "status": "queued"}}),
        env={"AETHER_API_KEY": API_KEY, "AETHER_API_URL": "http://api.example:9000"},
    )
    assert custom.factory_calls == [("http://api.example:9000", API_KEY)]
