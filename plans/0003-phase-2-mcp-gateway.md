# Plan 0003 — Phase 2: Enterprise MCP Gateway

| 키 | 값 |
| --- | --- |
| 번호 | 0003 |
| 근거 spec | [../specs/0003-phase-2-mcp-gateway.md](../specs/0003-phase-2-mcp-gateway.md) (승인됨 2026-09-25, D-1 ~ D-13) |
| 근거 intent | [../intents/0003-phase-2-mcp-gateway.md](../intents/0003-phase-2-mcp-gateway.md) (승인됨 2026-09-25) |
| 작업 단위 | [../intents/mvp-backlog.md](../intents/mvp-backlog.md) P2-1 ~ P2-6 (P2-2 → **2a·2b** 로 분할) |
| 작성일 | 2026-09-25 |
| 상태 | 승인 대기 |
| 승인 | (사람 이름과 날짜. 비어 있으면 구현을 시작하지 않습니다) |

spec 이 정한 요구사항(R-1 ~ R-12)·결정(D-1 ~ D-13)은 반복하지 않습니다. 이 문서는 일곱 단위를 어떤 순서로 하고, 단위마다 어느 파일을 누가 만들며, 무엇으로 판정하는지를 정합니다. 표기 — **A** 에이전트(`implementer`), **M** 주 세션(`docs/`·backlog·spec·plan), **H** 사람(보호 파일).

이 plan 이 풀어야 하는 문제는 셋입니다.

1. **Gateway 가 판정 없이 존재하는 커밋을 만들지 않습니다.** 권한 판정(P2-4)이 Gateway(P2-2b)보다 **먼저** 갑니다. 순서를 뒤집으면 "판정 없는 Gateway" 가 main 에 한동안 남고, 그 상태가 곧 AR-6 의 우회 경로입니다 — 나중에 끼워 넣는 것보다 처음부터 순서 안에 두는 것이 싸고 안전합니다. P2-4 는 🔒 이므로 사람 검토가 그 자리에 붙습니다.
2. **`.importlinter` 는 한 번만 바꿉니다.** `ignore_imports` 의 각 줄은 실제 import 와 매칭되어야 `unmatched_ignore_imports_alerting = error` 를 통과합니다(plan 0002 1절 문제 2 와 같은 함정). `mcp` SDK 를 import 하는 어댑터가 없는 동안에는 AR-6 계약을 좁혀도 매칭될 것이 없습니다. 그래서 H-1 은 **P2-2b 병합 뒤, P2-3 착수 전** 한 번입니다(부록 A).
3. **마이그레이션 0003 은 한 번에 담습니다.** `data.tool_call_audit` 과 `control.tool_permissions` 를 P2-2a 에서 함께 만듭니다 — 뒤 단위가 열을 기다리지 않게 하고, 역할 분리(P0-8)의 GRANT 를 한 곳에서 판정합니다.

## 1. 순서

의존 그래프(backlog 의 `의존` 열)와 spec 2.1 의 호출 방향에서 유도했습니다. **세션 하나에 단위 하나**입니다. 판정은 모델과 무관하게 4절의 명령입니다.

| Wave | 단위 | 왜 이 자리인가 | 사람 손 |
| --- | --- | --- | --- |
| 1 | **P2-1** MCP 클라이언트 · Discovery · 테스트 서버 | 뒤 전부의 선행. SDK 고정(D-1)과 `McpClient` 포트가 여기서 정해지고, 저장소 안 echo 서버가 R-1 의 판정 대상입니다. 보호 파일 없음 | — |
| 1 | **P2-2a** 마이그레이션 0003 · 감사 싱크 | P2-1 과 파일이 겹치지 않습니다(다른 패키지·다른 앱). `AuditSink` 포트와 PG 어댑터, GRANT 판정 | — |
| 2 | **P2-4** 🔒 권한 판정 | Gateway 보다 **먼저**(1절 문제 1). `packages/policy` 의 판정 함수 하나 + `control.tool_permissions` 읽기. 인터페이스·테스트 목록을 먼저 제안 | **사람 검토** |
| 2 | **P2-2b** Gateway 유스케이스 | P2-1(호출)·P2-2a(감사)·P2-4(판정)를 판정 → 호출 → 감사 순서로 묶는 단위. R-3·R-4 가 여기서 판정됩니다 | — |
| — | (경계) | `.importlinter` 한 번 — AR-6 을 `aether_mcp.adapters` 로 좁히고, `aether_mcp` → `aether_policy.adapters` 금지 계약 추가 | **H-1** |
| 3 | **P2-3** runtime 이 Gateway 로만 | H-1 아래에서. `ToolGateway` outbound 포트, Executor 전환, 내부 도구 둘을 MCP Server 로 이전(D-5). R-2·R-6·R-10 | — |
| 4 | **P2-6** 바인딩 | `AgentDefinition.mcp_servers`(D-2), Run 시작 시 바인딩된 서버만 연결. R-9. sdk 생성 타입 갱신 | — |
| 5 | **P2-5** 초기 Integration · smoke | 전부가 있어야 e2e 가 성립합니다. Filesystem(smoke) · HTTP · PostgreSQL(우리 구현, D-7), 이미지 빌드 시점 주입(D-8), 실측 기록 | **H-2**(evaluation) |

P2-4 를 P2-2b 앞에 둔 것과 P2-2 를 2a·2b 로 쪼갠 것이 backlog 번호 순서와 다릅니다. 근거는 1절 문제 1·3 입니다. backlog 에 P2-2a·P2-2b 행을 추가하는 것은 **M** 이 이 plan 승인과 같은 커밋에서 합니다.

## 2. 단위별 계획

모든 단위는 **red(실패하는 테스트, 실행해 기록) → green → refactor(테스트 불변)** 순서이고, 보고의 `red 증거` 칸이 그것을 증명합니다 — 실패 원인이 기대한 원인인지도 적습니다. 테스트 docstring 은 `spec 0003 R-n`·`D-n`·`AR-n` 을 인용합니다. 단위마다 브랜치 하나(`p2-1-mcp-client`), PR 하나, 커밋 trailer `Unit: P2-1`. 유스케이스는 평탄 배치 `application/usecases/<이름>.py` + `test_<이름>.py` 1:1 입니다.

### P2-1 MCP 클라이언트와 Tool Discovery (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `packages/mcp/src/aether_mcp/domain/tools.py`(`Tool`, `ToolResult`, `McpServerRef`) · `application/ports/outbound/mcp_client.py`(`McpClient`) · `application/ports/inbound/discover_tools.py` · `application/usecases/discover_tools.py` · `adapters/outbound/mcp_client/stdio.py`·`http.py` · `tools/mcp-servers/echo/`(도구 `echo`·`fail`) |
| 고치는 것 | `packages/mcp/pyproject.toml` 에 `mcp == 2.2.0`(D-1), 루트 `uv.lock` |
| 판정 | `api-unit`: echo 서버 stdio Discovery 로 도구 2개 + 스키마(R-1), `call` 성공·실패 경로. 소켓 차단 아래 통과 — stdio 는 서브프로세스이므로 loopback 허용으로 충분한지 **실측해 보고**합니다(아니면 그 테스트만 `integration`) |
| 주의 | SDK 타입이 `McpClient` 포트 밖으로 새지 않습니다. `domain`·`application` 은 `mcp` 를 import 하지 않습니다(AR-9) — H-1 전이라 계약이 아직 막지 않으므로 이 단위는 **구조 테스트로 자체 판정**합니다 |

### P2-2a 마이그레이션 0003 과 감사 싱크 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `apps/api/migrations/versions/0003_*.py`(`data.tool_call_audit`, `control.tool_permissions`, GRANT) · `packages/mcp/.../ports/outbound/audit_sink.py` · `adapters/outbound/audit_sink/postgres.py` · `domain/audit.py`(레코드 타입, spec 2.7 의 열) |
| 판정 | `api-integration`: 빈 DB(testcontainers)에서 up/down 왕복. `aether_control` 로 `data.tool_call_audit` 접근 시 permission denied, `aether_data` 로는 INSERT 가능. `api-unit`: 레코드 직렬화에 인자·결과 본문과 자격증명이 없음(R-11, D-12) |
| 주의 | 인자·결과 **본문을 넣지 않습니다**. 크기와 종류만(D-12) |

### P2-4 🔒 권한 판정 지점 (A, 사람 검토)

| 항목 | 내용 |
| --- | --- |
| 먼저 제안 | 인터페이스(`PermissionJudge` inbound 포트)와 테스트 목록을 **보고로 먼저** 올립니다. 사람 확인 뒤 구현 |
| 만드는 것 | `packages/policy/src/aether_policy/domain/decision.py` · `application/ports/inbound/judge_tool_call.py` · `application/ports/outbound/permission_table.py` · `application/usecases/judge_tool_call.py` · `adapters/outbound/permission_table/postgres.py` |
| 판정 | `api-unit`: 표에 없는 (Version, Tool) 의 기본값이 **deny** 임을 단언 — 허용 목록 방식입니다. allow 행이 있을 때만 allow. `api-arch`: `aether_policy` 가 `runtime`·`mcp`·`context` 를 import 하지 않음(R-5) |
| 주의 | 기본값이 allow 가 되면 이 층은 있으나 없으나 같습니다. 그 단언이 이 단위의 핵심 테스트입니다 |

### P2-2b Gateway 유스케이스 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `packages/mcp/.../ports/inbound/call_tool.py` · `application/usecases/call_tool.py`(판정 → 호출 → 감사, D-9) · `domain/errors.py`(`ToolCallDenied`, `ToolCallFailed`, `ToolNotFound`) · 연결 수명 관리(spec 2.5) |
| 판정 | `api-unit`: deny 시 `McpClient.call` spy 0회 + 감사 1건(R-4). 성공·실패·거부 세 경우 각 감사 1건(R-3). 감사 실패가 호출 결과를 바꾸지 않음(D-10). 서버 1개 연결 실패 시 그 도구만 빠지고 나머지는 동작(spec 2.5). `api-integration`: 호출 3회 = 감사 3행 |
| 주의 | 진입점은 이 유스케이스 **하나**입니다. 테스트용 우회 함수도 만들지 않습니다 |

### H-1 (경계) `.importlinter` — 사람이 커밋

부록 A 의 후보를 scratchpad 로 넘깁니다. 에이전트는 후보를 적용한 트리에서 `lint-imports` 가 통과하는 것을 확인한 기록을 함께 올립니다. 사람이 `harness-change` 라벨로 PR 을 병합합니다.

### P2-3 Runtime 이 Gateway 로만 도구를 부름 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `packages/runtime/.../ports/outbound/tool_gateway.py` · `adapters/outbound/tool_gateway/mcp.py`(`aether_mcp` 의 inbound 포트 타입만 봄, AR-12) · `tools/mcp-servers/builtin/`(시계·계산기, D-5) |
| 지우는 것 | `packages/runtime/.../adapters/outbound/tools/clock_tool.py`·`calculator.py`·`registry.py` — 같은 도구를 두 경로로 부를 수 있는 상태를 남기지 않습니다 |
| 판정 | `api-unit`: Phase 1 의 도구 시나리오 테스트가 Gateway 포트 fake 로 그대로 통과(R-6). Executor 에 `aether_mcp` 외의 도구 호출 경로가 없음을 구조 테스트로. 지시 문장을 담은 fake 서버 결과가 `role: tool` + `trust: untrusted` 안에만 있음(R-10). `api-arch`: H-1 의 좁힌 AR-6 아래에서 통과, `tests/arch/test_real_importlinter_fires.py` 에 위반 주입 1건 추가(R-2) |
| 주의 | 도구 이름 검증(`BUILTIN_TOOL_NAMES`, spec 0002 D-3)이 이제 Discovery 결과에서 옵니다. `AgentDefinition` 의 기존 도구 이름이 깨지지 않는지 판정에 넣습니다 |

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
| H-2 | REP-6 이 실행 가능해지므로 `evaluation/README.md`·`evaluation/tasks/representative.md` 의 "실행 가능" 칸을 사람이 갱신합니다. 에이전트는 문구 후보만 올립니다 |

## 3. 사람 손

접촉은 셋 + 단위마다 PR 병합입니다.

| 순간 | 언제 | 사람이 하는 일 | 에이전트가 넘기는 것 |
| --- | --- | --- | --- |
| **P2-4 검토** | P2-4 착수 전과 PR 리뷰 | 🔒 권한 판정의 인터페이스와 테스트 목록 확인. 기본값 deny 확인 | 인터페이스 초안과 테스트 목록(보고) |
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
| P2-4 | 표에 행이 없을 때 deny 인 것을 손으로도 1회 |
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

## 6. Phase 완료

backlog 의 Phase 2 완료 판정 + spec 0003 의 R-1 ~ R-12 전부가 판정 통과하고 일곱 단위가 병합되면 완료입니다. 그때 **M** 이 하는 일: intent 0003 의 상태를 `완료` 로, [../intents/intent.md](../intents/intent.md) 의 활성 intent 를 다음 건으로, backlog 의 Phase 2 상태 행, [../docs/roadmap.md](../docs/roadmap.md) 의 Phase 행. 그리고 REP-6 이 실행 가능해진 것을 근거로 평가 1회를 돌려 `evaluation/runs/` 에 기록합니다.

## 부록 — 보호 파일 제안

### A. `.importlinter` — 바꿀 부분 (H-1, 한 번)

현재 `ar6-mcp-client-only-in-mcp` 는 `mcp` SDK 를 `aether_mcp` **전체**에 허용합니다. 좁힙니다.

| 무엇 | 왜 |
| --- | --- |
| AR-6 계약의 허용 범위를 `aether_mcp.adapters` 로 | 지금은 `aether_mcp.domain`·`application` 이 SDK 를 import 해도 통과합니다. AR-9 가 문장으로만 막고 있습니다 |
| `aether_runtime`·`aether_api`·`aether_worker` → `mcp` 금지를 명시 | R-2 의 "우회 경로를 만들면 실패한다" 가 이 줄로 발화합니다 |
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
