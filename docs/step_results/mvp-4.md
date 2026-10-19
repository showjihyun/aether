# MVP-4 — 로드맵 10장이 테스트 하나가 되고, 화면이 처음으로 실제 데이터를 보입니다

`scripts/e2e.sh` 가 사슬 끝까지 갑니다. 네트워크를 끊은 compose 에서 **Knowledge 적재 → MCP·Knowledge 바인딩 Agent → 도구 허용 → Workflow 실행 → 성공**이 한 스크립트의 exit 코드가 됐습니다(**R-10**). 그리고 같은 스택에 `web` 을 띄워 **그 실행이 만든 이름이 화면에 보이는지**를 봅니다 — `web-unit` 은 SDK 를 가짜로 바꾸므로 영원히 볼 수 없는 것이고, 그래서 **R-5 의 나머지 절반이 여기서 처음 참이 됩니다**(`improvement-log/2026-10-18-004`).

## 무엇이 생겼는가

| 조각 | 내용 |
| --- | --- |
| `scripts/smoke_client.py` → `scenario_offline` | 사슬 전체를 api 컨테이너 안에서 한 번에. Knowledge Set 생성 → 적재(`succeeded` 까지 폴링) → MCP·Knowledge 바인딩 Agent → `aether-api permissions allow` → `POST /workflows`(START→AGENT→END) → `POST /workflows/{id}/runs` → `GET /workflow-runs/{id}` 가 `succeeded`. 화면이 찾을 **이름들**을 한 줄 JSON 으로 돌려줍니다 |
| `scripts/web_routes_check.py` | 새 파일. api 컨테이너 안의 표준 라이브러리 python 이 `http://web:3000` 의 여섯 경로를 쳐서 렌더된 HTML 의 **텍스트만** 봅니다. 판정은 순수 함수 `evaluate` 에 있습니다 |
| `scripts/e2e.sh` | 임베딩 모델도 받고(**D-19**), 1단계에서 web 이미지를 확보하고, 3단계에서 `scenario_offline`(R-10)과 화면 확인(R-5)을 더합니다 |
| `infra/docker/compose.e2e.yaml` | `web` 의 호스트 포트도 비웁니다 — 개발 스택의 3000 과 겹칩니다 |

## 왜 그렇게 했는가

사슬의 고리마다 **값**을 봅니다 — "통과했다" 가 아니라 무엇이 참이 됐는지입니다(spec 2.11 의 표). 적재는 청크 수, Agent 는 선언과 **허용**, Workflow 는 `succeeded`, 화면은 **이 실행이 만든 이름**입니다. 그리고 시작할 때 둘이 드러났습니다.

**1. 적재에 모델이 하나 더 필요합니다(D-19).** R-10 의 사슬에 "Knowledge 적재" 가 있는데 적재는 `ModelGateway.embed` 로 갑니다. `e2e` 는 지금까지 **채팅 모델 하나만** 받고 있었고, 그 스택에서 적재를 한 번도 해 보지 않았기 때문에 드러나지 않았습니다. `fetch-model.sh` 를 두 번 부릅니다(`qwen2.5:0.5b` + `nomic-embed-text`). 부팅 경로는 여전히 아무것도 받지 않습니다(R-9 는 그대로).

**2. R-5 를 판정할 자리가 여기뿐입니다(D-20).** 그래서 `web` 을 같은 오프라인 스택에 띄웁니다. 키는 **발급된 뒤에** web 을 띄워 환경변수로만 넣습니다(서버가 읽습니다) — 그래서 web 의 `up` 이 `keys create` 뒤에 와야 하고, 테스트가 그 순서를 고정합니다.

같은 자리에서 **문서 불일치 하나**를 고쳤습니다: spec 0006 의 R-5 는 "**네** 화면/네 경로" 인데 `NAV_ITEMS`·plan·backlog 는 **다섯**입니다 — D-13 이 `/settings` 를 더한 뒤로 spec 만 낡아 있었습니다. 조용히 고르지 않고 spec 을 맞추고 개정 7 에 적었습니다.

## 정한 것과 다른 점

**plan 은 `scripts/e2e.sh` 하나를 적었는데 스크립트가 둘이 됐습니다.** 화면 확인을 셸에 섞으면 판정 로직(상태·두 오류 화면·기대값)이 테스트할 수 없는 자리에 들어갑니다 — `scripts/web_routes_check.py` 로 떼고 `evaluate` 를 순수 함수로 두어 컨테이너 없이 다섯 분기를 고정했습니다. plan 과 backlog 를 그에 맞게 고쳤습니다.

**R-8 의 기존 `scenario` 를 `scenario_offline` 으로 대체하지 않았습니다.** 둘 다 돕니다 — 이미 초록인 R-8 의 증거(직접 Run 하나가 `succeeded`)를 새 사슬에 얹어 바꾸면, 실패했을 때 어느 쪽이 깨졌는지 구별되지 않습니다.

## 리뷰에서 고친 둘

**적재가 `succeeded` 인 것만으로는 Knowledge 고리가 빕니다.** 적재는 **아무것도 쌓지 않아도 `succeeded`** 가 되고, 상태 API 가 청크 수를 내지 않습니다(spec 0004 2.4). `smoke` 는 그 구멍을 psql 실측으로 막고 있는데(`"ingestion reported succeeded but stored no chunks"`), 위임된 구현은 상태만 보고 있었습니다 — **실제 임베딩이 도는 유일한 자리**가 더 느슨할 이유가 없습니다. 청크 수를 시나리오 **앞뒤로** 재고 늘지 않으면 `R-10` 으로 실패합니다. red: `FAKE_CHUNK_SEQ="7 7"` 에서 exit 0. 변이: `-gt` → `-ge` 로 바꾸니 그 테스트가 다시 실패했습니다.

**`/runs` 에 기대값이 없어 빈 목록도 통과했습니다.** `/runs` 는 R-5 가 이름으로 부르는 화면인데, 기대값이 없으면 "200 이고 오류 화면이 아니다" 까지만 봅니다. Run 의 id 는 전체가 HTML 에 있습니다(`CopyableId` 의 `title`, 상세 링크의 `href`) — R-8 시나리오가 돌려준 `run_id` 를 그 화면에서 찾습니다. red: 확인 호출에 `WEB_EXPECT_RUN` 이 없었습니다. 변이: 그 `-e` 이름만 바꾸니 실패했습니다.

## 하네스 근거

| 줄 | 내용 |
| --- | --- |
| **요구** | spec 0006 **R-10**(사슬)과 **R-5 의 나머지 절반**(화면이 실제 데이터로 뜬다) |
| **결정** | **D-19**(모델 둘) · **D-20**(web 을 같은 스택에서 확인) · 기존 D-6·D-12 는 그대로 |
| **단계** | `e2e`(이 단위가 늘린 스크립트) · `harness-scripts`(가짜 docker 로 순서·실패 판정) · `api-unit` · `api-lint`·`api-typecheck` |
| **증거** | PR 본문. red 는 위임 4건(임베딩 pull·web up·R-5 실패·R-10 실패) + 수집 실패 2건, 리뷰 3건 |

## 단언하지 않는 것

적지 않으면 다음 사람이 통과를 과대 해석합니다(spec 2.11 의 같은 표).

- **MCP 도구 호출이 실제로 일어났다는 것.** 소형 모델이 도구를 부를지는 비결정적입니다. 이 단위가 단언하는 것은 "선언 + **허용**(기본 deny 를 넘었다) + Workflow Run 이 `succeeded`" 입니다. 도구 호출 자체는 `smoke` 의 `scenario_tool` 이 fake 어댑터의 `TOOL_CALL` 마커로 **결정적으로** 봅니다.
- **검색 결과가 Context 에 들어간 양.** 그 값은 collector 출력에 있고 `smoke` 가 소유합니다(spec 0004 2.9.1). 여기서는 청크가 쌓였다는 것까지입니다.
- **모델 답변의 품질**(D-12)과 **화면의 시각적 모양** — 브라우저를 띄우지 않습니다. 사람의 눈이 남은 몫입니다.

## 남긴 것

`web` 이미지가 CI 의 bake 목록(`.github/workflows/harness.yml`, **보호 파일**)에 없어 `e2e` 안에서 캐시 없이 빌드됩니다. `smoke` 는 `SMOKE_NO_BUILD=1` 로 bake 이미지를 쓰는데 `e2e` 는 그렇지 않아 api·worker 까지 다시 빌드합니다 — 이 비대칭 자체가 측정 거리입니다. 예산을 넘기면 **사람이 봅니다**(EI-2): 선택지는 예산 상향이거나 bake 목록에 `web` 을 더하고 `E2E_NO_BUILD=1` 을 주는 것입니다. 에이전트는 임계를 올리지 않습니다.

## 관련 문서

- [../../specs/0006-mvp-integration.md](../../specs/0006-mvp-integration.md) — R-5·R-10, 2.11, D-19·D-20
- [../../plans/0006-mvp-integration.md](../../plans/0006-mvp-integration.md) — MVP-4 절, 개정 5
- [mvp-3.md](mvp-3.md) — 이 스크립트가 처음 생긴 단위(R-8·R-9·C-5)
- [README.md](README.md) — 단계 결과 모음
