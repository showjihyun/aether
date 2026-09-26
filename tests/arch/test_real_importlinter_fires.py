"""spec 0002 R-7 (D-13, 개정 2): 실제 `.importlinter` 가 AR-5(`httpx`)와
AR-7(`aether_runtime.application`/`adapters`) 위반을 실제로 잡는지, fixture 가 아니라
**복사된 실제 src** 로 확인합니다.

`tests/arch/test_import_linter.py` 의 기존 테스트는 fixture 전용 설정으로 "규칙이
등록되어 있다" 만 증명합니다. 이 모듈은 `apps/*/src` · `packages/*/src`(9개) ·
`.importlinter` 를 임시 디렉터리에 복사하고, 그 9개 `src` 경로를 **`PYTHONPATH` 앞**에
넣어(editable 설치의 `.pth` 항목보다 먼저 잡히도록) `lint-imports --no-cache` 를 실제로
돌립니다. 복사본이 아니라 실제 site-packages 의 editable 설치가 검사되는 사고를 막기
위해, 먼저 `aether_api.__file__` 이 임시 디렉터리를 가리키는지 확인합니다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_PACKAGE_DIRS = [
    "apps/api",
    "apps/worker",
    "packages/runtime",
    "packages/workflow",
    "packages/context",
    "packages/memory",
    "packages/mcp",
    "packages/policy",
    "packages/evaluation",
]


def _copy_src_tree(dest_root: Path) -> list[Path]:
    """`apps/*/src`·`packages/*/src` 9개를 `dest_root` 아래 같은 상대 경로로 복사합니다."""
    src_paths: list[Path] = []
    for package_dir in _PACKAGE_DIRS:
        source = REPO_ROOT / package_dir / "src"
        dest = dest_root / package_dir / "src"
        shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__"))
        src_paths.append(dest)
    shutil.copy2(REPO_ROOT / ".importlinter", dest_root / ".importlinter")
    return src_paths


def _pythonpath_env(src_paths: list[Path]) -> dict[str, str]:
    """복사된 9개 `src` 를 **기존 `PYTHONPATH`(따라서 editable 설치의 `.pth` 보다) 앞**에 둡니다."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"  # Windows cp949 로 UTF-8 주석을 못 읽는 문제(session finding)
    prefix = os.pathsep.join(str(p) for p in src_paths)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{prefix}{os.pathsep}{existing}" if existing else prefix
    return env


def _lint_imports_cmd() -> list[str]:
    exe = shutil.which("lint-imports")
    if exe:
        return [exe]
    return [sys.executable, "-m", "importlinter"]


def _run_lint_imports(config_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*_lint_imports_cmd(), "--config", str(config_path), "--no-cache"],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _assert_copy_is_actually_checked(env: dict[str, str], expected_root: Path) -> None:
    """복사본이 아니라 실제 site-packages 의 editable 설치가 검사되는 사고를 막습니다."""
    result = subprocess.run(
        [sys.executable, "-c", "import aether_api; print(aether_api.__file__)"],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    resolved = Path(result.stdout.strip()).resolve()
    assert str(resolved).startswith(str(expected_root.resolve())), (
        f"aether_api resolved outside the temp copy: {resolved}"
    )


def test_unmodified_copy_passes(tmp_path: Path) -> None:
    src_paths = _copy_src_tree(tmp_path)
    env = _pythonpath_env(src_paths)
    _assert_copy_is_actually_checked(env, tmp_path)

    result = _run_lint_imports(tmp_path / ".importlinter", env)

    assert result.returncode == 0, result.stdout + result.stderr


def test_httpx_import_outside_model_gateway_is_rejected_ar5(tmp_path: Path) -> None:
    src_paths = _copy_src_tree(tmp_path)
    env = _pythonpath_env(src_paths)
    _assert_copy_is_actually_checked(env, tmp_path)

    bad_module = tmp_path / "apps" / "api" / "src" / "aether_api" / "_bad_httpx.py"
    bad_module.write_text("import httpx\n", encoding="utf-8")

    result = _run_lint_imports(tmp_path / ".importlinter", env)
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "AR-5" in output, output


def test_runtime_execution_layers_import_from_api_is_rejected_ar7(tmp_path: Path) -> None:
    src_paths = _copy_src_tree(tmp_path)
    env = _pythonpath_env(src_paths)
    _assert_copy_is_actually_checked(env, tmp_path)

    bad_module = tmp_path / "apps" / "api" / "src" / "aether_api" / "_bad_runtime.py"
    bad_module.write_text("import aether_runtime.application\n", encoding="utf-8")

    result = _run_lint_imports(tmp_path / ".importlinter", env)
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "AR-7" in output, output


def test_policy_import_of_mcp_domain_is_rejected_ar4(tmp_path: Path) -> None:
    """spec 0003 R-5 (🔒 P2-4): `ar4-policy-judges-only` 가 처음으로 막을 코드를 갖습니다.

    `aether_policy` 는 `runtime`·`mcp`·`context` 를 import 하지 않습니다(AR-4). 이
    테스트는 그 계약이 fixture 가 아니라 **실제 `.importlinter`** 와 **복사된 실제
    src** 위에서 발화하는지를 봅니다(P2-1 착수 전까지는 `aether_mcp` 도, P2-4 착수
    전까지는 `aether_policy` 도 판단할 코드가 없어 이 계약이 한 번도 발화한 적이
    없었습니다).
    """
    src_paths = _copy_src_tree(tmp_path)
    env = _pythonpath_env(src_paths)
    _assert_copy_is_actually_checked(env, tmp_path)

    bad_module = tmp_path / "packages" / "policy" / "src" / "aether_policy" / "_bad.py"
    bad_module.write_text("import aether_mcp.domain\n", encoding="utf-8")

    result = _run_lint_imports(tmp_path / ".importlinter", env)
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert "AR-4" in output, output


def test_real_importlinter_contract_bodies_declare_the_expected_forbidden_modules() -> None:
    """spec 개정 2: 실제 파일의 contract 본문 단언.

    `httpx` ∈ AR-5 forbidden, `aether_runtime.application` ∈ AR-7 forbidden.
    """
    content = (REPO_ROOT / ".importlinter").read_text(encoding="utf-8")
    assert "httpx" in content
    assert "aether_runtime.application" in content
