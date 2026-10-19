"""spec 0006 R-5, D-20 (MVP-4): 오프라인 e2e 스택의 `web` 화면 확인.

`docker compose exec -T api python - web-routes-check < scripts/web_routes_check.py` 로
api 컨테이너 안에서 돕니다(`smoke_client.py` 와 같은 방식 - **표준 라이브러리만**).
`http://web:3000` 의 경로를 쳐서 렌더된 HTML 의 **텍스트만** 봅니다(브라우저 없음).

환경변수(전부 비밀이 아닙니다):
  WEB_BASE_URL          기본 `http://web:3000`
  WEB_EXPECT_AGENT      `/agents` 에서 찾을 이름
  WEB_EXPECT_KNOWLEDGE  `/knowledge` 에서 찾을 이름
  WEB_EXPECT_WORKFLOW   `/workflows` 에서 찾을 이름
  WEB_EXPECT_RUN        `/runs` 에서 찾을 Run id(전체 - `CopyableId` 의 `title` 과 상세 링크의 href)
`/` 와 `/settings` 만 기대값이 없습니다(목록이 아닙니다).

문제로 보는 것: 200 이 아님 / "키 없음" 화면 / "목록 오류" 화면 / 기대 이름이 없음.
**어떤 경우에도 api 키·환경변수 값·응답 본문을 출력하지 않습니다**(본문은 길이만).
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://web:3000"
REQUEST_TIMEOUT_SECONDS = 20.0

# `apps/web/components/nav-items.ts` 의 NAV_ITEMS 다섯 + `/`.
# tests/scripts/test_web_routes_check.py 가 드리프트를 잡습니다.
ROUTES = ("/", "/agents", "/runs", "/knowledge", "/workflows", "/settings")

# `apps/web/components/ListStates.tsx` 의 `MissingApiKey` 의 AlertTitle / `ListError` 의 AlertTitle.
MISSING_KEY_TEXT = "api 키가 없습니다"
LIST_ERROR_TEXT = "목록을 불러오지 못했습니다"

_EXPECT_ENV = {
    "/agents": "WEB_EXPECT_AGENT",
    "/knowledge": "WEB_EXPECT_KNOWLEDGE",
    "/workflows": "WEB_EXPECT_WORKFLOW",
    # 기대값이 없으면 **빈 목록도 통과**합니다 - R-5 가 이름으로 부르는 화면이라 값을 요구합니다
    # (리뷰 2026-10-19).
    "/runs": "WEB_EXPECT_RUN",
}


def evaluate(path: str, status: int, body: str, expect: str | None) -> list[str]:
    """한 경로의 문제 목록(비면 정상). 본문을 문구에 싣지 않습니다."""
    problems: list[str] = []
    if status != 200:
        problems.append(f"{path}: status {status} (want 200)")
    if MISSING_KEY_TEXT in body:
        problems.append(f"{path}: shows the missing-api-key screen")
    if LIST_ERROR_TEXT in body:
        problems.append(f"{path}: shows the list-error screen")
    if expect and expect not in body:
        problems.append(f"{path}: expected name {expect!r} not found (body length {len(body)})")
    return problems


def _fetch(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


def main() -> int:
    base = os.environ.get("WEB_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    all_problems: list[str] = []
    for path in ROUTES:
        env_name = _EXPECT_ENV.get(path)
        expect = os.environ.get(env_name) if env_name else None
        if env_name and not expect:
            all_problems.append(f"{path}: {env_name} is not set (cannot check the row)")
            continue
        try:
            status, body = _fetch(base + path)
        except (urllib.error.URLError, OSError) as exc:
            all_problems.append(f"{path}: request failed ({type(exc).__name__})")
            continue
        all_problems.extend(evaluate(path, status, body, expect))
    if all_problems:
        for problem in all_problems:
            sys.stderr.write(f"web_routes_check: {problem}\n")
        return 1
    sys.stdout.write(f"web_routes_check: ok - {len(ROUTES)} routes\n")
    return 0


if __name__ == "__main__":
    # stdin 으로 실행될 때 argv[1] 은 `web-routes-check` 입니다(smoke_client 와 같은 호출 형태).
    sys.exit(main())
