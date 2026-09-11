"""spec 0001 2.9 H-3: `aether-api keys create --label` — 원문은 stdout 에만, 한 번만.

단위 테스트는 `IssueApiKey` 포트에 fake 를 꽂아 `keys_create` 함수만 봅니다(AR-12 — CLI
어댑터는 유스케이스가 아니라 포트만 압니다). 통합 테스트는 실제 서브프로세스로
`aether-api keys create` 를 실행해 발급된 키가 PostgreSQL 에 저장됐는지 확인합니다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from aether_api.adapters.inbound.cli import build_parser, keys_create
from aether_api.application.ports.inbound.issue_api_key import IssuedApiKey
from aether_api.domain.api_key import ApiKey, generate_raw_key, hash_key, is_well_formed

REPO_ROOT = Path(__file__).resolve().parents[3]


class _FakeIssueApiKey:
    """`IssueApiKey` 포트의 최소 fake — 항상 같은 `IssuedApiKey` 를 반환합니다."""

    def __init__(self, issued: IssuedApiKey) -> None:
        self._issued = issued
        self.labels: list[str] = []

    def __call__(self, label: str) -> IssuedApiKey:
        self.labels.append(label)
        return self._issued


def _issued_key(*, raw: str, label: str) -> IssuedApiKey:
    key = ApiKey(
        id=uuid4(),
        label=label,
        key_hash=hash_key(raw),
        created_at=datetime.now(UTC),
        revoked_at=None,
    )
    return IssuedApiKey(raw_key=raw, key=key)


def test_build_parser_accepts_keys_create_with_required_label() -> None:
    parser = build_parser()

    args = parser.parse_args(["keys", "create", "--label", "ci"])

    assert args.command == "keys"
    assert args.keys_command == "create"
    assert args.label == "ci"


def test_build_parser_rejects_keys_create_without_label() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["keys", "create"])


def test_keys_create_prints_only_raw_key_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = generate_raw_key()
    issue = _FakeIssueApiKey(_issued_key(raw=raw, label="ci"))

    keys_create(issue, "ci")

    captured = capsys.readouterr()
    assert captured.out == raw + "\n"
    assert issue.labels == ["ci"]


def test_keys_create_stderr_has_metadata_but_not_raw_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = generate_raw_key()
    issued = _issued_key(raw=raw, label="ci-runner")
    issue = _FakeIssueApiKey(issued)

    keys_create(issue, "ci-runner")

    captured = capsys.readouterr()
    assert str(issued.key.id) in captured.err
    assert "ci-runner" in captured.err
    assert raw not in captured.err


def _aether_api_cmd() -> list[str]:
    exe = shutil.which("aether-api")
    if exe:
        return [exe]
    return [sys.executable, "-m", "aether_api.main"]


@pytest.mark.integration
def test_keys_create_cli_end_to_end_persists_a_well_formed_key(
    control_database_url: str,
    control_connection_factory: Callable[[], psycopg.Connection],
) -> None:
    env = os.environ.copy()
    env["AETHER_DATABASE_URL"] = control_database_url

    result = subprocess.run(
        [*_aether_api_cmd(), "keys", "create", "--label", "ci"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    raw = result.stdout.strip()
    assert is_well_formed(raw)
    assert raw not in result.stderr

    from aether_api.adapters.outbound.db.api_keys import PostgresApiKeyStore

    store = PostgresApiKeyStore(control_connection_factory)
    found = store.find_by_hash(hash_key(raw))
    assert found is not None
    assert found.label == "ci"
