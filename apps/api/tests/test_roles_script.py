"""단위 테스트(컨테이너 없음): `01-roles.sh` 가 존재하고 두 역할 이름을 담고 있는지만
봅니다. `conftest.py` 의 역할 생성 문장과 이 스크립트가 갈라지지 않게 하는 최소 가드
입니다 — 문장이 갈라지면 testcontainers 에서는 통과하고 실제 compose 기동에서는
`aether_control`/`aether_data` 역할이 없어 실패하는 일이 생깁니다.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ROLES_SCRIPT = REPO_ROOT / "infra" / "docker" / "postgres" / "init" / "01-roles.sh"


def test_roles_script_exists() -> None:
    assert ROLES_SCRIPT.is_file()


def test_roles_script_creates_both_plane_roles() -> None:
    content = ROLES_SCRIPT.read_text(encoding="utf-8")

    assert "aether_control" in content
    assert "aether_data" in content
    assert "CREATE ROLE" in content


def test_roles_script_reads_passwords_from_env_not_literals() -> None:
    content = ROLES_SCRIPT.read_text(encoding="utf-8")

    assert "AETHER_CONTROL_PASSWORD" in content
    assert "AETHER_DATA_PASSWORD" in content
