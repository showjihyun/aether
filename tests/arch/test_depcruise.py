"""P0-6: prove the .dependency-cruiser.cjs AR-1 contract actually fires.

Only the fixture check runs here. The real root config's exit-0 check moved
to P0-3 (plan 0001-phase-0-foundation.md, P0-6 step 4) because `apps/web` has
no TypeScript files yet -- depcruise has nothing to cruise, so an exit-0
assertion here would pass for the wrong reason.

This test invokes the real `depcruise` binary as-is. It does not paper over
environment mismatches: if the installed Node is one dependency-cruiser
refuses to start on, that is a real defect in this machine's setup (it
disagrees with `.nvmrc`), and the test fails loudly with that diagnosis
instead of skipping or silently working around it (harness/rules/
evaluation-integrity.rule.md EI-6).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "ar1_violation"

_UNSUPPORTED_NODE_MARKER = "is not supported"


def _run(command: str, *, cwd: Path) -> subprocess.CompletedProcess[str]:
    # shell=True (not an argv list): on Windows, `pnpm` resolves to a .cmd
    # shim that the Win32 CreateProcess call cannot exec directly -- it needs
    # cmd.exe (or, on POSIX CI, /bin/sh) to interpret it.
    return subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_ar1_violation_fixture_is_rejected() -> None:
    result = _run(
        "pnpm exec depcruise apps/web --config depcruise.fixture.cjs",
        cwd=FIXTURE_DIR,
    )
    output = result.stdout + result.stderr

    if _UNSUPPORTED_NODE_MARKER in output:
        pytest.fail(
            f"dependency-cruiser refused to start on this machine's Node ({_node_version()}). "
            "Use the Node 22 LTS declared in .nvmrc -- dependency-cruiser 18 "
            "only supports ^22 || ^24 || >=26. Raw output:\n" + output
        )

    assert result.returncode != 0, output
    assert "ar1-web-imports-only-sdk" in output, output


def _node_version() -> str:
    result = subprocess.run(
        "node --version",
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return (result.stdout + result.stderr).strip() or "<unknown>"
