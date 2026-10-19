"""spec 0006 R-5, D-20 (MVP-4): `scripts/web_routes_check.py` 의 판정(`evaluate`)과 nav 드리프트."""

from __future__ import annotations

import re

from scripts.web_routes_check import LIST_ERROR_TEXT, MISSING_KEY_TEXT, ROUTES, evaluate
from tests.scripts._fake_docker import REPO_ROOT


def test_ok_page_has_no_problems() -> None:
    """R-5: 200 이고 두 오류 화면이 아니고 기대 이름이 있으면 문제 없음."""
    assert evaluate("/agents", 200, "<td>smoke-abc</td>", "smoke-abc") == []


def test_non_200_is_a_problem() -> None:
    """R-5: 404 는 문제."""
    assert evaluate("/runs", 404, "", None)


def test_missing_key_screen_is_a_problem() -> None:
    """R-5: 키 없음 화면은 200 이어도 문제(D-15)."""
    assert evaluate("/runs", 200, f"<h5>{MISSING_KEY_TEXT}</h5>", None)


def test_list_error_screen_is_a_problem() -> None:
    """R-5: 목록 오류 화면은 200 이어도 문제."""
    assert evaluate("/knowledge", 200, f"<h5>{LIST_ERROR_TEXT}</h5>", None)


def test_expected_name_missing_is_a_problem() -> None:
    """D-20: 이 실행이 만든 이름이 안 보이면 문제."""
    problems = evaluate("/workflows", 200, "<td>other</td>", "wf-1")
    assert problems and any("wf-1" in p for p in problems)


def test_problems_never_echo_the_body() -> None:
    """비밀 방지: 본문 전체를 문제 문구에 싣지 않는다."""
    secret = "SECRET-BODY-MARKER"
    problems = evaluate("/agents", 500, f"{secret} {MISSING_KEY_TEXT}", "x")
    assert not any(secret in p for p in problems)


def test_routes_cover_every_nav_item_and_root() -> None:
    """R-5: 사이드바가 늘면 이 테스트가 깨진다(nav 드리프트)."""
    source = (REPO_ROOT / "apps/web/components/nav-items.ts").read_text(encoding="utf-8")
    hrefs = re.findall(r'href:\s*"([^"]+)"', source)
    assert len(hrefs) >= 5
    assert set(hrefs) <= set(ROUTES)
    assert "/" in ROUTES


def test_runs_screen_requires_a_value() -> None:
    """R-5 리뷰(2026-10-19): `/runs` 에 기대값이 없으면 빈 목록도 통과합니다 - R-5 가 이름으로
    부르는 화면이라 "실제 데이터로 뜬다" 를 값으로 봅니다."""
    from scripts.web_routes_check import _EXPECT_ENV

    assert _EXPECT_ENV["/runs"] == "WEB_EXPECT_RUN"
