"""P0-9 plan 1b: every `application/usecases/*.py` needs a matching `test_<name>.py`.

Structural test -- it cannot prove tests were written *before* the implementation
(red before green), but it can catch "a usecase exists with no test anywhere in the
repository", which is the cheaper, machine-checkable half of the TDD discipline this
repo asks for (docs/architecture.md 3.1, AR-8/AR-12: usecases live in
`application/usecases`).

This runs inside `api-unit` so the step count in harness.config does not change
(spec 0001 D-7).

P0-9 stage 1 added this test while `application/usecases/*.py` was still empty, so it
passed vacuously (the glob matched zero files). Stage 2 adds `authenticate.py` and
`issue_api_key.py`, so this test now checks them for real -- `test_authenticate.py` /
`test_issue_api_key.py` (already written in stage 1) satisfy it.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_USECASE_GLOBS = [
    "apps/*/src/aether_*/application/usecases/*.py",
    "packages/*/src/aether_*/application/usecases/*.py",
]


def _usecase_files() -> list[Path]:
    files: list[Path] = []
    for pattern in _USECASE_GLOBS:
        files.extend(REPO_ROOT.glob(pattern))
    return [f for f in files if f.name != "__init__.py"]


def _has_matching_test(usecase: Path) -> bool:
    expected_name = f"test_{usecase.stem}.py"
    return any(REPO_ROOT.rglob(expected_name))


def test_every_usecase_has_a_matching_test_file() -> None:
    usecases = _usecase_files()

    missing = [str(f.relative_to(REPO_ROOT)) for f in usecases if not _has_matching_test(f)]

    assert not missing, f"usecases with no matching test_<name>.py anywhere: {missing}"
