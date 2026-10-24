"""MVP-3 스크립트 테스트의 공용 지원: 호출을 기록만 하는 가짜 `docker`(bash 스크립트).

실제 docker 도 compose 프로젝트도 띄우지 않고 `scripts/fetch-model.sh`·`scripts/e2e.sh` 의
**인자 조립·이름 검사·멱등 판단**만 본다. 동작은 환경변수로 정한다.

- `FAKE_DOCKER_LOG`   호출마다 `$*` 한 줄을 덧붙일 파일
- `FAKE_OLLAMA_LIST`  `ollama list` 가 찍을 본문(헤더 포함)
- `FAKE_PS_Q`         `ps -q llm` 이 찍을 내용(비어 있으면 llm 이 꺼져 있음)
- `FAKE_UP_EXIT` / `FAKE_PULL_EXIT` / `FAKE_ALL_EXIT`  각 호출의 종료 코드(기본 0)
- `FAKE_UP_EXIT_SEQ`   `up` 호출마다 차례로 소비할 종료 코드(공백 구분, 예: "1 0")
- `FAKE_LOGS` / `FAKE_SCENARIO_JSON`  `logs`·시나리오 호출의 출력
- `FAKE_SCENARIO_OFFLINE_JSON`  `scenario_offline` 의 출력(일반 `scenario` 분기보다 먼저 가려낸다)
- `FAKE_WEB_CHECK_EXIT`  `web-routes-check` 의 종료 코드(기본 0)
- `FAKE_WEB_WRITE_EXIT`  `web-write-check` 의 종료 코드(기본 0)
- `FAKE_WEB_WRITE_OUT`  `web-write-check` 의 출력(기본은 성공 표식, 빈 값이면 아무것도 안 한 확인)
- `FAKE_CHUNK_SEQ`  `psql` 호출마다 차례로 소비할 숫자(기본 "0 3" = 적재가 청크를 쌓았다)
- `FAKE_PROBE_EXIT`  외부 접속 시도의 결과(0=막힘, 7=닿음)
- `FAKE_NO_RECORD`  pull 이 성공해도 목록에 남기지 않는 서버
- pull 이 성공하면 이후 `ollama list` 에 그 모델이 나타난다(상태는 로그 옆 마커 파일)
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_BASH = shutil.which("bash") or "bash"

_FAKE = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_DOCKER_LOG"
OFFLINE_DEFAULT='{"status":"succeeded","agent_name":"a-1","knowledge_set_name":"k-1","workflow_name":"w-1"}'
if [ -n "${FAKE_ALL_EXIT:-}" ]; then exit "$FAKE_ALL_EXIT"; fi
case " $* " in
  *" ollama list"*)
    printf '%s
' "${FAKE_OLLAMA_LIST:-NAME ID SIZE MODIFIED}"
    if [ -f "$FAKE_DOCKER_LOG.pulled" ]; then printf '%s
' "$(cat "$FAKE_DOCKER_LOG.pulled") x 1 MB now"; fi
    exit 0 ;;
  *" ollama pull "*)
    if [ "${FAKE_PULL_EXIT:-0}" = 0 ] && [ -z "${FAKE_NO_RECORD:-}" ]; then
      m="${!#}"; case "$m" in *:*) ;; *) m="$m:latest" ;; esac   # 실제 list 는 :latest
      printf '%s' "$m" > "$FAKE_DOCKER_LOG.pulled"
    fi
    exit "${FAKE_PULL_EXIT:-0}" ;;
  *" ps -q"*) printf '%s' "${FAKE_PS_Q:-}"; exit 0 ;;
  *" e2e-offline-probe "*) exit "${FAKE_PROBE_EXIT:-0}" ;;
  *" psql "*)
    seq="$FAKE_DOCKER_LOG.sqlseq"
    if [ ! -f "$seq" ]; then printf '%s' "${FAKE_CHUNK_SEQ:-0 3}" > "$seq"; fi
    v="$(awk '{print $1}' "$seq")"; rest="$(awk '{$1=""; sub(/^ /,""); print}' "$seq")"
    printf '%s' "$rest" > "$seq"
    printf '%s' "${v:-0}"
    exit 0 ;;
  *" scenario_offline"*)
    printf '%s
' "${FAKE_SCENARIO_OFFLINE_JSON:-$OFFLINE_DEFAULT}"; exit 0 ;;
  *" web-routes-check "*) exit "${FAKE_WEB_CHECK_EXIT:-0}" ;;
  *" web-write-check "*)
    printf '%s
' "${FAKE_WEB_WRITE_OUT-web_write_check: ok - fake}"
    exit "${FAKE_WEB_WRITE_EXIT:-0}" ;;
  *" scenario"*) printf '%s
' "${FAKE_SCENARIO_JSON:-{\"run_id\":\"r\",\"status\":\"succeeded\"}}"; exit 0 ;;
  *" keys create"*) echo "fake-key"; exit 0 ;;
  *" logs "*) printf '%s
' "${FAKE_LOGS:-}"; exit 0 ;;
  *" up "*)
    seq="$FAKE_DOCKER_LOG.upseq"
    if [ ! -f "$seq" ]; then printf '%s' "${FAKE_UP_EXIT_SEQ:-${FAKE_UP_EXIT:-0}}" > "$seq"; fi
    code="$(awk '{print $1}' "$seq")"; rest="$(awk '{$1=""; sub(/^ /,""); print}' "$seq")"
    printf '%s' "$rest" > "$seq"
    exit "${code:-${FAKE_UP_EXIT:-0}}" ;;
esac
exit 0
"""


def run_script(
    tmp_path: Path, script: str, args: list[str], env_extra: dict[str, str] | None = None
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """`scripts/<script>` 를 가짜 docker 와 함께 실행한다. `(결과, docker 호출 목록)`."""
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True)
    fake = bindir / "docker"
    fake.write_text(_FAKE, encoding="utf-8", newline="\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "docker.log"
    env = dict(os.environ)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["FAKE_DOCKER_LOG"] = log.as_posix()
    env.update(env_extra or {})
    result = subprocess.run(
        [_BASH, str(REPO_ROOT / "scripts" / script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=REPO_ROOT,
        check=False,
        timeout=120,
    )
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, calls
