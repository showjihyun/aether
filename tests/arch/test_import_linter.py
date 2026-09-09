"""P0-6: prove the import-linter contracts actually fire.

`.importlinter` at the repo root is a protected file (H-1). This module does
not assert on the *content* of that file's rules by hand -- it runs the real
`lint-imports` binary against small, deliberately-violating fixtures under
`tests/arch/fixtures/`, and against the real repository, and checks the
process exit code and output. "The contract is registered" and "the contract
fires" are different claims; only the second is worth anything.
"""

from __future__ import annotations

import configparser
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Contract-id prefixes that must exist in the real .importlinter (spec 2.10 /
# docs/architecture.md 3 and 3.1). AR-10 has no contract yet (registered as a
# review item until Phase 1, per architecture.md 3.1 "기계 판정").
EXPECTED_CONTRACT_PREFIXES = {
    "ar2",
    "ar3",
    "ar4",
    "ar5",
    "ar6",
    "ar7",
    "ar8",
    "ar9",
    "ar11",
    "ar12",
}


def _lint_imports_cmd() -> list[str]:
    """Locate the lint-imports console script, falling back to `-m`.

    Preferred over relying on PATH: this must work whether or not the venv's
    Scripts/bin directory happens to be first on PATH for whoever invokes
    pytest.
    """
    exe = shutil.which("lint-imports")
    if exe:
        return [exe]
    return [sys.executable, "-m", "importlinter"]


def _run_lint_imports(
    *,
    cwd: Path,
    config_name: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run lint-imports in `cwd`.

    `config_name` is the fixtures' own config file (never named `.importlinter`
    -- that exact name is a protected file, see the fixture READMEs/comments).
    Passing `None` (the real repository case) omits --config so import-linter
    falls back to its own default discovery of `.importlinter` in `cwd`.
    """
    env = os.environ.copy()
    # Windows' cp949 locale cannot read the UTF-8 comments in the config files
    # (session finding, also applied in harness.config's api-arch step).
    env["PYTHONUTF8"] = "1"
    if extra_env:
        env.update(extra_env)
    command = list(_lint_imports_cmd())
    if config_name is not None:
        command += ["--config", config_name]
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_ar_violation_fixture_is_rejected() -> None:
    """AR-2-style fixture: bad_runtime importing bad_api must be BROKEN."""
    fixture_dir = FIXTURES_DIR / "ar_violation"
    result = _run_lint_imports(
        cwd=fixture_dir,
        config_name="importlinter.ini",
        extra_env={"PYTHONPATH": str(fixture_dir)},
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "bad_runtime must not import bad_api" in output, output


def test_inward_violation_fixture_is_rejected() -> None:
    """AR-8/AR-9/AR-11/AR-12 fixture: one violation per package-internal rule."""
    fixture_dir = FIXTURES_DIR / "inward_violation"
    result = _run_lint_imports(
        cwd=fixture_dir,
        config_name="importlinter.ini",
        extra_env={"PYTHONPATH": str(fixture_dir)},
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0, output

    expected_fragments = [
        "adapters -> application -> domain, inward only",  # AR-8
        "domain and application import no framework or I/O",  # AR-9
        "inbound adapters do not import outbound adapters",  # AR-11
        "adapters reach the application only through ports",  # AR-12
    ]
    for fragment in expected_fragments:
        assert fragment in output, f"missing {fragment!r} in output:\n{output}"

    broken_count = output.count(" BROKEN")
    assert broken_count == 4, f"expected 4 broken contracts, saw {broken_count}:\n{output}"


def test_real_importlinter_declares_every_ar_prefix() -> None:
    """The real .importlinter must carry one contract per AR-* rule (2.10)."""
    config = configparser.ConfigParser()
    config.read(REPO_ROOT / ".importlinter", encoding="utf-8")

    prefix = "importlinter:contract:"
    contract_ids = [
        section[len(prefix) :] for section in config.sections() if section.startswith(prefix)
    ]
    assert contract_ids, "no [importlinter:contract:*] sections found in .importlinter"

    seen_prefixes = {contract_id.split("-", 1)[0] for contract_id in contract_ids}
    missing = EXPECTED_CONTRACT_PREFIXES - seen_prefixes
    assert not missing, f"missing AR-* contracts in .importlinter: {sorted(missing)}"


def test_real_repository_passes_lint_imports() -> None:
    """The real .importlinter must pass (exit 0) against the real repo tree."""
    result = _run_lint_imports(cwd=REPO_ROOT)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
