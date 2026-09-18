"""AD-2 후보 2026-09-17-005: `scripts/check-sdk-drift.sh` 가 생성물 디렉터리를
"재생성 결과 = 작업 트리에 있는 파일" 로 검사해, 커밋 여부와 무관하게 계약(openapi.json)과
생성물이 서로 맞는지 검증하는지 확인합니다.

기존 `harness.config` 의 `web-typecheck` 드리프트 검사(`git diff --exit-code HEAD -- ...`)는
재생성 결과를 HEAD 와 비교해, 계약을 올바르게 바꾸고 정확히 재생성했더라도 **커밋 전에는
반드시 실패**했습니다(improvement-log 2026-09-17-005, evaluation/runs/2026-09-17-REP-7.md,
evaluation/runs/2026-09-17-REP-1-r2.md). 이 스크립트는 git 을 쓰지 않고 작업 트리 자체가
스스로 일치하는지만 봅니다.

이 테스트는 `--dir`·`--generate-cmd` 로 임시 디렉터리와 가짜 생성 스크립트를 주입해
pnpm 을 전혀 호출하지 않습니다. subprocess 로 bash 스크립트를 실행할 뿐 자체적으로
소켓을 열지 않으므로 `pytest-socket` 의 기본 `--disable-socket` 아래에서도(그리고
`integration` 마크 없이) 돕니다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-sdk-drift.sh"

# Windows 의 `CreateProcess` 는 인자 하나짜리 "bash" 를 넘기면 PATH 순서와 무관하게
# System32 의 WSL 런처(App execution alias)를 먼저 찾아 실패한다(실측,
# aether-windows-pitfalls). `shutil.which` 는 PATH 를 순서대로 직접 훑어 Git Bash 의
# 절대경로를 찾으므로, 그 경로를 argv[0] 로 명시해 이 문제를 피한다.
_BASH = shutil.which("bash") or "bash"


def _posix(path: Path) -> str:
    """`--generate-cmd` 값으로 넘길 경로를 슬래시 형태로 바꿉니다.

    `--generate-cmd` 값은 `check-sdk-drift.sh` 안에서 `eval` 로 재해석됩니다.
    Windows 경로(`C:\\Users\\...`)를 따옴표 없이 그대로 넘기면 eval 의 unquoted
    backslash 제거 규칙 때문에 경로가 깨지고("C:UsersFoo"), 큰따옴표로 감싸 넘기면
    이번에는 Python 의 `subprocess`가 Windows `CreateProcess` 인자를 이스케이프하는
    방식과 맞물려 인자가 다시 깨진다(둘 다 실측). 슬래시 경로는 Git Bash 가 그대로
    이해하고 backslash 특수 처리를 만나지 않으므로 이 문제를 통째로 피한다.
    """
    return str(path).replace("\\", "/")


def _write_text(path: Path, content: str) -> None:
    # newline="\n" 을 명시합니다 — pathlib 의 기본 텍스트 모드는 Windows 에서 "\n" 을
    # os.linesep("\r\n")으로 번역해, 이 fixture 로 만든 파일과 bash 의 printf(항상
    # LF)가 쓴 파일이 "내용은 같지만 바이트는 다른" 상태가 되어 버릴 수 있다. 이
    # 스크립트는 바이트 단위 비교이므로 양쪽 다 LF 로 고정해야 한다.
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_fake_generate_cmd(tmp_path: Path, body: str) -> Path:
    """생성 명령으로 쓸 가짜 스크립트를 만들어 실행 비트를 켜고 경로를 돌려줍니다."""
    script = tmp_path / "fake-generate.sh"
    _write_text(script, f"#!/usr/bin/env bash\nset -euo pipefail\n{body}\n")
    script.chmod(0o755)
    return script


def _run(dir_path: Path, generate_cmd_script: Path) -> subprocess.CompletedProcess[str]:
    # bash 로 명시적으로 실행합니다 — Windows 는 shebang 을 직접 해석하지 않습니다.
    return subprocess.run(
        [
            _BASH,
            str(SCRIPT_PATH),
            "--dir",
            _posix(dir_path),
            "--generate-cmd",
            _posix(generate_cmd_script),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _last_line(result: subprocess.CompletedProcess[str]) -> str:
    combined = (result.stdout + result.stderr).strip()
    return combined.splitlines()[-1] if combined else ""


def test_regenerate_same_content_exits_zero(tmp_path: Path) -> None:
    """(a) 재생성이 기존 생성물과 바이트 단위로 같은 내용을 쓰면 exit 0."""
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir()
    target = gen_dir / "openapi.d.ts"
    _write_text(target, "export type Foo = string;\n")

    fake_cmd = _write_fake_generate_cmd(
        tmp_path,
        # printf 의 이스케이프(\n)는 포맷 문자열에서만 해석됩니다 — %s 인자로 넘긴
        # "...\n" 은 문자 그대로 백슬래시+n 이 되어 실제 개행이 되지 않습니다.
        f'printf "%s\\n" "export type Foo = string;" > "{target}"',
    )

    result = _run(gen_dir, fake_cmd)

    assert result.returncode == 0, result.stdout + result.stderr


def test_regenerate_different_content_exits_one_and_names_file(tmp_path: Path) -> None:
    """(b) 파일 내용이 달라지면 exit 1 이고 마지막 줄에 그 파일 이름이 드러납니다."""
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir()
    target = gen_dir / "openapi.d.ts"
    _write_text(target, "export type Foo = string;\n")

    fake_cmd = _write_fake_generate_cmd(
        tmp_path,
        f'printf "%s\\n" "export type Foo = number;" > "{target}"',
    )

    result = _run(gen_dir, fake_cmd)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "openapi.d.ts" in _last_line(result)


def test_regenerate_adds_new_file_exits_one(tmp_path: Path) -> None:
    """(c) 재생성으로 파일이 새로 생기는 것도 차이로 봐 exit 1."""
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir()
    _write_text(gen_dir / "openapi.d.ts", "export type Foo = string;\n")
    new_file = gen_dir / "events.d.ts"

    fake_cmd = _write_fake_generate_cmd(tmp_path, f'echo extra > "{new_file}"')

    result = _run(gen_dir, fake_cmd)

    assert result.returncode == 1, result.stdout + result.stderr


def test_regenerate_removes_file_exits_one(tmp_path: Path) -> None:
    """(d) 재생성 뒤 파일이 사라지는 것도 차이로 봐 exit 1."""
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir()
    _write_text(gen_dir / "openapi.d.ts", "export type Foo = string;\n")
    stale = gen_dir / "events.d.ts"
    _write_text(stale, "export type Bar = string;\n")

    fake_cmd = _write_fake_generate_cmd(tmp_path, f'rm -f "{stale}"')

    result = _run(gen_dir, fake_cmd)

    assert result.returncode == 1, result.stdout + result.stderr


def test_generate_command_failure_exits_one(tmp_path: Path) -> None:
    """(e) 생성 명령 자체가 실패하면 그 종료 코드를 그대로 전파합니다(exit 1)."""
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir()
    _write_text(gen_dir / "openapi.d.ts", "export type Foo = string;\n")

    fake_cmd = _write_fake_generate_cmd(tmp_path, "exit 1")

    result = _run(gen_dir, fake_cmd)

    assert result.returncode == 1, result.stdout + result.stderr
    assert _last_line(result) != ""


def test_missing_dir_exits_one(tmp_path: Path) -> None:
    """생성물 디렉터리 자체가 없으면 exit 1 이고 이유를 밝힙니다."""
    gen_dir = tmp_path / "does-not-exist"
    fake_cmd = _write_fake_generate_cmd(tmp_path, "true")

    result = _run(gen_dir, fake_cmd)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr.strip() != ""
