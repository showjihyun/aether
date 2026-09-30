"""spec 0003 2.9, D-2 (P2-6): `aether_worker.main._resolve_mcp_servers` — worker 가
`AETHER_MCP_SERVERS`(`name=transport:target` 목록, `;` 로 구분)을 실제 `McpServerRef`
로 푸는 표를 만듭니다. `definition.mcp_servers` 의 `ref` 가 이 표의 키입니다(spec 2.6).

자격증명은 target 안의 `${VAR}` 참조로만 들어가고, 여기서 실제 환경변수 값으로
치환됩니다(R-11) — 원문 문자열(치환 전)은 어디에도 남지 않습니다.
"""

from __future__ import annotations

from aether_mcp.domain.tools import McpServerRef
from aether_worker.main import _resolve_mcp_servers


def test_empty_raw_string_resolves_to_empty_table() -> None:
    assert _resolve_mcp_servers("") == {}


def test_single_stdio_entry_splits_command_and_args() -> None:
    table = _resolve_mcp_servers("filesystem=stdio:npx -y server-fs /data")

    assert table == {
        "filesystem": McpServerRef(
            name="filesystem", transport="stdio", command="npx", args=("-y", "server-fs", "/data")
        )
    }


def test_single_http_entry_captures_url() -> None:
    table = _resolve_mcp_servers("postgres=http:http://postgres-mcp:8080")

    assert table == {
        "postgres": McpServerRef(name="postgres", transport="http", url="http://postgres-mcp:8080")
    }


def test_multiple_entries_are_separated_by_semicolons() -> None:
    table = _resolve_mcp_servers(
        "filesystem=stdio:python fs.py;postgres=http:http://postgres-mcp:8080"
    )

    assert set(table) == {"filesystem", "postgres"}


def test_env_var_reference_in_target_is_expanded_from_the_given_environment() -> None:
    """R-11: 자격증명은 target 안의 `${VAR}` 참조로만 들어갑니다."""
    table = _resolve_mcp_servers(
        "postgres=http:http://postgres-mcp:8080/${TOKEN}",
        env={"TOKEN": "secret-value"},
    )

    assert table["postgres"].url == "http://postgres-mcp:8080/secret-value"


def test_env_var_reference_missing_from_environment_resolves_to_empty_string() -> None:
    table = _resolve_mcp_servers("postgres=http:http://x/${MISSING}", env={})

    assert table["postgres"].url == "http://x/"


def test_blank_entries_are_ignored() -> None:
    table = _resolve_mcp_servers(";;filesystem=stdio:python fs.py;;")

    assert set(table) == {"filesystem"}


def test_stdio_entry_without_env_assignments_leaves_env_as_none() -> None:
    """spec 0003 2.9 (P2-5 2단계): `KEY=VALUE` 선행 토큰이 없으면 `env` 는 여전히
    `None` — 이 단위 이전의 항목(1단계까지)과 동일 동작입니다."""
    table = _resolve_mcp_servers("filesystem=stdio:python fs.py")

    assert table["filesystem"].env is None


def test_stdio_entry_with_a_leading_env_assignment_captures_it_as_server_env() -> None:
    """spec 0003 2.9 (P2-5 2단계, 1단계 보고 불일치 2번): stdio target 의 **선행**
    `KEY=VALUE` 토큰(들)은 명령이 아니라 그 서버 프로세스의 env 로 갑니다 —
    `tools/mcp-servers/postgres-readonly/` 가 `AETHER_POSTGRES_READONLY_URL` 을
    받을 유일한 경로입니다. `${VAR}` 치환은 이미 끝난 뒤라(R-11) 원문 자격증명은
    `AETHER_MCP_SERVERS` 문자열 자체에만 남습니다."""
    table = _resolve_mcp_servers(
        "postgres=stdio:AETHER_POSTGRES_READONLY_URL=${DSN} python server.py",
        env={"DSN": "postgresql://x"},
    )

    ref = table["postgres"]
    assert ref.command == "python"
    assert ref.args == ("server.py",)
    assert ref.env == {"AETHER_POSTGRES_READONLY_URL": "postgresql://x"}


def test_stdio_entry_with_multiple_leading_env_assignments() -> None:
    table = _resolve_mcp_servers("postgres=stdio:A=1 B=2 python server.py")

    assert table["postgres"].env == {"A": "1", "B": "2"}
    assert table["postgres"].command == "python"
    assert table["postgres"].args == ("server.py",)


def test_stdio_entry_env_assignment_stops_at_the_first_non_assignment_token() -> None:
    """명령·인자 어디에도 `=` 가 우연히 있는 경우를 위해, 맨 앞부터 연속한
    `KEY=VALUE` 모양만 env 로 소비하고 첫 비일치 토큰부터는 전부 명령·인자입니다."""
    table = _resolve_mcp_servers("x=stdio:A=1 python server.py --flag=value")

    ref = table["x"]
    assert ref.env == {"A": "1"}
    assert ref.command == "python"
    assert ref.args == ("server.py", "--flag=value")
