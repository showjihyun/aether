# Plan 0006 — MVP 통합

| 키 | 값 |
| --- | --- |
| 번호 | 0006 |
| 근거 spec | [../specs/0006-mvp-integration.md](../specs/0006-mvp-integration.md) (승인됨 2026-10-17, R-1 ~ R-12 · D-1 ~ D-11) |
| 근거 intent | [../intents/0006-mvp-integration.md](../intents/0006-mvp-integration.md) (승인됨 2026-10-17) |
| 작업 단위 | [../intents/mvp-backlog.md](../intents/mvp-backlog.md) MVP-1 ~ MVP-5 (MVP-2 → **2a·2b·2c** 로 분할) |
| 작성일 | 2026-10-17 |
| 상태 | **초안** — 사람 승인 전입니다 |
| 승인 | (대기) |

spec 이 정한 요구사항(R-1 ~ R-12)·결정(D-1 ~ D-11)은 반복하지 않습니다. 이 문서는 **일곱 단위를 어떤 순서로** 하고, 단위마다 **어느 파일을 누가** 만들며, **무엇으로 판정**하는지를 정합니다. 표기 — **A** 에이전트(`implementer`), **M** 주 세션, **H** 사람(보호 파일·섭외).

이 plan 이 풀어야 하는 문제는 **다섯**입니다.

1. **화면이 데이터 없이 먼저 서지 않게 합니다.** 지금 사이드바는 404 네 개를 가리킵니다 — 껍데기가 먼저 서 있고 내용이 없는 상태가 이미 한 번 일어났습니다. 그래서 **목록 API 와 SDK 가 화면보다 먼저**입니다(MVP-0). 화면 단위는 그것이 끝난 뒤 시작합니다.
2. **계약을 먼저 세웁니다.** CLI 는 제품 코드를 import 하지 않아야 하고(R-2) 그 강제는 `.importlinter` 의 **AR-14** 입니다. 보호 파일이므로 **사람이 먼저 커밋**합니다 — Phase 4 가 AR-13 을 P4-1 앞에 둔 것과 같은 순서입니다. 계약이 먼저 있으면 첫 CLI 코드가 처음부터 위반할 수 없습니다.
3. **`e2e` 단계는 예산 결정과 한 묶음입니다.** spec D-6 이 그 단계를 요구하는데, 더하면 CI 전량이 예산을 넘깁니다(2026-10-17 실측 452,980~605,631 ms / 600,000). 그래서 **`e2e` 를 쓰는 단위(MVP-3·MVP-4)보다 먼저 그 보호 파일 PR 이 가고**, 거기서 사람이 예산을 정합니다. 에이전트는 숫자를 올려 두고 고르지 않습니다(EI-2).
4. **오프라인은 모델 파일이 있어야 판정됩니다.** MVP-3 의 완료 판정이 "네트워크 없이 `succeeded`" 이고 그 전제가 볼륨에 받아 둔 모델입니다(D-5). 그 스크립트와 실패 메시지가 **MVP-3 의 첫 조각**이고, 사람이 한 번 실행해야 그 뒤가 측정됩니다.
5. **TTFSA 는 마지막이고 사람입니다.** MVP-5 는 CLI·화면·오프라인이 전부 끝난 뒤에만 의미가 있습니다(그 전에 재면 "막힌 지점" 이 전부 미구현입니다). 에이전트는 Quickstart 와 양식까지 만들고 **멈춥니다**.

## 1. 순서

| Wave | 단위 | 왜 이 자리인가 | 사람 손 |
| --- | --- | --- | --- |
| 0 | **H-1** `.importlinter` 의 **AR-14** 신설 + AR-5 에 `aether_cli` | 문제 2. 계약이 먼저 | **H** |
| 1 | **MVP-0** 목록 API 넷 + SDK 함수(신설 단위) | 문제 1. 화면이 가리킬 데이터 | — |
| 2 | **MVP-1** Python CLI (`apps/cli`) | AR-14 가 선 뒤 첫 CLI 코드. `e2e` 없이도 통합으로 판정 가능 | — |
| 3 | **H-2** `harness.config` 에 `e2e` 단계 + **예산 결정** | 문제 3. MVP-3·MVP-4 의 판정 수단 | **H** |
| 4 | **MVP-3** 로컬 LLM 과 모델 볼륨 | 문제 4. `e2e` 가 있어야 "네트워크 없이" 를 판정 | **H-3** 모델 1회 적재 |
| 5 | **MVP-2a** 목록 화면 둘(`/runs`·`/agents`) | 데이터가 있고 계약이 선 뒤 | — |
| 6 | **MVP-2b** 상세 화면(`/runs/{id}`: 이벤트 타임라인 + trace) | 2a 의 목록에서 들어갑니다 | — |
| 7 | **MVP-2c** `/knowledge`·`/workflows` 목록과 Agent 대화(스트림) | 남은 404 둘 + 대화. 스트림은 2b 의 이벤트 코드를 재사용 | — |
| 8 | **MVP-4** 오프라인 시나리오 `e2e` | 앞의 전부를 한 테스트로 겹니다 | — |
| 9 | **MVP-5** TTFSA 측정 | 문제 5. 에이전트는 Quickstart·양식까지 | **H-4** 처음 보는 사람 1명 |

**MVP-0 은 backlog 에 없던 단위입니다.** spec D-3 이 요구하는 목록 API 넷과 SDK 함수를 화면 단위에 섞으면, 화면 PR 하나가 API·SDK·UI 를 한꺼번에 들고 와 리뷰가 불가능해집니다. backlog 에 행을 더하는 것은 **M 이 plan 승인과 같은 커밋에서** 합니다.

**MVP-2 를 셋으로 쪼갭니다**(spec C-3). 목록 → 상세 → 대화 순서이고, 각 단위의 완료 판정은 "실제 데이터로 뜬다" 입니다. 디자인은 최소이고 `apps/web/DESIGN.md` 를 따릅니다.

**Wave 1 과 Wave 2 는 서로 독립이지만 동시에 돌리지 않습니다** — `verify.sh` 의 락이 동시 실행을 막고(`2026-10-03-001`), 두 위임이 번갈아 기다리면 벽시계가 늘어납니다. 그리고 2026-10-17 에 **같은 작업 트리에서 동시 편집이 변경을 잃는 사고**가 한 번 있었습니다(`2026-10-17-001`) — 위임은 **한 번에 하나**입니다.

## 2. 단위별 계획

모든 단위는 **red(실패하는 테스트, 실행해 기록) → green → refactor** 순서입니다. `ModuleNotFoundError` 하나로 여러 단언을 갈음하지 않습니다 — 각 단언이 **자기 이유로** 한 번은 실패하는 것을 보여야 합니다. 단위마다 브랜치 하나, PR 하나, 커밋 trailer `Unit: <단위>`.

### H-1 `.importlinter` — AR-14 신설 (H)

| 항목 | 내용 |
| --- | --- |
| 바뀌는 것 | `.importlinter` 에 `ar14-cli-does-not-import-product`(source `aether_cli`, forbidden 제품 패키지 여덟) 신설. AR-5 의 `source_modules` 에 `aether_cli` 추가 |
| 판정 | `api-arch` 가 통과하고, `tests/arch` 에 `aether_cli/_bad.py`(제품 패키지 import) 주입 케이스가 **실패**합니다(R-2). `aether_cli` 가 아직 없으므로 **그 주입 테스트가 계약의 유일한 증거**입니다 — 빈 패키지 `apps/cli/src/aether_cli/__init__.py` 만 먼저 둡니다 |
| 에이전트가 넘기는 것 | 고칠 내용의 diff, red 증거(주입 실패 기록), 그리고 "이 계약이 지금 무엇도 막지 않는다" 는 사실(코드가 없으므로). 사람이 `harness-change` 라벨로 커밋합니다 |

### MVP-0 목록 API 넷과 SDK (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것(api) | `GET /runs`·`GET /workflows`·`GET /workflow-runs`·`GET /knowledge-sets`·`GET /knowledge-sets/{id}/ingestions`. 페이지 규칙은 **`GET /agents` 를 그대로 베낍니다**(새 규약 금지). 필터는 상태 하나 |
| 만드는 것(저장소) | 각 목록의 outbound 포트 메서드와 PostgreSQL 구현. **포트에 메서드를 더하면 fake 가 깨집니다** — 먼저 몇 곳인지 세십시오(`2026-09-28-001`: P2-6 에서 39개가 깨졌습니다) |
| 만드는 것(SDK) | `packages/sdk/src/client.ts` 에 목록 함수 다섯 + Knowledge·Workflow 타입. `openapi.json` 재생성(**추가만**) |
| 판정 | `api-integration`: 다섯 경로가 200 과 페이지 모양, 빈 목록도 200, 잘못된 커서는 4xx. 인증 없으면 401(기존 테스트가 자동 수집). `web-typecheck`: 드리프트 0, **기존 경로·스키마 변경 0건**(R-4·D-11) |
| 주의 | 목록이 `data` 평면을 읽지 않습니다 — Workflow Run 목록도 `control.workflow_runs`(투영)만 봅니다. 노드 실행은 범위 밖(D-4) |

### MVP-1 Python CLI (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `apps/cli` — `aether` 콘솔 스크립트. 명령: `up`(compose), `agent create`·`agent list`, `run <agent>`(스트림 출력), `runs get`. HTTP 는 **표준 라이브러리 `urllib`**(D-1) |
| 만드는 것(계약 확인) | CLI 가 쓰는 경로가 `openapi.json` 에 실재하는지 보는 드리프트 테스트(spec C-1) |
| 판정 | `api-unit`: 각 명령이 fake HTTP 계층으로 요청을 만들고 응답을 포맷(컨테이너 없이). `api-arch`: AR-14 가 발화하고 `httpx`·`requests`·`aiohttp` 가 의존성에 없음(R-3). **격리 compose 통합 1건**: CLI 서브프로세스로 네 명령을 돌려 `succeeded` 와 스트림 출력(R-1) |
| 주의 | 키는 `AETHER_API_KEY` 환경변수로만 받고 파일·로그에 남기지 않습니다(D-8). `up` 이 만드는 임시 `.env` 는 `smoke.sh` 와 같은 방식이고 실행 뒤 지웁니다 |

### H-2 `harness.config` — `e2e` 단계와 예산 (H)

| 항목 | 내용 |
| --- | --- |
| 바뀌는 것 | `HARNESS_STEPS` 에 `e2e`(계층 `behavior`, `required=true`), `HARNESS_DEFERRED_STEPS` 에 `e2e` 추가. 스크립트는 `scripts/e2e.sh`(에이전트가 MVP-4 에서 채웁니다 — 이 PR 에서는 **단계 정의와 빈 진입점**까지) |
| 사람이 정하는 것 | **예산.** 2026-10-17 실측 전량 452,980~605,631 ms / 예산 600,000 ms 이고 `e2e` 는 `smoke`(약 110초)와 비슷하거나 더 깁니다. 선택지는 (a) 예산 상향 (b) `harness-scripts`(합계의 20%, 제품 아님)를 CI 전용으로 (c) `api-integration` 의 컨테이너 재사용(측정은 `2026-10-06-002` 에) |
| 에이전트가 넘기는 것 | 단계 정의 diff, 그 세 선택지와 각각의 대가, 그리고 **지금까지의 합계 추이**. 숫자를 고르지 않습니다(EI-2) |

### MVP-3 로컬 LLM 과 모델 볼륨 (A, 적재는 H-3)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `scripts/fetch-model.sh`(네트워크 있는 환경에서 1회, 볼륨에 적재). compose 의 `llm` 프로파일을 **기본 경로**로 쓰는 설정과, 볼륨이 비었을 때의 **명확한 실패**(받는 방법을 메시지에 적음, 조용한 fake 폴백 금지) |
| 판정 | `e2e`: 외부와 끊긴 네트워크에서 Run 하나가 로컬 모델로 `succeeded`(R-8). 볼륨을 비우면 **up 이 명확한 오류로 멈춤**(R-9). `api-unit`: 설정 분기(fake / openai_compatible)와 빈 볼륨 오류 메시지 |
| H-3 | **모델 1회 적재** — 사람이 네트워크 있는 환경에서 스크립트를 실행합니다. 에이전트는 그 전까지(스크립트·설정·실패 경로)를 만들고 **"미측정" 으로 보고**합니다 |
| 주의 | 모델을 다시 고르지 않습니다(Q6 닫힘, Qwen3.8 27B). 부팅 경로에 다운로드를 넣으면 그것이 결함입니다(DP-4) |

### MVP-2a 목록 화면 둘 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `apps/web/app/agents/page.tsx`·`runs/page.tsx` — SDK 목록 함수로 행을 그립니다. 빈 목록·오류 상태를 포함합니다 |
| 판정 | `web-unit`: SDK 응답 고정값으로 행이 렌더되고, 빈 목록·오류가 각각 다른 화면을 냅니다. **`NAV_ITEMS` 의 `href` 전부에 라우트가 있는지 보는 테스트**(R-6)를 이 단위에서 세우되, 아직 없는 둘(`/knowledge`·`/workflows`)은 2c 가 채우므로 **그 테스트가 2c 까지 빨간 것을 의도로 적습니다**(skip 하지 않습니다 — `xfail` 로 두고 2c 에서 제거) |
| 주의 | `apps/web` 은 `packages/sdk` 외의 `packages/*` 를 import 하지 않습니다(AR-1, `web-arch` 가 발화). 정적 프리렌더가 빌드 때 api 를 부르지 않게 `force-dynamic` 을 유지합니다(기존 홈 화면의 선례) |

### MVP-2b Run 상세 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `app/runs/[id]/page.tsx` — 상태·시각·실패 사유와 **이벤트 타임라인**(SSE), 그리고 **trace id**. 취소 버튼은 범위 밖(기존 API 는 있지만 화면 범위를 넓히지 않습니다) |
| 판정 | `web-unit`: 이벤트 목록이 `seq` 순서로 렌더되고 `run.finished` 가 마지막. 연결이 끊기면 그 사실이 화면에 나타남. `e2e`(MVP-4): 실제 Run 의 이벤트가 화면에 나타남 |
| 주의 | 이벤트 봉투는 **계약**입니다(DP-1) — 화면이 그 모양을 바꾸지 않습니다. 모델 응답 본문은 이벤트에 **없습니다**(spec 0002·0005 D-11) |

### MVP-2c `/knowledge`·`/workflows` 와 Agent 대화 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `app/knowledge/page.tsx`(세트 목록 + 적재 상태), `app/workflows/page.tsx`(정의 목록 + **Run 수준** 실행 목록, D-4), `app/agents/[id]/chat/page.tsx`(대화 — 입력 → `POST /agents/{id}/run` → 스트림) |
| 판정 | `web-unit`: 세 화면이 고정값으로 렌더. **R-6 의 `xfail` 을 제거**하고 통과시킵니다(사이드바에 404 가 없다). `e2e`: 네 경로가 실제 행을 보여줌(R-5) |
| 주의 | Workflow 화면에 **노드 실행을 요구하는 호출을 만들지 않습니다**(그 API 가 없습니다, R-7). "준비 중" 자리표시도 두지 않습니다(D-4) |

### MVP-4 오프라인 시나리오 e2e (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `scripts/e2e.sh` — 차단된 네트워크에서 compose up → Knowledge 적재 → Agent 생성(MCP 바인딩) → **Workflow 실행** → 성공. 화면 네 경로가 200 인 것도 같은 스크립트에서 확인(R-5 의 절반) |
| 판정 | `e2e` 단계가 통과하고 로그가 `.harness/logs/e2e.log` 에 남습니다(R-10). **외부 주소 호출이 실패하는 것을 스크립트 안에서 확인**합니다(C-5 — "끊었다" 를 주장하지 않고 증명) |
| 주의 | `smoke` 를 바꾸지 않습니다(D-10). `down -v` 는 **격리 프로젝트 이름**에서만(`-p aether-e2e`) |

### MVP-5 TTFSA (A 는 문서까지, 측정은 H-4)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `docs/quickstart.md` 한 장(clone → 모델 적재 → `aether up` → 첫 Run)과 `docs/measurements/ttfsa-TEMPLATE.md`(측정자·환경·단계별 시각·막힌 지점·총 시간) |
| 판정 | `links`(문서 링크)와 `web-typecheck`는 그대로. **측정 자체는 사람**이고, 기록 파일이 커밋되면 R-12 입니다 |
| H-4 | **처음 보는 사람 1명.** 에이전트는 그 사람이 될 수 없습니다 — Quickstart 와 양식까지 만들고 멈춥니다. 10분을 넘기면 **막힌 지점을 backlog 단위로 등록**하고 숫자를 조정하지 않습니다(EI-3) |

## 3. 사람 손

| 순간 | 언제 | 사람이 하는 일 |
| --- | --- | --- |
| **H-1** | MVP-1 **앞** | `.importlinter` 에 AR-14 신설 + AR-5 에 `aether_cli`. `harness-change` 라벨 |
| **H-2** | MVP-3 **앞** | `harness.config` 에 `e2e` 단계. **같은 PR 에서 예산을 정합니다** — 선택지 셋과 숫자는 에이전트가 올립니다 |
| **H-3** | MVP-3 중 | 네트워크 있는 환경에서 모델 1회 적재(`scripts/fetch-model.sh`) |
| **H-4** | MVP-5 | **처음 보는 사람 1명의 시간**. 에이전트가 대신할 수 없는 유일한 단위 |

보호 파일 변경은 **둘**입니다(H-1·H-2). 하네스 변경은 한 번에 하나이고 변경 사이에 평가를 실행합니다(CC-1·CC-5) — 그래서 두 PR 사이에 단위 하나(MVP-1)가 들어갑니다.

## 4. 판정 절차

`TESTCONTAINERS_RYUK_DISABLED=true ./harness/scripts/verify.sh` 하나가 판정입니다. **H-2 뒤에는 `e2e` 가 `HARNESS_DEFERRED_STEPS` 에 있으므로 로컬 기본 실행이 그 단계를 미룹니다** — 그 단계에 걸린 단위(MVP-3·MVP-4)는 **`--full` 을 최소 1회** 돌립니다.

**단위마다 보고에 적습니다**: `.harness/verify.json` 의 합계 ms, `api-integration`·(있으면) `e2e` 의 ms. 예산을 넘기면 선택 실패로 집계하고 **사람이 봅니다** — 에이전트가 임계를 올리지 않습니다(EI-2).

| 단위 | 추가 확인(verify 가 아직 못 보는 것) |
| --- | --- |
| MVP-0 | 목록 응답의 페이지 모양이 `GET /agents` 와 **글자까지 같은지** 눈으로 |
| MVP-1 | CLI 를 **설치된 상태로** 한 번(`uv run aether ...` 가 아니라 콘솔 스크립트) |
| MVP-3 | 모델 볼륨을 비운 상태의 오류 메시지를 **읽어 보기**(받는 방법이 적혀 있는지) |
| MVP-2a~2c | 브라우저로 네 경로를 **직접 열기** 1회 |
| MVP-4 | 외부 주소 호출이 실제로 실패하는 것을 로그에서 |
| MVP-5 | 해당 없음 — 측정 자체가 사람 |

**보고에 반드시**: `red 증거`, 판정 명령 exit 표, verify 합계 ms, 미측정, spec/plan 과의 불일치, `docs/` 에 옮길 표 초안.

## 5. 예산과 중단

| 항목 | 값 |
| --- | --- |
| 쪼개기 | MVP-2 는 **처음부터** 2a·2b·2c. 포트에 메서드를 더하는 변경(MVP-0)은 fake 가 몇 곳인지 **먼저 세십시오**(`2026-09-28-001`) |
| 위임 | **한 번에 하나**입니다. 2026-10-17 에 같은 작업 트리의 동시 편집으로 변경을 잃었습니다(`2026-10-17-001`) — 주 세션은 위임이 도는 동안 편집하지 않습니다 |
| Docker | `down -v` 는 격리 프로젝트 이름(`-p`)에서만. `e2e` 는 `aether-e2e`, `smoke` 는 `aether-smoke` |
| 중단 조건 | **MVP-3 에서 로컬 모델로 `succeeded` 가 되지 않으면 멈추고 보고**합니다. fake 로 통과시키는 우회를 만들지 마십시오 — 그것이 이 Phase 가 증명하려는 것입니다 |
| 시간 예산 | 합계 10분(판정 명령). 넘으면 선택 실패로 집계되고 사람이 판단합니다 |

## 6. Phase 완료

backlog 의 MVP 완료 판정 + spec 0006 의 R-1 ~ R-12 전부가 통과하고 일곱 단위가 병합되면 완료입니다.

| 요구 | 어느 단위가 판정하는가 |
| --- | --- |
| R-2 | **H-1**(사람) |
| R-4 | MVP-0 |
| R-1, R-3 | MVP-1 |
| R-11 | **H-2**(사람) |
| R-8, R-9 | MVP-3 (적재는 H-3) |
| R-5(절반), R-6 | MVP-2a ~ 2c |
| R-7 | MVP-2c |
| R-10, R-5(절반) | MVP-4 |
| R-12 | MVP-5 (측정은 H-4) |

그때 **M** 이 하는 일: intent 0006 의 상태를 `완료` 로, `intents/intent.md` 의 활성 intent 를 다음 건으로, backlog 의 MVP 상태 행, `docs/roadmap.md` 의 Phase 행. 그리고 **TTFSA 측정에서 나온 막힌 지점**을 backlog 의 단위로 등록합니다.

## 관련 문서

- [../specs/0006-mvp-integration.md](../specs/0006-mvp-integration.md) — 요구사항·결정
- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — 단위의 범위(MVP-0 행은 plan 승인과 함께 M 이 더합니다)
- [../docs/architecture.md](../docs/architecture.md) — **AR-1(개정 대상)**, AR-5, AR-14(신설)
- [../improvement-log/2026-10-06-002.yaml](../improvement-log/2026-10-06-002.yaml) — verify 예산. H-2 가 이것과 한 묶음입니다
- [../improvement-log/2026-10-17-001.yaml](../improvement-log/2026-10-17-001.yaml) — 같은 트리 동시 편집. 5절의 "위임은 한 번에 하나" 가 이 교훈입니다
- [../AGENTS.md](../AGENTS.md) — Loop, Trust, 반복 예산
