"""PreToolUse 가드 사슬의 **비용**과 그 비용을 줄여도 변하지 않아야 하는 것.

근거: improvement-log `2026-10-11-002`. 가드는 verify 단계가 아니라 **도구 호출마다**
도는 훅이라 `.harness/verify.json` 의 어느 숫자에도 나타나지 않는다. 2026-10-11 실측에서
`echo hello` 하나에도 2.2~3.3초가 들었고, 내역은 번들 가드 위임 1.22초와 래퍼의 JSON 필드
추출 약 1.0초였다 — 둘 다 **같은 답을 더 비싸게 구하는** 비용이다.

그래서 이 파일이 고정하는 것은 셋이다.

1. **보호 목록의 내용**(`test_*_pattern_list_is_unchanged`). 비용을 줄이는 변경이
   패턴 하나를 조용히 떨어뜨리면 가드는 빨라지면서 **덜 막는다**. 그건 개선이 아니라
   검출력과 비용을 맞바꾼 것이다. 이 목록은 2026-10-11 수정 **직전**의 실제 출력이고,
   `harness/hooks/*` 와 `harness/language/*/lang.sh` 가 소유하는 내용이므로 패턴을
   의도적으로 더하거나 뺄 때는 이 골든도 같이 고치는 것이 맞다 — 조용히 바뀌는 것만 막는다.
2. **병합 비용**(`test_pattern_merge_costs_at_most_a_few_forks`). 벽시계 절대값으로 재면
   플랫폼마다 임계가 달라져 쉽게 흔들린다. 그래서 이 환경의 **fork 1회 비용을 먼저 재고**
   그 배수로 판정한다 — fork 가 싼 Linux 에서는 임계도 같이 줄어든다. 수정 직전 구현은
   `up="$(_lang_upper "$p")"` 처럼 순수 bash 연산을 명령 치환으로 감싸 팩·kind 마다 fork 를
   했고, 그것이 fork 19회분(실측 약 400ms)이었다.
3. **필드 추출 프로세스 수**(`test_*_grep_*`). `json_field` 는 필드마다
   `printf | grep -oE | head | sed` 파이프라인을 새로 띄웠다. jq 가 있는 환경에서는 한 번에
   끝나지만 이 환경에는 jq 가 없어 전량 폴백이고, 필드 7개에 프로세스 28개가 들었다.

`test_guard_protected.py`(12건)·`test_guard_docker_volumes.py`·`test_guard_eval_blind.py` 가
**판정**을 고정하고, 이 파일이 **비용**을 고정한다. 둘을 함께 둬야 "빨라졌지만 덜 막는다" 가
어느 한쪽에서 반드시 걸린다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "scripts" / "guard-protected.sh"
BUNDLE_GUARD = REPO_ROOT / "harness" / "hooks" / "guard-evaluation-tampering.sh"
DETECT_STACK = REPO_ROOT / "harness" / "scripts" / "lib" / "detect-stack.sh"

# Windows 의 CreateProcess 는 인자 하나짜리 "bash" 를 System32 의 WSL 런처로 잡는다
# (tests/scripts/test_verify_lock.py 와 같은 이유로 절대 경로를 쓴다).
_BASH = shutil.which("bash") or "bash"
_GREP = shutil.which("grep") or "grep"

# --- 골든: 2026-10-11 수정 직전의 실제 병합 결과 -------------------------------------

BLOCKED_PATTERNS = (
    ".bandit",
    ".cargo/audit.toml",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".clippy.toml",
    ".coveragerc",
    ".dependency-cruiser.*",
    ".eslintrc",
    ".eslintrc.*",
    ".flake8",
    ".github/CODEOWNERS",
    ".github/workflows/harness.yml",
    ".go-arch-lint.yml",
    ".golangci.json",
    ".golangci.toml",
    ".golangci.yaml",
    ".golangci.yml",
    ".harness/*",
    ".importlinter",
    ".lighthouserc.*",
    ".mocharc.*",
    ".mypy.ini",
    ".oxlintrc.json",
    ".pylintrc",
    ".rspec",
    ".rubocop.yaml",
    ".rubocop.yml",
    ".rubocop_todo.yml",
    ".ruff.toml",
    ".rustfmt.toml",
    ".simplecov",
    ".size-limit.*",
    ".storybook/test-runner.*",
    ".stylelintrc",
    ".stylelintrc.*",
    "archunit.properties",
    "axe.config.*",
    "biome.json",
    "biome.jsonc",
    "checkstyle-suppressions.xml",
    "checkstyle.xml",
    "clippy.toml",
    "config/checkstyle/*",
    "config/detekt/*",
    "config/pmd/*",
    "config/spotbugs/*",
    "cypress.config.*",
    "deny.toml",
    "detekt.yml",
    "eslint.config.*",
    "evaluation/*",
    "harness.config",
    "harness.config.local",
    "harness/evaluation/*",
    "harness/hooks/*",
    "harness/language/*/lang.sh",
    "harness/rules/*",
    "harness/scripts/*.sh",
    "harness/scripts/lib/*",
    "jest-e2e.json",
    "junit-platform.properties",
    "knip.config.*",
    "knip.json",
    "lighthouserc.*",
    "lombok.config",
    "mypy.ini",
    "packwerk.yml",
    "playwright.config.*",
    "pmd-ruleset.xml",
    "pylintrc",
    "pyrightconfig.json",
    "pytest.ini",
    "ruff.toml",
    "rustfmt.toml",
    "spotbugs-exclude.xml",
    "spotbugs.xml",
    "staticcheck.conf",
    "test/jest-e2e.json",
    "tsconfig.*.json",
    "tsconfig.json",
)

WARN_PATTERNS = (
    "*.gemspec",
    ".browserslistrc",
    ".cargo/config.toml",
    ".eslintignore",
    ".github/workflows/*",
    ".gitlab-ci.yml",
    ".mvn/*",
    ".node-version",
    ".npmrc",
    ".nvmrc",
    ".ruby-version",
    ".storybook/*",
    "Cargo.lock",
    "Cargo.toml",
    "Gemfile",
    "Gemfile.lock",
    "Makefile",
    "Pipfile",
    "Rakefile",
    "angular.json",
    "build.gradle",
    "build.gradle.kts",
    "build.rs",
    "buildSrc/*",
    "codecov.yml",
    "conftest.py",
    "docker-compose*.yaml",
    "docker-compose*.yml",
    "drizzle.config.*",
    "gems.locked",
    "gems.rb",
    "go.mod",
    "go.sum",
    "go.work",
    "gradle.properties",
    "gradle/libs.versions.toml",
    "improvement-log/*",
    "jacoco*.xml",
    "jest.config.*",
    "knexfile.*",
    "next.config.*",
    "nuxt.config.*",
    "nx.json",
    "ormconfig.*",
    "package.json",
    "pdm.lock",
    "pnpm-workspace.yaml",
    "poetry.lock",
    "pom.xml",
    "postcss.config.*",
    "prisma/migrations/*",
    "prisma/schema.prisma",
    "pyproject.toml",
    "requirements*.txt",
    "requirements/*",
    "settings.gradle",
    "settings.gradle.kts",
    "setup.cfg",
    "setup.py",
    "sonar-project.properties",
    "spec/spec_helper.rb",
    "svelte.config.*",
    "tailwind.config.*",
    "test/test_helper.rb",
    "tools.go",
    "tox.ini",
    "turbo.json",
    "uv.lock",
    "vite.config.*",
    "vitest.config.*",
    "vitest.workspace.*",
)


def _bash(script: str, *, cwd: Path, env: dict[str, str] | None = None) -> str:
    merged = dict(os.environ)
    if env:
        merged.update(env)
    result = subprocess.run(
        [_BASH, "-c", script],
        cwd=cwd,
        capture_output=True,
        # text=True 만 주면 Windows 기본 코드페이지(cp949)로 디코딩하다 한국어 출력에서
        # UnicodeDecodeError 가 난다(tests/scripts/test_verify_lock.py 와 같은 이유).
        encoding="utf-8",
        errors="replace",
        env=merged,
        timeout=600,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def _guard_list_section(name: str) -> list[str]:
    """`--list` 의 blocked / warned 구획을 정렬해 돌려준다."""
    out = _bash(f'bash "{BUNDLE_GUARD.as_posix()}" --list', cwd=REPO_ROOT)
    lines = out.splitlines()
    start = lines.index(f"{name}:") + 1
    collected: list[str] = []
    for line in lines[start:]:
        if not line.startswith("  "):
            break
        collected.append(line.strip())
    return sorted(collected)


# --- 보호 목록의 내용 ----------------------------------------------------------------


def test_blocked_pattern_list_is_unchanged() -> None:
    """비용을 줄이는 변경이 차단 패턴을 하나도 떨어뜨리지 않는다."""
    assert _guard_list_section("blocked") == sorted(BLOCKED_PATTERNS)


def test_warn_pattern_list_is_unchanged() -> None:
    """경고 패턴도 같은 병합 경로를 지난다 — 한쪽만 고정하면 다른 쪽이 조용히 준다."""
    assert _guard_list_section("warned") == sorted(WARN_PATTERNS)


# --- 병합 비용 -----------------------------------------------------------------------

_CORE_BLOCKED = 14
_CORE_WARN = 5
"""코어 목록(`harness/hooks/lib/guard-lib.sh`)의 패턴 수. 위 골든에서 이만큼을 빼면
언어 팩이 기여한 수가 되고, 그것이 병합이 실제로 일어났는지의 확인이 된다."""

_MERGE_FORK_BUDGET = 10
"""병합 한 벌(protected + warn)이 써도 되는 fork 횟수.

수정 직전 구현은 팩 6개 × (팩 1 + kind 2) × 목록 2벌 만큼 명령 치환을 했고, 실측 fork
**50회분**(631ms)이었다. 한 번에 모으면 남는 것은 호출자의 프로세스 치환 2개뿐이라
실측 fork 1~4회분(약 40ms)이다. 10 은 그 사이에 넉넉히 둔 값이다.

처음에 6 으로 두었더니 한 번 흔들렸다 — fork 1회 비용이 11~29ms 로 2.6배 움직이는
환경이라 분모가 작게 나온 회차에서 예산이 같이 줄었다. 흔들림을 임계로 메우지 않고
분모 쪽 표본을 늘린 뒤(_FORK_SAMPLES) 양쪽 모두에서 다섯 배 이상 여유가 남는 값으로
올렸다. 여유를 줘도 되돌아가면(50회분) 반드시 걸린다.
"""

_FORK_SAMPLES = 40
"""fork 1회 비용을 재는 표본 수. 이 값이 작으면 분모가 흔들려 테스트가 비용이 아니라
그때의 부하를 재게 된다."""


def test_pattern_merge_costs_at_most_a_few_forks() -> None:
    """패턴 병합은 **파일을 읽는 일이 아니라 배열을 잇는 일**이므로 fork 가 거의 없어야 한다.

    fork 1회 비용을 먼저 재고 그 배수로 판정한다. 절대 ms 로 재면 Windows(fork 약 20ms)와
    Linux(약 1ms)에서 임계가 달라져, 한쪽에서는 흔들리고 다른 쪽에서는 공허해진다.
    """
    script = f"""
set -euo pipefail
source "{DETECT_STACK.as_posix()}" 2>/dev/null || true
harness_lang_load_packs || true
now() {{ date +%s%N; }}

# fork 1회 비용({_FORK_SAMPLES}회 평균). printf 는 내장이므로 재는 것은 명령 치환의 fork 다.
t0=$(now)
for _ in $(seq 1 {_FORK_SAMPLES}); do _v="$(printf x)"; done
t1=$(now)

t2=$(now)
_n=0
while IFS= read -r _p; do _n=$((_n + 1)); done < <(lang_all_protected_patterns)
while IFS= read -r _p; do _n=$((_n + 1)); done < <(lang_all_warn_patterns)
t3=$(now)

printf 'fork_ns=%s\\nmerge_ns=%s\\npatterns=%s\\n' \
  $(( (t1 - t0) / {_FORK_SAMPLES} )) $(( t3 - t2 )) "$_n"
"""
    out = _bash(script, cwd=REPO_ROOT)
    values = dict(line.split("=", 1) for line in out.strip().splitlines())
    fork_ns = int(values["fork_ns"])
    merge_ns = int(values["merge_ns"])
    patterns = int(values["patterns"])

    expected = len(BLOCKED_PATTERNS) - _CORE_BLOCKED + len(WARN_PATTERNS) - _CORE_WARN
    assert patterns == expected, (
        f"팩 패턴 수가 달라졌습니다: {patterns} (기대 {expected}). "
        "비용을 재기 전에 병합이 실제로 일어났는지부터 확인합니다"
    )
    assert fork_ns > 0, "fork 비용을 재지 못했습니다 — 임계를 만들 수 없습니다"
    budget_ns = fork_ns * _MERGE_FORK_BUDGET
    assert merge_ns <= budget_ns, (
        f"패턴 병합이 {merge_ns / 1e6:.0f}ms(fork {merge_ns / fork_ns:.0f}회분)를 썼습니다. "
        f"예산은 fork {_MERGE_FORK_BUDGET}회분({budget_ns / 1e6:.0f}ms)입니다 — "
        "순수 bash 연산을 명령 치환으로 감싸면 비용이 팩 수에 비례합니다"
    )


# --- 필드 추출 프로세스 수 -------------------------------------------------------------


def _grep_shim(log: Path) -> Path:
    """인자를 기록하고 진짜 grep 으로 넘기는 래퍼. PATH 앞에 놓는다."""
    shim_dir = log.parent / "shim"
    shim_dir.mkdir(parents=True, exist_ok=True)
    script = shim_dir / "grep"
    # 두 경로 모두 공백이 있는 Windows 경로일 수 있으므로 POSIX 표기 + 인용이다
    # (`exec C:\\Program Files\\…\\grep.exe` 는 공백에서 갈라져 조용히 실패한다, 실측).
    script.write_text(
        "#!/usr/bin/env bash\n"
        f'printf \'%s\\n\' "$*" >> "{log.as_posix()}"\n'
        f'exec "{Path(_GREP).as_posix()}" "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    script.chmod(0o755)
    return shim_dir


def _run_guard_counting_grep(root: Path, payload: str) -> tuple[int, int]:
    """가드를 돌리고 (종료 코드, grep 프로세스 수)를 돌려준다."""
    log = root.parent / "grep-calls.log"
    if log.exists():
        log.unlink()
    shim_dir = _grep_shim(log)
    result = subprocess.run(
        [_BASH, str(WRAPPER), "--root", str(root)],
        input=payload,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "PATH": f"{shim_dir.as_posix()}{os.pathsep}{os.environ.get('PATH', '')}",
        },
        check=False,
    )
    calls = 0
    if log.exists():
        calls = len(log.read_text(encoding="utf-8").splitlines())
    return result.returncode, calls


def _payload(tool_name: str, tool_input: dict[str, str]) -> str:
    return json.dumps({"tool_name": tool_name, "tool_input": tool_input})


def _copy_bundle(root: Path) -> None:
    shutil.copytree(REPO_ROOT / "harness", root / "harness")


def test_wrapper_field_extraction_spawns_at_most_one_grep(tmp_path: Path) -> None:
    """래퍼가 보는 필드는 7개(tool_name·file_path·path·notebook_path·command·pattern·glob)
    지만, 추출은 **한 번**이어야 한다.

    증거 경로(`evaluation/runs/`) 페이로드는 번들 가드로 위임하지 않고 래퍼에서 끝나므로,
    여기서 세는 grep 은 래퍼의 것뿐이다. 수정 직전에는 필드마다 파이프라인을 새로
    띄워 7회였다.
    """
    _copy_bundle(tmp_path)
    payload = _payload("Write", {"file_path": "evaluation/runs/2026-10-11-x.md", "content": "x"})

    code, calls = _run_guard_counting_grep(tmp_path, payload)

    assert code == 0, f"증거 경로는 허용이어야 합니다 (exit {code})"
    assert calls <= 1, (
        f"필드 7개를 뽑으려고 grep 을 {calls}번 띄웠습니다 — 한 번의 추출로 끝나야 합니다"
    )


_CHAIN_GREP_BUDGET = 7
"""`echo hello` 한 줄이 가드 사슬 전체에서 써도 되는 grep 프로세스 수.

수정 직전은 15회였다. 수정 뒤 남는 7회의 내역(2026-10-11 실측, PATH 로그에서 그대로 셈):

  1  래퍼  필드 7개를 한 번에 추출
  1  래퍼  명령에서 경로 같은 토큰 뽑기
  1  번들  필드 추출(한 번)
  4  번들  변경 대상 찾기 — 리다이렉션 / tee / 제자리 편집 여부 / 복사 계열 여부

뒤의 4회는 "무엇을 고치려는 명령인가" 를 보는 **판정**이다. 비용이 아니라 검출력이 이 훅의
존재 이유이므로 그쪽은 줄이지 않는다(후보 2026-10-11-002 의 거부 항목).
예산을 실측값에 딱 맞춰 둔다 — 이 수는 타이밍이 아니라 프로세스 수라서 흔들리지 않고,
한 자리라도 늘면 그것이 의도된 변경인지 리뷰에서 묻게 된다.
"""


def test_whole_chain_stays_within_the_grep_budget(tmp_path: Path) -> None:
    """무해한 명령 하나가 가드 사슬 전체에서 띄우는 프로세스를 고정한다.

    `echo hello` 는 보호 경로를 하나도 건드리지 않는데도 수정 직전에는 2.2~3.3초가 들었다
    (improvement-log 2026-10-11-002). 에이전트 작업의 단위가 셸 명령이므로 이 상수는
    세션 전체에 곱해진다.
    """
    _copy_bundle(tmp_path)
    payload = _payload("Bash", {"command": "echo hello"})

    code, calls = _run_guard_counting_grep(tmp_path, payload)

    assert code == 0, f"무해한 명령은 허용이어야 합니다 (exit {code})"
    assert calls <= _CHAIN_GREP_BUDGET, (
        f"`echo hello` 하나에 grep 프로세스 {calls}개를 썼습니다 (예산 {_CHAIN_GREP_BUDGET}개)"
    )


# --- 값: 한 번의 추출이 필드마다의 추출과 같은 답을 내는가 -------------------------------


def test_escaped_quote_in_command_is_still_extracted(tmp_path: Path) -> None:
    """명령 안의 `\\"` 때문에 문자열이 일찍 끝나면 뒤에 있는 보호 경로를 못 본다.

    한 번의 추출로 바꿀 때 가장 깨지기 쉬운 자리다 — 값의 경계를 잘못 잡으면 가드가
    **덜 막는** 쪽으로 틀린다.
    """
    _copy_bundle(tmp_path)
    payload = _payload("Bash", {"command": 'echo "a\\"b" > harness.config'})

    code, _ = _run_guard_counting_grep(tmp_path, payload)

    assert code == 2, "따옴표가 섞여도 harness.config 로의 리다이렉션은 막아야 합니다"


def test_windows_backslash_path_is_still_blocked(tmp_path: Path) -> None:
    """JSON 의 `\\\\` 를 풀지 않으면 '/' 를 포함한 패턴이 전부 빗나간다
    (guard-evaluation-tampering.sh 의 json_unescape 주석이 기록한 2026-09-05 사건).
    """
    _copy_bundle(tmp_path)
    target = str(tmp_path / "harness" / "scripts" / "verify.sh")
    payload = _payload("Bash", {"command": f"sed -i s/a/b/ {target}"})

    code, _ = _run_guard_counting_grep(tmp_path, payload)

    assert code == 2, f"보호 스크립트의 제자리 편집은 막아야 합니다: {target}"


def test_tool_input_field_wins_over_an_unrelated_key(tmp_path: Path) -> None:
    """한 번에 뽑을 때는 **처음 나온** 값을 쓴다 — 필드마다 뽑던 때와 같은 규칙이다."""
    _copy_bundle(tmp_path)
    payload = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "echo x > harness.config", "description": "무해한 설명"},
        }
    )

    code, _ = _run_guard_counting_grep(tmp_path, payload)

    assert code == 2, "다른 키가 섞여도 command 의 리다이렉션 대상을 봐야 합니다"
