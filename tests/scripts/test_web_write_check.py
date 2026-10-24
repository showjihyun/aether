"""spec 0007 R-8, C-1; D-20 (P5-9): `scripts/web_write_check.py` 의 순수 판정.

서버 액션 id 를 **이름으로** 찾고(해시는 빌드마다 바뀝니다), 응답의 `ok` 를 읽고, 이름이 목록에
보이는지 본다. 못 찾으면 **건너뛰지 않고 실패**해야 한다(건너뛰면 쓰기 경로를 안 지난 초록)."""

from __future__ import annotations

import json

import pytest

from scripts.web_write_check import (
    ACTION_NAME,
    build_graph_args,
    check_listed,
    find_action_id,
    parse_action_result,
)

ID = "60183d1d75e3c405070094edef3bf8a6c7312f1d3d"
CHUNK = (
    f'(0,e.createServerReference)("{ID}",h.callServer,void 0,h.findSourceMapURL,"{ACTION_NAME}")'
)


def test_finds_the_id_by_name_not_by_position() -> None:
    """R-8: 다른 액션 참조가 앞에 있어도 이름으로 가린다."""
    other = (
        '(0,e.createServerReference)("'
        + "ab" * 20
        + '",h.callServer,void 0,h.f,"createAgentAction")'
    )
    assert find_action_id({"a.js": other, "b.js": CHUNK}) == ID


def test_missing_name_is_an_error_not_a_skip() -> None:
    """R-8: 이름이 안 보이면 None 이 아니라 예외 - 조용한 건너뜀 금지."""
    with pytest.raises(LookupError, match=ACTION_NAME):
        find_action_id({"a.js": "no references here"})


def test_no_chunks_is_an_error() -> None:
    """R-8: 청크가 하나도 없어도 예외."""
    with pytest.raises(LookupError):
        find_action_id({})


def test_ok_true_is_accepted() -> None:
    """R-8: 마지막 줄의 ok:true."""
    assert (
        parse_action_result('0:["$@1"]\n1:{"ok":true,"workflowId":"w","version":1}\n')["ok"] is True
    )


def test_ok_false_message_is_carried() -> None:
    """R-8: 거절하면 message 가 실패 문구에 실린다."""
    result = parse_action_result('1:{"ok":false,"message":"이름을 입력하세요."}\n')
    assert result["ok"] is False
    assert "이름" in str(result["message"])


def test_garbage_response_is_an_error() -> None:
    """R-8: 해석 못 하는 응답은 예외(통과 아님)."""
    with pytest.raises(ValueError):
        parse_action_result("<html>500</html>")


def test_name_must_be_in_the_list_html() -> None:
    """R-8: 목록 HTML 에 이름이 없으면 문제."""
    assert check_listed("<td>e2e-ui-1</td>", "e2e-ui-1") == []
    assert check_listed("<td>other</td>", "e2e-ui-1")


def test_graph_args_are_name_and_a_json_string_of_start_to_end() -> None:
    """DESIGN 7.3: 인자는 [이름, 그래프 JSON 문자열]. START->END 한 간선."""
    name, graph = json.loads(build_graph_args("n1"))
    assert name == "n1"
    parsed = json.loads(graph)
    assert [n["kind"] for n in parsed["nodes"]] == ["START", "END"]
    assert len(parsed["edges"]) == 1
