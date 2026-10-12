"""spec 0004 R-7, 2.9.1: `smoke` 의 Knowledge 적재·검색 시나리오.

R-7("적재가 **오프라인에서** 동작한다")은 Phase 3 이 끝날 때까지 **게이트 커버리지가
0** 이었습니다. spec 2.9.1 이 그 이유를 적고 있습니다 — P3-2b 시점에는 검색의 HTTP
경로가 없어 `smoke` 가 API 로 확인할 방법이 없었고, 보조 스크립트로 어댑터를 직접
부르는 것은 "smoke 는 제품이 쓰는 경로를 본다" 는 성질을 깨므로 하지 않았습니다.
P3-3 이 그 경로를 만들었고, 2026-10-12 의 수동 확인이 실제 모델로 한 번 돌렸습니다
(docs/step_results/phase-3.md "P3-3 수동 확인"). 이제 그것을 게이트로 옮깁니다.

**이 파일이 고정하는 것과 고정하지 못하는 것.**

고정하는 것은 "시나리오가 존재하고, 제품 경로를 지나고, 검색 결과가 Context 에
들어갔는지를 **값으로** 확인한다" 입니다. HTTP 왕복 자체는 `smoke.sh` 의 통합 실행만이
판정합니다(`test_smoke_client.py` 의 머리말과 같은 분담) — 그래서 여기서는 순수 함수와
스크립트의 **계약**을 봅니다.

고정하지 **못하는** 것은 검색의 품질입니다. `smoke` 는 fake 어댑터로 돌고 그 어댑터의
`embed` 는 해시 벡터이므로(adapters/outbound/model_gateway/fake.py), 어느 청크가 1위가
되는지는 의미가 없습니다. 그래서 시나리오는 "무엇이 검색됐나" 가 아니라 "검색이 **일어나
Context 에 들어갔나**" 를 봅니다 — R-7 이 요구하는 "검색 1건 성공" 이 그것입니다.
실제 임베딩의 품질은 수동 확인(D-13)과 `api-integration` 이 소유합니다.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SH = REPO_ROOT / "scripts" / "smoke.sh"
WORKER_DOCKERFILE = REPO_ROOT / "infra" / "docker" / "worker.Dockerfile"

KNOWLEDGE_ATTRIBUTE = "context.tokens.knowledge"


def test_worker_image_bakes_the_knowledge_fixture() -> None:
    """적재할 디렉터리는 **worker 이미지에** 있어야 한다.

    `FilesystemConnector` 는 worker 에서 돌고, smoke 의 HTTP 클라이언트는 api 컨테이너
    안에서 돈다 — 클라이언트가 파일을 써도 worker 는 보지 못한다. 그래서 Filesystem MCP
    의 fixture(`/srv/mcp-filesystem/smoke.txt`)와 같은 방식으로 빌드 시점에 굽는다.
    """
    text = WORKER_DOCKERFILE.read_text(encoding="utf-8")

    from scripts.smoke_client import SMOKE_KNOWLEDGE_SOURCE

    assert SMOKE_KNOWLEDGE_SOURCE in text, (
        f"worker.Dockerfile 이 {SMOKE_KNOWLEDGE_SOURCE} 를 만들지 않습니다 — "
        "적재할 디렉터리가 worker 컨테이너에 없으면 시나리오가 404 가 아니라 "
        "빈 적재로 조용히 성공합니다"
    )
    assert ".txt" in text, "fixture 디렉터리에 문서 파일이 있어야 합니다"


def test_client_exposes_the_knowledge_scenario_command() -> None:
    """`smoke.sh` 가 부를 수 있는 명령이어야 한다 — dispatch 와 usage 둘 다."""
    from scripts import smoke_client

    assert hasattr(smoke_client, "scenario_knowledge"), (
        "smoke_client 에 scenario_knowledge 가 없습니다"
    )
    source = Path(smoke_client.__file__).read_text(encoding="utf-8")
    assert 'command == "scenario_knowledge"' in source, (
        "main 의 dispatch 에 scenario_knowledge 가 없습니다 — 함수만 있으면 "
        "smoke.sh 가 부를 수 없습니다"
    )
    assert "scenario_knowledge" in source.split("usage:")[1][:200], (
        "usage 문자열에 scenario_knowledge 가 없습니다"
    )


def test_knowledge_agent_definition_binds_the_set() -> None:
    """Agent 정의가 적재한 집합을 **이름으로** 바인딩해야 한다(spec 0004 2.2, D-5).

    바인딩이 없으면 Run 은 성공하지만 검색을 하지 않는다 — 그러면
    `context.tokens.knowledge` 가 아예 없고, 시나리오는 "성공했지만 아무것도 확인하지
    않은" 상태가 된다. 그 조용한 구멍을 여기서 막는다.
    """
    from scripts.smoke_client import knowledge_agent_body

    body = knowledge_agent_body("docs-abc")
    definition = body["definition"]

    assert definition["knowledge"] == ["docs-abc"]
    assert definition["knowledge_top_k"] >= 1
    assert definition["tools"] == [], "이 시나리오는 도구를 쓰지 않습니다"
    assert definition["system_prompt"].strip(), "system_prompt 는 비어 있을 수 없습니다"


def test_smoke_waits_for_a_positive_knowledge_context_attribute() -> None:
    """`smoke.sh` 가 `context.tokens.knowledge` 를 **값으로** 확인해야 한다.

    속성의 존재만 보면 0 토큰도 통과한다. 지금 구현에서는 검색 결과가 없으면 속성이
    아예 붙지 않으므로(compile_context 가 빈 목록이면 항목을 넣지 않는다) 존재 검사만
    해도 사실상 같지만, 그 성질은 compile_context 의 구현 세부다. 여기서 양수를
    요구하면 그 세부가 바뀌어도 시나리오의 뜻("검색 1건 성공")이 유지된다.
    """
    text = SMOKE_SH.read_text(encoding="utf-8")

    assert KNOWLEDGE_ATTRIBUTE in text, (
        f"smoke.sh 가 {KNOWLEDGE_ATTRIBUTE} 를 확인하지 않습니다 — "
        "적재만 하고 검색을 보지 않으면 R-7 의 '검색 1건 성공' 이 빠집니다"
    )
    assert "scenario_knowledge" in text, "smoke.sh 가 knowledge 시나리오를 부르지 않습니다"
    # 값 확인용 보조 함수가 있어야 합니다(존재 검사 `_trace_has_attribute` 와 별개).
    assert re.search(r"_trace_attribute_value\s*\(\)", text), (
        "값을 읽는 보조 함수(_trace_attribute_value)가 없습니다 — 존재만 보면 0 토큰이 통과합니다"
    )


def test_smoke_reports_the_ingestion_and_search_facts() -> None:
    """사람이 로그만 보고 무엇이 확인됐는지 알 수 있어야 한다.

    smoke 의 다른 시나리오는 전부 한 줄씩 사실을 남긴다(`smoke: data.tool_call_audit
    rows 0 -> 1 …`). 조용히 통과하는 단계는 다음 사람에게 "돌았는지" 를 알려주지 않는다.
    """
    text = SMOKE_SH.read_text(encoding="utf-8")

    assert "smoke: running knowledge scenario" in text, "시나리오 시작을 알리는 줄이 없습니다"
    assert re.search(r"smoke: knowledge .*chunks", text), (
        "적재된 청크 수를 남기는 줄이 없습니다 — 빈 적재가 조용히 통과합니다"
    )
