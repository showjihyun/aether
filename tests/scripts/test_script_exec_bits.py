"""`scripts/*.sh` 는 git 인덱스에서 **실행 가능**해야 한다.

Windows 에서 만든 파일은 기본이 `100644` 이고, 그 상태로 커밋되면 **리눅스에서만**
깨집니다 - 한 스크립트가 다른 스크립트를 직접 부르는 순간 `Permission denied` 입니다.
2026-10-18 에 그 일이 실제로 났습니다: `scripts/e2e.sh` 가 `scripts/fetch-model.sh` 를
부르는데 CI(리눅스)에서 권한 거부로 멈췄고, Windows 로컬 전량은 20/20 통과였습니다.

파일 시스템의 권한을 보지 않고 **git 인덱스의 모드**를 봅니다 - 커밋에 들어가는 값이
그것이고, Windows 작업 트리의 권한은 어차피 의미가 없습니다. `bash <경로>` 로만 불리는
스크립트도 포함합니다: 호출 방식은 바뀌고(주석의 사용법은 이미 직접 호출을 적고 있습니다)
예외를 두면 다음 사람이 그 예외를 복사합니다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

EXECUTABLE = "100755"


def test_every_shell_script_is_executable_in_the_index() -> None:
    listing = subprocess.run(
        ["git", "ls-files", "-s", "--", "scripts/*.sh"],
        cwd=REPO_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=60,
    ).stdout.splitlines()

    assert listing, "scripts/*.sh 를 하나도 찾지 못했습니다"
    not_executable = []
    for line in listing:
        mode, _rest = line.split(" ", 1)
        path = line.split("	", 1)[1]
        if mode != EXECUTABLE:
            not_executable.append(f"{path} ({mode})")

    assert not not_executable, (
        "git 인덱스에서 실행 비트가 없는 스크립트입니다 - 리눅스에서 다른 스크립트가 "
        "이것을 직접 부르면 Permission denied 입니다. "
        f"`git update-index --chmod=+x <경로>` 로 고치십시오: {not_executable}"
    )
