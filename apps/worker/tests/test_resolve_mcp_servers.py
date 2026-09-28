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
