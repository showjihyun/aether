"""spec 0007 R-8, C-1; spec 0006 D-20 (P5-9): 화면의 **쓰기 경로**를 `e2e` 가 지납니다.

`docker compose exec -T api python - web-write-check < scripts/web_write_check.py` 로 api 컨테이너
안에서 돕니다(`web_routes_check.py` 와 같은 방식 - **표준 라이브러리만**, 브라우저 없음).

브라우저의 React 클라이언트가 서버 액션을 부를 때 하는 HTTP 호출을 그대로 합니다
(폼은 고치지 않습니다):
  1. `GET /workflows/new` 의 HTML 에서 `/_next/static/chunks/*.js` 를 모읍니다.
  2. 청크를 받아 `createServerReference)("<hex id>", …, "createWorkflowAction")` 에서
     id 를 **이름으로** 찾습니다.
     (id 는 빌드마다 바뀝니다 - 코드에 적지 않습니다.)
  3. `POST /workflows/new` 에 `Next-Action: <id>`, 본문은 인자 배열 JSON
     `[이름, 그래프 JSON 문자열]`(DESIGN 7.3).
     응답 `text/x-component` 의 마지막 줄이 액션의 반환값입니다 - `ok:true` 여야 합니다.
  4. `GET /workflows` 의 HTML 에 그 이름이 보여야 합니다.

환경변수(비밀이 아닙니다): WEB_BASE_URL(기본 `http://web:3000`),
WEB_WRITE_NAME(만들 Workflow 이름 - 필수).
**조용히 건너뛰지 않습니다**: id 를 못 찾거나, `ok` 가 아니거나, 이름이 안 보이면 실패합니다.
api 키·응답 본문은 출력하지 않습니다(액션의 `message` 는 키·URL 을 담지 않도록 만들어져 있습니다).
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://web:3000"
REQUEST_TIMEOUT_SECONDS = 30.0
ACTION_NAME = "createWorkflowAction"
MAX_CHUNKS = 200

_CHUNK_RE = re.compile(r"/_next/static/chunks/[A-Za-z0-9_.~%-]+\.js")


def chunk_paths(html: str) -> list[str]:
    """HTML(내장 flight 데이터 포함)에 나온 청크 경로, 처음 나온 순서, 중복 없이."""
    return list(dict.fromkeys(_CHUNK_RE.findall(html)))


def find_action_id(chunks: dict[str, str], name: str = ACTION_NAME) -> str:
    """`createServerReference)("<id>", …, "<name>")` 에서 id 를 이름으로 찾는다.

    없으면 LookupError."""
    pattern = re.compile(
        r'createServerReference\)?\(\s*"([0-9a-f]{32,})"\s*,[^()]*?"' + re.escape(name) + r'"\s*\)'
    )
    for text in chunks.values():
        match = pattern.search(text)
        if match:
            return match.group(1)
    raise LookupError(
        f"server action {name!r} not found in {len(chunks)} chunk(s) - "
        "the write path was not exercised (did the page or the bundler output change?)"
    )


def parse_action_result(text: str) -> dict[str, object]:
    """`text/x-component` 의 마지막 줄 `N:{json}` 을 읽는다. 해석 못 하면 ValueError."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty action response")
    match = re.match(r"^\d+:(\{.*\})$", lines[-1])
    if not match:
        raise ValueError(f"unrecognized action response (length {len(text)})")
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError("action response is not JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("action response is not an object")
    return value


def check_listed(body: str, name: str) -> list[str]:
    """목록 HTML 에 이름이 보이는지. 문제 목록(비면 정상). 본문은 문구에 싣지 않는다."""
    if name in body:
        return []
    return [f"/workflows: created name {name!r} not found (body length {len(body)})"]


def build_graph_args(name: str) -> str:
    """서버 액션 인자 배열(JSON 문자열): [이름, 그래프 JSON 문자열]. START -> END 한 간선."""
    graph = {
        "nodes": [{"id": "start-1", "kind": "START"}, {"id": "end-1", "kind": "END"}],
        "edges": [{"source": "start-1", "target": "end-1"}],
    }
    return json.dumps([name, json.dumps(graph)])


def _get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


def _post_action(url: str, action_id: str, payload: str) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        data=payload.encode("utf-8"),
        method="POST",
        headers={"Next-Action": action_id, "Content-Type": "text/plain;charset=UTF-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


def _fail(message: str) -> int:
    sys.stderr.write(f"web_write_check: {message}\n")
    return 1


def main() -> int:
    base = os.environ.get("WEB_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    name = os.environ.get("WEB_WRITE_NAME", "")
    if not name:
        return _fail("WEB_WRITE_NAME is not set")

    try:
        status, page = _get(base + "/workflows/new")
        if status != 200:
            return _fail(f"/workflows/new: status {status} (want 200)")
        paths = chunk_paths(page)[:MAX_CHUNKS]
        if not paths:
            return _fail(
                "/workflows/new: no /_next/static/chunks/*.js referenced - cannot find the action"
            )
        chunks: dict[str, str] = {}
        for path in paths:
            chunk_status, text = _get(base + path)
            if chunk_status == 200:
                chunks[path] = text
        try:
            action_id = find_action_id(chunks)
        except LookupError as exc:
            return _fail(str(exc))

        status, response = _post_action(base + "/workflows/new", action_id, build_graph_args(name))
        if status != 200:
            return _fail(f"action POST: status {status} (want 200)")
        try:
            result = parse_action_result(response)
        except ValueError as exc:
            return _fail(f"action POST: {exc}")
        if result.get("ok") is not True:
            return _fail(f"action POST: ok is not true - message: {result.get('message')!r}")

        status, listing = _get(base + "/workflows")
        if status != 200:
            return _fail(f"/workflows: status {status} (want 200)")
        problems = check_listed(listing, name)
    except (urllib.error.URLError, OSError) as exc:
        return _fail(f"request failed ({type(exc).__name__})")

    if problems:
        for problem in problems:
            sys.stderr.write(f"web_write_check: {problem}\n")
        return 1
    sys.stdout.write(
        "web_write_check: ok - Workflow created through the server action and listed\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
