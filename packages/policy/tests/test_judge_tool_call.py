"""spec 0003 D-6, R-5 (🔒 P2-4): `JudgeToolCallUseCase` — 기본값 deny(허용 목록),
행이 있으면 그 값, 같은 도구 이름이라도 서버가 다르면 판정이 독립, 대소문자가
다르면 allow 되지 않습니다.

`FakePermissionTable` 로 컨테이너 없이 돕니다(AR-9) — `PermissionTable` outbound
포트의 fake 구현입니다.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from aether_policy.application.usecases.judge_tool_call import JudgeToolCallUseCase
from aether_policy.domain.decision import Decision


class FakePermissionTable:
    """`(agent_version_id, server_name, tool_name)` 정확히 일치하는 행만 반환합니다."""

    def __init__(self) -> None:
        self._rows: dict[tuple[UUID, str, str], Decision] = {}

    def set(
        self, agent_version_id: UUID, server_name: str, tool_name: str, decision: Decision
    ) -> None:
        self._rows[(agent_version_id, server_name, tool_name)] = decision

    def lookup(self, agent_version_id: UUID, server_name: str, tool_name: str) -> Decision | None:
        return self._rows.get((agent_version_id, server_name, tool_name))


def test_no_row_means_deny_default() -> None:
    """spec D-6: 표에 행이 없으면 기본값은 deny (허용 목록)."""
    judge = JudgeToolCallUseCase(FakePermissionTable())

    assert judge(uuid4(), "filesystem", "read") == "deny"


def test_allow_row_means_allow() -> None:
    table = FakePermissionTable()
    version_id = uuid4()
    table.set(version_id, "filesystem", "read", "allow")
    judge = JudgeToolCallUseCase(table)

    assert judge(version_id, "filesystem", "read") == "allow"


def test_deny_row_means_deny() -> None:
    table = FakePermissionTable()
    version_id = uuid4()
    table.set(version_id, "filesystem", "read", "deny")
    judge = JudgeToolCallUseCase(table)

    assert judge(version_id, "filesystem", "read") == "deny"


def test_different_server_same_tool_name_judged_independently() -> None:
    """spec 개정 4, 2.7: 자원 신분은 (server_name, tool_name) — 서버가 다르면 독립."""
    table = FakePermissionTable()
    version_id = uuid4()
    table.set(version_id, "filesystem", "read", "allow")
    judge = JudgeToolCallUseCase(table)

    assert judge(version_id, "filesystem", "read") == "allow"
    assert judge(version_id, "postgres-readonly", "read") == "deny"


def test_tool_name_case_mismatch_is_not_allowed() -> None:
    """spec D-6: 이름은 정확히 일치 — 정규화·와일드카드 없음."""
    table = FakePermissionTable()
    version_id = uuid4()
    table.set(version_id, "filesystem", "read", "allow")
    judge = JudgeToolCallUseCase(table)

    assert judge(version_id, "filesystem", "Read") == "deny"
