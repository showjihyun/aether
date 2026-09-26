# Plan 0003 — Phase 2: Enterprise MCP Gateway

| 키 | 값 |
| --- | --- |
| 번호 | 0003 |
| 근거 spec | [../specs/0003-phase-2-mcp-gateway.md](../specs/0003-phase-2-mcp-gateway.md) (승인됨 2026-09-25, D-1 ~ D-16. 개정 1 은 이 plan 의 리뷰에서) |
| 근거 intent | [../intents/0003-phase-2-mcp-gateway.md](../intents/0003-phase-2-mcp-gateway.md) (승인됨 2026-09-25) |
| 작업 단위 | [../intents/mvp-backlog.md](../intents/mvp-backlog.md) P2-1 ~ P2-6 (P2-2 → **2a·2b** 로 분할) |
| 작성일 | 2026-09-25 |
| 상태 | 승인됨 |
| 승인 | showjihyun, 2026-09-25 (리뷰 F-1 ~ F-7 반영본. spec 0003 개정 1 [실질] 도 이 승인으로 확정) |
| 개정 | 2 — 2026-09-26. P2-2b 의 범위에 MCP 클라이언트 어댑터의 호출 상한을 더했습니다 — 처음 구현이 주입된 시계의 델타로 **사후 판정**만 했고, 그것은 상한이 아닙니다(멈춘 호출을 끊지 못합니다). 주 세션이 그 단위 안에서 범위 확대를 승인했습니다 |
| 개정 | 1 — 2026-09-26. P2-1 실행이 찾은 사실로 H-1 의 범위를 줄였습니다: `.importlinter` 의 AR-6·AR-9 가 이미 SDK 누출과 다른 패키지의 `mcp` import 를 막고 있습니다. P2-1 의 "구조 테스트로 자체 판정" 전제는 틀렸습니다 |

spec 이 정한 요구사항(R-1 ~ R-12)·결정(D-1 ~ D-13)은 반복하지 않습니다. 이 문서는 일곱 단위를 어떤 순서로 하고, 단위마다 어느 파일을 누가 만들며, 무엇으로 판정하는지를 정합니다. 표기 — **A** 에이전트(`implementer`), **M** 주 세션(`docs/`·backlog·spec·plan), **H** 사람(보호 파일).

이 plan 이 풀어야 하는 문제는 넷입니다.

1. **Gateway 가 판정 없이 존재하는 커밋을 만들지 않습니다.** 권한 판정(P2-4)이 Gateway(P2-2b)보다 **먼저** 갑니다. 순서를 뒤집으면 "판정 없는 Gateway" 가 main 에 한동안 남고, 그 상태가 곧 AR-6 의 우회 경로입니다 — 나중에 끼워 넣는 것보다 처음부터 순서 안에 두는 것이 싸고 안전합니다. P2-4 는 🔒 이므로 사람 검토가 그 자리에 붙습니다.
2. **`.importlinter` 는 한 번만 바꿉니다.** `ignore_imports` 의 각 줄은 실제 import 와 매칭되어야 `unmatched_ignore_imports_alerting = error` 를 통과합니다(plan 0002 1절 문제 2 와 같은 함정). `mcp` SDK 를 import 하는 어댑터가 없는 동안에는 AR-6 계약을 좁혀도 매칭될 것이 없습니다. 그래서 H-1 은 **P2-2b 병합 뒤, P2-3 착수 전** 한 번입니다(부록 A).
3. **허용 목록에는 행을 넣는 경로가 함께 가야 합니다.** 기본값 deny 인데 정책 표에 행을 넣을 방법이 없으면 모든 도구 호출이 거부되고 R-7 이 원리적으로 불가능합니다(리뷰 F-1). 그래서 P2-4 범위에 CLI 서브커맨드(spec 개정 1 의 D-14)가 들어가고, `aether_data` 의 `control.tool_permissions` SELECT GRANT(D-15)가 P2-2a 에 들어갑니다.
4. **마이그레이션 0003 은 한 번에 담습니다.** `data.tool_call_audit` 과 `control.tool_permissions` 를 P2-2a 에서 함께 만듭니다 — 뒤 단위가 열을 기다리지 않게 하고, 역할 분리(P0-8)의 GRANT 를 한 곳에서 판정합니다.

## 1. 순서

의존 그래프(backlog 의 `의존` 열)와 spec 2.1 의 호출 방향에서 유도했습니다. **세션 하나에 단위 하나**입니다. 판정은 모델과 무관하게 4절의 명령입니다.

| Wave | 단위 | 왜 이 자리인가 | 사람 손 |
| --- | --- | --- | --- |
| 1 | **P2-1** MCP 클라이언트 · Discovery · 테스트 서버 | 뒤 전부의 선행. SDK 고정(D-1)과 `McpClient` 포트가 여기서 정해지고, 저장소 안 echo 서버가 R-1 의 판정 대상입니다. 보호 파일 없음 | — |
| 1 | **P2-2a** 마이그레이션 0003 · 감사 싱크 | P2-1 과 파일이 겹치지 않습니다(다른 패키지·다른 앱). `AuditSink` 포트와 PG 어댑터, GRANT 판정 | — |
| 2 | **P2-4** 🔒 권한 판정 | Gateway 보다 **먼저**(1절 문제 1). `packages/policy` 의 판정 함수 하나 + `control.tool_permissions` 읽기. 인터페이스·테스트 목록을 먼저 제안 | **사람 검토** |
| 2 | **P2-2b** Gateway 유스케이스 | P2-1(호출)·P2-2a(감사)·P2-4(판정)를 판정 → 호출 → 감사 순서로 묶는 단위. R-3·R-4 가 여기서 판정됩니다 | — |
| — | (경계) | `.importlinter` 한 번 — **`aether_mcp` → `aether_policy.adapters` 금지 계약 추가**. AR-6 좁히기는 범위가 줄었습니다(개정 1: 기존 AR-6·AR-9 가 이미 대부분을 막습니다) | **H-1** |
| 3 | **P2-3** runtime 이 Gateway 로만 | H-1 아래에서. `ToolGateway` outbound 포트, Executor 전환, 내부 도구 둘을 MCP Server 로 이전(D-5). R-2·R-6·R-10 | — |
| 4 | **P2-6** 바인딩 | `AgentDefinition.mcp_servers`(D-2), Run 시작 시 바인딩된 서버만 연결. R-9. sdk 생성 타입 갱신 | — |
| 5 | **P2-5** 초기 Integration · smoke | 전부가 있어야 e2e 가 성립합니다. Filesystem(smoke) · HTTP · PostgreSQL(우리 구현, D-7), 이미지 빌드 시점 주입(D-8), 실측 기록 | **H-2**(evaluation) |

P2-4 를 P2-2b 앞에 둔 것과 P2-2 를 2a·2b 로 쪼갠 것이 backlog 번호 순서와 다릅니다. 근거는 1절 문제 1·4 입니다. backlog 에 P2-2a·P2-2b 행을 추가하는 것은 **M** 이 이 plan 승인과 같은 커밋에서 합니다.

## 2. 단위별 계획

모든 단위는 **red(실패하는 테스트, 실행해 기록) → green → refactor(테스트 불변)** 순서이고, 보고의 `red 증거` 칸이 그것을 증명합니다 — 실패 원인이 기대한 원인인지도 적습니다. 테스트 docstring 은 `spec 0003 R-n`·`D-n`·`AR-n` 을 인용합니다. 단위마다 브랜치 하나(`p2-1-mcp-client`), PR 하나, 커밋 trailer `Unit: P2-1`. 유스케이스는 평탄 배치 `application/usecases/<이름>.py` + `test_<이름>.py` 1:1 입니다.

### P2-1 MCP 클라이언트와 Tool Discovery (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `packages/mcp/src/aether_mcp/domain/tools.py`(`Tool`, `ToolResult`, `McpServerRef`) · `application/ports/outbound/mcp_client.py`(`McpClient`) · `application/ports/inbound/discover_tools.py` · `application/usecases/discover_tools.py` · `adapters/outbound/mcp_client/stdio.py`·`http.py` · `tools/mcp-servers/echo/`(도구 `echo`·`fail`. **파이썬 + 같은 `mcp` SDK 의 서버 API** — 테스트에 새 언어 런타임을 들이지 않습니다) |
| 고치는 것 | `packages/mcp/pyproject.toml` 에 `mcp == 2.2.0`(D-1), 루트 `uv.lock` |
| 판정 | `api-unit`: echo 서버 stdio Discovery 로 도구 2개 + 스키마(R-1), `call` 성공·실패 경로. 소켓 차단 아래 통과 — stdio 는 서브프로세스이므로 loopback 허용으로 충분한지 **실측해 보고**합니다(아니면 그 테스트만 `integration`) |
| 주의 | SDK 타입이 `McpClient` 포트 밖으로 새지 않습니다. `domain`·`application` 은 `mcp` 를 import 하지 않습니다(AR-9) — **이것은 `.importlinter` 의 `ar9-core-is-framework-free` 가 이미 막습니다**(`aether_mcp.domain`·`application` 이 `source_modules` 에, `mcp` 가 `forbidden_modules` 에). 별도 구조 테스트를 만들지 않습니다(P2-1 실행이 확인, 개정 1) |

### P2-2a 마이그레이션 0003 과 감사 싱크 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `apps/api/migrations/versions/0003_*.py`(`data.tool_call_audit`, `control.tool_permissions`, GRANT — **`aether_data` 에 `control.tool_permissions` SELECT 포함**, spec D-15) · `packages/mcp/.../ports/outbound/audit_sink.py` · `adapters/outbound/audit_sink/postgres.py` · `domain/audit.py`(레코드 타입, spec 2.7 의 열) |
| 판정 | `api-integration`: 빈 DB(testcontainers)에서 up/down 왕복. `aether_control` 로 `data.tool_call_audit` 접근 시 permission denied, `aether_data` 로는 INSERT 가능. `api-unit`: 레코드 직렬화에 인자·결과 본문과 자격증명이 없음(R-11, D-12) |
| 고치는 것 | `packages/mcp/pyproject.toml` 에 `psycopg[binary]`(감사 싱크가 PG 어댑터입니다 — runtime 의 선례와 같은 의존), 루트 `uv.lock` |
| 판정 추가 | `apps/api/tests/test_plane_roles.py` 에 새 GRANT 의 범위를 고정하는 단언 — `aether_data` 는 `control.tool_permissions` 를 **SELECT 만** 하고 INSERT/UPDATE 는 거부(spec C-7) |
| 주의 | 인자·결과 **본문을 넣지 않습니다**. 크기와 종류만(D-12) |

### P2-4 🔒 권한 판정 지점 (A, 사람 검토)

| 항목 | 내용 |
| --- | --- |
| 먼저 제안 | 인터페이스(`PermissionJudge` inbound 포트)와 테스트 목록을 **보고로 먼저** 올립니다. 사람 확인 뒤 구현 |
| 만드는 것 | `packages/policy/src/aether_policy/domain/decision.py` · `application/ports/inbound/judge_tool_call.py` · `application/ports/outbound/permission_table.py` · `application/usecases/judge_tool_call.py` · `adapters/outbound/permission_table/postgres.py` · **그리고 `aether-api permissions allow|deny` CLI 서브커맨드**(spec D-14, `keys create` 와 같은 모양) |
| 판정 | `api-unit`: 표에 없는 (Version, Tool) 의 기본값이 **deny** 임을 단언 — 허용 목록 방식입니다. allow 행이 있을 때만 allow. CLI 로 넣은 allow 행이 판정에 반영되는 것도 1건. `api-arch`: `aether_policy` 가 `runtime`·`mcp`·`context` 를 import 하지 않음(R-5) |
| 주의 | 기본값이 allow 가 되면 이 층은 있으나 없으나 같습니다. 그 단언이 이 단위의 핵심 테스트입니다 |

### P2-2b Gateway 유스케이스 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `packages/mcp/.../ports/inbound/call_tool.py` · `application/usecases/call_tool.py`(판정 → 호출 → 감사, D-9) · `domain/errors.py`(`ToolCallDenied`, `ToolCallFailed`, `ToolNotFound`) · 연결 수명 관리(spec 2.5) · **그리고 `adapters/outbound/mcp_client/{stdio,http}.py` 의 호출 상한**(개정 2: spec 2.9 의 `AETHER_MCP_CALL_TIMEOUT_MS` 는 사후 판정이 아니라 강제여야 하고, 강제는 async 호출이 있는 어댑터에서만 가능합니다 — `asyncio.wait_for`) |
| 판정 | `api-unit`: deny 시 `McpClient.call` spy 0회 + 감사 1건(R-4). 성공·실패·거부 세 경우 각 감사 1건(R-3). 감사 실패가 호출 결과를 바꾸지 않음(D-10). 서버 1개 연결 실패 시 그 도구만 빠지고 나머지는 동작(spec 2.5). `api-integration`: **Gateway 를 직접** 3회 불러 감사 3행 — 이 단위에는 Gateway 를 지나는 Run 경로가 아직 없습니다(리뷰 F-3). Run 경유 판정은 P2-3 으로 이월 |
| 주의 | 진입점은 이 유스케이스 **하나**입니다. 테스트용 우회 함수도 만들지 않습니다 |

### H-1 (경계) `.importlinter` — 사람이 커밋

부록 A 의 후보를 scratchpad 로 넘깁니다. 에이전트는 후보를 적용한 트리에서 `lint-imports` 가 통과하는 것을 확인한 기록을 함께 올립니다. 사람이 `harness-change` 라벨로 PR 을 병합합니다.

### P2-3 Runtime 이 Gateway 로만 도구를 부름 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `packages/runtime/.../ports/outbound/tool_gateway.py` · `adapters/outbound/tool_gateway/mcp.py`(`aether_mcp` 의 inbound 포트 타입만 봄, AR-12) · `tools/mcp-servers/builtin/`(시계·계산기, D-5) |
| 지우는 것 | `packages/runtime/.../adapters/outbound/tools/clock_tool.py`·`calculator.py`·`registry.py` — 같은 도구를 두 경로로 부를 수 있는 상태를 남기지 않습니다 |
| 판정 | `api-unit`: Phase 1 의 도구 시나리오 테스트가 Gateway 포트 fake 로 그대로 통과(R-6). Executor 에 `aether_mcp` 외의 도구 호출 경로가 없음을 구조 테스트로. 지시 문장을 담은 fake 서버 결과가 `role: tool` + `trust: untrusted` 안에만 있음(R-10). `api-arch`: `tests/arch/test_real_importlinter_fires.py` 에 위반 주입 1건 추가(R-2) — 기존 AR-6 계약이 `aether_runtime`·`aether_api`·`aether_worker` 의 `mcp` import 를 이미 금지하므로, 이 단위는 그 계약이 **실제로 발화하는지**를 판정합니다(개정 1) |
| 이월 | P2-2b 에서 못 하는 Run 경유 판정 — 도구를 3회 부르는 Run 하나에서 감사 3행(R-3), deny 넣은 Run 이 `failed` + 사유 `tool_denied`(R-4). 리뷰 F-3 |
| 주의 | 도구 이름의 **생성 시 정적 검증을 없앱니다**(spec 개정 1 의 D-16, spec 0002 D-3 [실질] 개정). 없는 도구는 Run 시점 `ToolNotFound` 로 감사에 남습니다 — 그 테스트를 이 단위에 넣습니다. `BUILTIN_TOOL_NAMES` 를 쓰던 검증 코드와 그 테스트를 지웁니다 |

### P2-6 Agent 에 MCP Server 바인딩 (A, 표는 M)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `AgentDefinition.mcp_servers`(D-2, 기본 `[]`) · worker 의 Run 시작 시 연결·종료 시 정리 · `AETHER_MCP_SERVERS` 해석(spec 2.9) |
| 고치는 것 | `packages/sdk/openapi.json`(추가 변경) + 생성 타입, `.env.example` |
| 판정 | `api-integration`: `PUT /agents/{id}` 로 `mcp_servers` 만 바꿔 `current_version == 2`, Version 1 의 `definition` 불변, Discovery 가 바인딩된 서버의 도구만(R-9). `web-typecheck` 의 sdk 드리프트 검사 통과. `openapi.json` 의 diff 가 **경로 추가 0개**임을 보고에 명시 |
| M | `docs/api.md` 의 `AgentDefinition` 표에 `mcp_servers` 행 — implementer 는 표 초안만 보고에 올립니다 |

### P2-5 초기 Integration 과 smoke (A, H-2)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `tools/mcp-servers/postgres-readonly/`(D-7, 조회 한 가지) · `infra/docker/` 의 MCP Server 이미지(참조 서버는 빌드 시점 주입, D-8) · compose 서비스(Filesystem 은 기본, 나머지는 통합 테스트용) · `scripts/smoke.sh` 에 도구 호출 있는 시나리오 |
| 판정 | `smoke`: 오프라인 compose 에서 Filesystem 도구로 파일을 읽어 Run `succeeded`(R-7). `api-integration`: HTTP·PostgreSQL 서버 Discovery + 호출 1회(R-8). `.harness/verify.json` 합계 ≤ 600,000 ms, `smoke` ≤ 240,000 ms(R-12) |
| 기록 | `smoke`·`api-integration` 실측과 감사 표 증가(행 수·바이트)를 `improvement-log/` 1건으로(D-3, spec 2.10). 예산을 넘으면 단계 분리를 **제안만** 하고 사람이 결정 |
| M | `docs/` 에 한 줄 — 참조 서버(npm)의 버전은 Dependabot 밖이라 사람이 주기적으로 본다(spec C-5). implementer 는 문장 초안만 보고에 |
| H-2 | REP-6 이 실행 가능해지므로 `evaluation/README.md`·`evaluation/tasks/representative.md` 의 "실행 가능" 칸을 사람이 갱신합니다. 에이전트는 문구 후보만 올립니다 |

## 3. 사람 손

접촉은 셋 + 단위마다 PR 병합입니다.

| 순간 | 언제 | 사람이 하는 일 | 에이전트가 넘기는 것 |
| --- | --- | --- | --- |
| **P2-4 검토** | P2-4 착수 전과 PR 리뷰 | 🔒 권한 판정의 인터페이스와 테스트 목록 확인. 기본값 deny 확인. **그리고 `aether_data` 의 `control.tool_permissions` SELECT 확대**(spec D-15) 가 SELECT 에만 머무는지 | 인터페이스 초안, 테스트 목록, GRANT 한 줄(보고) |
| **H-1** | **P2-2b 병합 뒤, P2-3 착수 전** | `.importlinter` 한 번(부록 A). `harness-change` PR | 후보 파일과 `lint-imports` 통과 기록 |
| **H-2** | P2-5 | `evaluation/` 의 REP-6 "실행 가능" 칸 | 문구 후보. 값·판정 제안 없음 |

`harness.config` 는 바뀌지 않습니다 — D-4 가 단계 수를 늘리지 않기로 했습니다. `.github/workflows/harness.yml` 도 바뀌지 않습니다(새 job 없음). 보호 파일 접촉이 Phase 1(넷)보다 줄었습니다.

## 4. 판정 절차

`TESTCONTAINERS_RYUK_DISABLED=true ./harness/scripts/verify.sh` 하나가 판정입니다(18단계, 변동 없음). 완료 보고에는 `.harness/verify.json` 경로와 실패 단계의 `log` 경로를 붙입니다.

**단위별 추가 확인**(verify 가 아직 못 보는 것 — 보고에 "손으로 실행" 으로, 실행하지 않았으면 "미측정"):

| 단위 | 추가 확인 |
| --- | --- |
| P2-1 | stdio 서브프로세스가 소켓 차단 아래에서 뜨는지. 안 되면 그 테스트를 `integration` 으로 옮긴 근거 |
| P2-2a | `aether_control` 로 `data.tool_call_audit` INSERT 시도 → permission denied 출력 |
| P2-4 | 표에 행이 없을 때 deny 인 것을 손으로도 1회. CLI 로 allow 를 넣고 다시 1회. `aether_data` 로 `control.tool_permissions` INSERT 시도 → permission denied |
| P2-2b | 감사 어댑터를 강제로 실패시킨 채 호출 1회 — 결과가 바뀌지 않고 로그만 남는지 |
| P2-3 | `git grep` 으로 Executor 에 남은 직접 도구 호출 0건 |
| P2-6 | compose 로 바인딩 바꾼 Agent 를 Run — 새 Version 번호 확인 |
| P2-5 | 네트워크를 끊은 상태에서 `docker compose up` → Run `succeeded` (D-8 이 지켜졌는지) |

**보고에 반드시**: `red 증거`, 판정 명령 exit 표, 미측정, spec/plan 과의 불일치, `docs/` 에 옮길 표 초안.

## 5. 예산과 중단

[../AGENTS.md](../AGENTS.md) Loop 와 `harness/rules/loop-budget.rule.md` 를 그대로 씁니다. 다른 것만 적습니다.

| 항목 | 값 |
| --- | --- |
| 쪼개기 | P2-2 는 **처음부터** 2a·2b 로 쪼갰습니다. 예산 안에 안 끝나면 더 쪼갭니다 — 예산을 늘리지 않습니다 |
| 브랜치·PR | 단위 하나 = `p2-<번호>-<slug>` 브랜치 하나 = PR 하나. 사람이 병합 |
| 보호 파일 | 증거(`evaluation/runs/**`)는 주 세션, 게이트는 사람(AGENTS.md Loop). 한 PR 에 게이트 파일 하나 |
| 새 `.sh`·서버 | `git update-index --chmod=+x`. 새 MCP Server 디렉터리는 `tools/mcp-servers/` 아래에만 |
| Docker | P2-5 에서 컨테이너가 늘어납니다. 격리 프로젝트 이름을 반드시 붙입니다 — `docker compose down -v` 를 기본 프로젝트에서 실행하면 개발 볼륨이 지워집니다(`scripts/guard-docker-volumes.sh` 가 막지만 규칙으로도 적습니다) |
| 외부 네트워크 | 이미지 **빌드**에는 필요합니다(npm 참조 서버). 테스트·실행에는 필요하지 않습니다 — 그것이 R-7·R-8 의 판정입니다 |
| 시간 예산 | verify 합계 10분. P2-5 에서 넘으면 사람 결정 |

## 5.1 이 plan 의 리뷰 (2026-09-25, 주 세션)

승인 전에 초안을 적으로 읽었습니다. 막아야 할 것 둘과 고칠 것 다섯이 나왔습니다.

| # | 발견 | 심각도 | 처리 |
| --- | --- | --- | --- |
| F-1 | 기본값 deny(허용 목록)인데 **정책 표에 행을 넣는 경로가 이번 Phase 에 없었습니다.** 그러면 smoke 의 Filesystem 호출이 반드시 거부되어 **R-7 이 원리적으로 불가능**합니다 | 막아야 함 | spec 개정 1 의 D-14 — `aether-api permissions allow|deny` CLI. P2-4 범위에 넣고 smoke 가 씁니다 |
| F-2 | 판정은 worker(`aether_data`) 안에서 일어나는데 그 역할은 `control` 에서 `agent_versions`·`runs` 만 SELECT 합니다 — **`control.tool_permissions` 를 읽을 GRANT 가 없었습니다** | 막아야 함 | spec D-15 — 마이그레이션 0003 에 SELECT GRANT. 권한 확대이므로 P2-4 의 🔒 검토와 `test_plane_roles.py` 가 범위를 고정 |
| F-3 | R-3·R-4 의 `api-integration` 판정을 P2-2b·P2-4 에 놓았는데, "Run 하나에서" 는 Run 경로가 Gateway 를 지난 **P2-3 이후**에만 성립합니다. 그대로 두면 구현자가 P2-2b 에서 Run 경로를 만들며 범위를 넘습니다 | 고칠 것 | P2-2b 는 Gateway 직접 호출로 판정, Run 경유는 P2-3 으로 이월 |
| F-4 | `packages/mcp` 에 감사 싱크의 PG 의존(`psycopg[binary]`)이 빠졌습니다 | 고칠 것 | P2-2a 의 "고치는 것" 에 추가 |
| F-5 | 도구 이름 검증(`BUILTIN_TOOL_NAMES`)이 Discovery 로 옮겨가며 **자리를 잃었습니다** — api 는 생성 시점에 어떤 서버가 무엇을 내놓는지 모릅니다. 미결로 두면 구현자가 추측합니다 | 고칠 것 | spec D-16 — 생성 시 정적 검증을 없애고 Run 시점 `ToolNotFound`. spec 0002 D-3 을 [실질] 개정 |
| F-6 | spec C-5 가 요구한 "npm 참조 서버는 Dependabot 밖" 을 `docs/` 에 적는 일이 어느 단위에도 없었습니다 | 고칠 것 | P2-5 의 M 항목으로 |
| F-7 | P2-1 의 echo 서버 런타임이 미지정이었습니다 | 고칠 것 | 파이썬 + 같은 SDK 의 서버 API. 테스트에 새 언어 런타임을 들이지 않습니다 |

F-1 과 F-2 는 **구현 중에 발견되면 P2-4·P2-5 를 되돌려야 했던 것**입니다. 둘 다 "층을 하나 넣었는데 그 층을 쓸 수 있게 만드는 부분이 빠졌다" 는 같은 모양입니다 — 허용 목록에는 행을 넣는 경로가, 새 표에는 읽을 권한이 함께 가야 합니다.

리뷰가 잡지 **못한** 것도 적어 둡니다. P2-1 의 stdio 서브프로세스가 소켓 차단 아래에서 뜨는지는 여전히 미확인이고(실측을 P2-1 의 보고 항목으로 남겼습니다), 참조 서버 이미지의 크기·빌드 시간도 P2-5 에서 처음 측정됩니다.

## 6. Phase 완료

backlog 의 Phase 2 완료 판정 + spec 0003 의 R-1 ~ R-12 전부가 판정 통과하고 일곱 단위가 병합되면 완료입니다. 그때 **M** 이 하는 일: intent 0003 의 상태를 `완료` 로, [../intents/intent.md](../intents/intent.md) 의 활성 intent 를 다음 건으로, backlog 의 Phase 2 상태 행, [../docs/roadmap.md](../docs/roadmap.md) 의 Phase 행. 그리고 REP-6 이 실행 가능해진 것을 근거로 평가 1회를 돌려 `evaluation/runs/` 에 기록합니다.

## 부록 — 보호 파일 제안

### A. `.importlinter` — 바꿀 부분 (H-1, 한 번)

현재 `ar6-mcp-client-only-in-mcp` 는 `mcp` SDK 를 `aether_mcp` **전체**에 허용합니다. 좁힙니다.

| 무엇 | 왜 |
| --- | --- |
| ~~AR-6 계약의 허용 범위를 `aether_mcp.adapters` 로~~ | **취소(개정 1).** `ar9-core-is-framework-free` 가 `aether_mcp.domain`·`application` 에서 `mcp` 를 이미 금지합니다 — P2-1 에서 실제 위반을 주입해 확인했습니다. 남는 빈틈은 `aether_mcp.adapters.inbound` 가 클라이언트 SDK 를 보는 경우뿐이고, 그것은 경계 위반이 아닙니다 |
| ~~`aether_runtime`·`aether_api`·`aether_worker` → `mcp` 금지를 명시~~ | **이미 있습니다(개정 1).** 기존 AR-6 계약의 `source_modules` 에 그 셋과 나머지 패키지가 전부 들어 있습니다. R-2 는 계약 추가가 아니라 **발화 확인**(P2-3 의 위반 주입 테스트)으로 판정합니다 |
| 새 계약: `aether_mcp` → `aether_policy.adapters` 금지 | Gateway 는 policy 의 **inbound 포트 타입만** 봅니다(AR-12) |
| `ignore_imports` 는 실제 import 가 생긴 뒤에만 | `unmatched_ignore_imports_alerting = error` 때문입니다. 그래서 H-1 은 P2-2b 병합 뒤입니다 |

정확한 줄은 P2-2b 병합 시점의 트리에서 만들어 scratchpad 후보로 올립니다 — 지금 적으면 그때의 모듈 이름과 어긋납니다.

### B. `evaluation/` — 바꿀 부분 (H-2, P2-5)

REP-6 의 "실행 가능" 칸이 `packages/mcp` 에 코드가 있어야 성립합니다. P2-5 병합 뒤 문구 후보를 올리고 사람이 커밋합니다. 합격 기준은 건드리지 않습니다 — 기준 변경은 별도 후보와 승격 판정을 거칩니다.

## 관련 문서

- [../specs/0003-phase-2-mcp-gateway.md](../specs/0003-phase-2-mcp-gateway.md) — 요구사항·결정
- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — 단위의 범위
- [../docs/architecture.md](../docs/architecture.md) — AR-3·AR-4·AR-6·AR-9·AR-12
- [../AGENTS.md](../AGENTS.md) — Loop, Trust
