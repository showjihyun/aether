# MVP-2b — Run 상세(이벤트 타임라인 + trace)

**Run 하나를 열어 무슨 일이 있었는지 봅니다.** 그리고 이 단위는 **500 하나를 고칩니다** — `GET /runs/{id}` 가 Workflow 자식 Run 에서 죽고 있었습니다.

## 무엇이 생겼는가

- **`/runs/{id}`** — `card` 머리(상태 `badge`, Run·trace id, Agent, 요청자, 시각, 실패 사유)와 **탭 둘**(이벤트 타임라인 / 트레이스).
- **`RunTabs`(클라이언트)** — `streamRunEvents` 로 SSE 를 받아 **도착하는 대로** 추가합니다. `seq` 로 정렬하고 같은 `seq` 는 한 번만 그립니다(재생·중복).
- **끊김을 말합니다** — 오류로 끊기거나 `run.finished` 없이 닫히면 `alert`, 그리고 **"다시 연결" 하나**(처음부터 다시 엽니다). 자동 재연결은 **없습니다**.
- **목록에서 들어가는 길** — `/runs` 의 상태 칸이 상세로 가는 링크가 됐습니다(MVP-2a 가 목적지가 없어 비워 둔 자리).
- **`requested_by` 가 nullable** — `RunView`·`RunDetailResponse`, 그리고 `openapi.json`·SDK 생성 타입.

## 왜 그렇게 했는가

- **`pragma: no cover` 가 결함을 숨기고 있었습니다.** `_row_to_view` 는 `requested_by` 가 NULL 이면 `RuntimeError` 를 던졌고, 그 줄에 `# pragma: no cover` 와 "api 는 항상 인증된 principal 로 만듭니다" 라는 주석이 붙어 있었습니다. **Phase 4 부터 그 전제가 거짓**입니다 — Workflow 자식 Run 은 요청자가 없습니다. 목록 경로는 별도 매퍼로 **피해** 갔을 뿐이고(`listings.py:45` 가 그 사실을 적고 있습니다), 상세만 남아 500 이었습니다.
- **`RunAccepted` 는 넓히지 않았습니다.** `POST /agents/{id}/run` 은 항상 인증된 principal 이 만듭니다. 거기까지 nullable 로 하면 **실제로 보장되는 것을 버리는** 일입니다 — 그래서 그 응답은 `principal.key_id` 로 채웁니다.
- **"입력" 탭을 만들지 않았습니다.** DESIGN 5절이 적었지만 입력 본문은 **어떤 API 응답에도 없습니다**(`GET /runs/{id}` 는 투영 열만 읽습니다). 내용이 "API 가 돌려주지 않습니다" 한 줄인 탭은 9절이 금지하는 자리표시입니다 — Workflow 노드에 "준비 중" 을 두지 않기로 한 것과 같은 것입니다. DESIGN 을 고쳤습니다.
- **재연결 정책을 발명하지 않았습니다.** 간격·횟수·`Last-Event-ID` 이어보기는 전부 새 결정이고, SSE 의 재접속 이어보기는 **보장되지 않습니다**(spec 0002 6절). 그래서 끊김을 **보이고** 사람이 누르는 수단 하나만 둡니다.
- **스트림을 `RunTabs` 가 소유합니다** — 탭을 옮겨도 다시 열리지 않습니다(테스트로 고정).
- **payload 와 trace id 는 `<pre>` 에 텍스트로만.** 도구 출력과 인자는 외부에서 온 값입니다(DESIGN 6절 = 신뢰 경계).

## 하네스 근거

| 줄 | 내용 |
| --- | --- |
| **요구** | spec 0006 **R-5**(화면이 실제 데이터로 뜬다 — **아래 "남긴 것" 을 보십시오. 이 단위는 그것을 주장하지 않습니다**) |
| **결정** | **D-14**(상세 응답의 `requested_by` 를 nullable — D-11 의 "기존 스키마 변경 0건" 에 대한 예외 1건, spec 개정 3) |
| **단계** | `api-integration`(**실제 DB** 에서 `requested_by` 가 NULL 인 자식 Run 의 상세가 200 이고 그 필드가 `null`) · `api-unit`·`api-typecheck`·`api-arch`(14 kept) · `web-unit`(이벤트가 `seq` 순서, `run.finished` 가 마지막, 중복 무시, 끊김 표시, 탭 이동이 스트림을 다시 열지 않음) · `web-arch`·`web-build`(`ƒ /runs/[id]`) · `check-sdk-drift`(`openapi.json` ↔ 생성 타입) |
| **증거** | PR 본문. `RuntimeError: control.runs … has no requested_by` 가 red 의 원문입니다 |

## 정한 것과 다른 점

- **"입력" 탭이 없습니다**(위). DESIGN 5절을 고쳤습니다.
- **`RunAccepted` 의 채우는 값이 바뀌었습니다** — `view.requested_by` → `principal.key_id`. 같은 값이지만, `RunView` 가 nullable 이 되면서 타입이 그 경로를 막았습니다.
- **새 환경변수 `AETHER_PUBLIC_API_URL`** — 브라우저가 닿는 주소는 서버가 닿는 주소와 다를 수 있습니다. **compose 에 넣지 않았고 이름도 확정이 아닙니다**(아래 결정에 딸린 것입니다).
- **`/runs` 의 행 전체가 아니라 상태 칸만 링크**입니다 — `CopyableId` 가 `<button>` 이라 행 전체를 `<a>` 로 감쌀 수 없습니다(중첩 금지).

## 남긴 것

**🔒 이 화면들은 실제 스택에서 데이터를 못 가져옵니다 — 알려진 결함입니다(미측정이 아닙니다).**

세 화면(`/agents`·`/runs`·`/runs/{id}`)이 전부 `createClient({ baseUrl })` 만 부르고 **API 키를 넘기지 않습니다.** api 는 `/healthz` 와 문서 경로를 뺀 모든 경로에 `Authorization: Bearer` 를 요구합니다(spec 0001 2.9). 그래서 실제 스택에서 세 화면은 **오류 상태**를 보입니다. 홈 화면만 동작하는데 그것은 `/healthz` 라서입니다. 타임라인은 그 위에 **CORS** 도 필요합니다(api 에 CORS 설정이 없습니다).

**이것은 예고된 결정입니다** — spec 0002 **C-4** 가 "브라우저 화면이 SSE 를 직접 열어야 하는 시점(**MVP-2 이전**)에 인증 변경이 필요하고 그것은 사람 결정" 이라고 기한까지 적어 뒀습니다. 그 기한이 지났고 결정되지 않은 채였습니다. 인증·비밀값에 닿으므로 고치지 않고 사람 검토로 올렸고, **그 자리에서 결정이 내려졌습니다** — **web 서버가 중계한다**(spec 0006 **D-15**, 2026-10-18). 키는 web 컨테이너 안에만 있고 브라우저로 가지 않습니다. 구현은 **MVP-2p** 이고 **MVP-2c 보다 앞**입니다. 그래서 이 단위는 **R-5 를 통과했다고 적지 않습니다** — 그것이 참이 되는 자리는 MVP-2p 와 MVP-4 입니다.

**아무 단계도 이것을 보지 못합니다.** `web-unit` 은 SDK 를 가짜로 바꾸므로 인증 경로가 없고, `api-integration` 은 api 만, `smoke` 는 web 을 띄우지 않습니다. 처음 보는 것은 **MVP-4 의 `e2e`** 입니다. 후보 `improvement-log/2026-10-18-004.yaml` 에 그 공백을 적었습니다.

그 밖에:

- **브라우저에서 눈으로 확인하지 않았습니다** — jsdom 단위 테스트와 `next build` 까지입니다. 다크 모드·반응형도 보지 않았습니다.
- **실제 Run 의 이벤트가 화면에 나타나는 것**은 plan 이 `e2e`(MVP-4)로 둡니다. 지금 증거는 가짜 스트림입니다.
- **취소 버튼은 범위 밖**입니다(API 는 있습니다).
- **`Last-Event-ID` 이어보기를 쓰지 않습니다** — "다시 연결" 은 항상 처음부터입니다.
