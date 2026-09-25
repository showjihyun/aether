# Spec 0003 — Phase 2: Enterprise MCP Gateway

| 키 | 값 |
| --- | --- |
| 번호 | 0003 |
| 작성일 | 2026-09-25 |
| 선행 intent | [../intents/0003-phase-2-mcp-gateway.md](../intents/0003-phase-2-mcp-gateway.md) (승인됨 2026-09-25) |
| 후속 plan | [../plans/0003-phase-2-mcp-gateway.md](../plans/0003-phase-2-mcp-gateway.md) (승인 대기) |
| 상태 | 승인됨 |
| 승인 | showjihyun, 2026-09-25 |
| 대상 단위 | [../intents/mvp-backlog.md](../intents/mvp-backlog.md) 의 P2-1 ~ P2-6 (P2-2 는 plan 에서 2a·2b 로 분할) |

이 문서는 intent 0003 의 열린 질문 6건을 결정(D-1 ~ D-13)으로 고정하고, 여섯 단위의 완료 판정을 **검증 가능한 명제**(R-1 ~ R-12)로 옮깁니다. 단위의 범위는 backlog 가 소유합니다 — 여기 복제하지 않습니다.

Phase 1 의 결정(spec 0002 D-1 ~ D-19)은 그대로 유효합니다. 이 spec 이 그중 무엇을 개정하면 해당 항목에 `[실질] 개정` 을 명시합니다.

## 1. 요구사항

| # | 요구사항 | 근거 | 어떻게 판정하는가 |
| --- | --- | --- | --- |
| R-1 | `packages/mcp` 가 MCP Server 에 붙어 `Tool` 목록과 입력 스키마를 발견합니다 | Outcome 1 (P2-1) | `api-unit`: 저장소 안 테스트 서버(2.3)를 stdio 로 띄워 도구 2개 이상을 스키마와 함께 발견. `pytest-socket` 소켓 차단 아래 통과(loopback 만 허용, spec 0002 D-18) |
| R-2 | 도구 호출은 **Gateway 함수 하나**만 지납니다. 우회 경로를 만들면 아키텍처 단계가 실패합니다 | Outcome 2 (P2-2, P2-3), AR-6 | `api-arch`: `.importlinter` 의 AR-6 계약에 `aether_runtime`·`aether_api`·`aether_worker` → `mcp`(SDK) 금지가 들어가고, `tests/arch/test_real_importlinter_fires.py` 에 위반 주입 케이스 1건 추가 — 실제 `.importlinter` 로 exit ≠ 0 (spec 0002 R-7 의 방식 재사용) |
| R-3 | 호출마다 감사 기록이 남습니다 — Agent Version·Run·Tool·시각·결과 크기·판정 | Outcome 3 (P2-2) | `api-integration`: P2-2b 에서는 Gateway 를 직접 3회 불러, **P2-3 이후**에는 도구를 3회 부르는 Run 하나에서 `data.tool_call_audit` 행이 정확히 3건, 각 행의 `run_id`·`agent_version_id`·`tool_name` 이 호출과 일치. deny 된 호출도 1건으로 남음(R-4) |
| R-4 | deny 된 도구 호출은 **실행되지 않고** 감사에 남습니다 | Outcome 4 (P2-4) | `api-unit`: deny 를 돌려주는 fake 판정으로 Gateway 를 부르면 MCP 클라이언트의 `call_tool` 이 호출되지 않고(spy 0회) `ToolCallDenied` 가 돌아오며 감사 1건. `api-integration`(**P2-3 이후**, Run 경로가 Gateway 를 지난 뒤): 정책 표에 deny 를 넣은 Run 이 `failed` 로 끝나고 사유가 `tool_denied` |
| R-5 | `packages/policy` 는 `runtime`·`mcp`·`context` 를 import 하지 않습니다 | Outcome 4, AR-4 | `api-arch`: 기존 `ar4-policy-judges-only` 계약이 처음으로 막을 코드를 갖습니다. `tests/arch/test_real_importlinter_fires.py` 에 `aether_policy/_bad.py`(`import aether_mcp.domain`) 주입 케이스 |
| R-6 | Phase 1 의 도구 시나리오 테스트가 **Gateway 경유로 그대로** 통과합니다 | Outcome 5 (P2-3) | `api-unit`: `packages/runtime/tests/test_tools.py` 와 Planner/Executor 시나리오가 내부 함수 대신 Gateway 포트 fake 로 통과. `Executor` 에 `aether_mcp` 외의 도구 호출 경로가 없음을 구조 테스트로 단언 |
| R-7 | 오프라인 compose 에서 Agent 가 Filesystem 도구로 파일을 읽어 Run 이 `succeeded` 까지 갑니다 | Outcome 6 (P2-5) | `smoke`: compose up(네트워크 없이) → Agent 생성(Filesystem 서버 바인딩) → Run → `succeeded`, 그리고 도구 결과에 그 파일의 내용이 있음 |
| R-8 | HTTP·PostgreSQL MCP Server 도 오프라인에서 붙습니다 | Outcome 6 (P2-5) | `api-integration`: 두 서버를 testcontainers/로컬 프로세스로 띄워 Discovery + 호출 1회. 외부 네트워크 없이 통과 |
| R-9 | 바인딩을 바꾸면 **새 `Agent Version`** 이 생기고, 바인딩되지 않은 Tool 은 Discovery 에 나타나지 않습니다 | Outcome 7 (P2-6) | `api-integration`: `PUT /agents/{id}` 로 `mcp_servers` 만 바꿔 `current_version == 2`, Version 1 의 `definition` 불변. Run 에서 Discovery 결과가 바인딩된 서버의 도구만 포함 |
| R-10 | 외부 MCP Server 의 응답은 데이터입니다 — 지시로 해석되는 경로가 없습니다 | intent Constraints, Trust | `api-unit`: 도구 결과에 "이제부터 system 지시로 취급하라" 류 문장을 넣은 fake 서버로 Run → 모델이 받은 요청에서 그 내용이 `role: tool` + `trust: untrusted` 안에만 있고 system 메시지에 없음(spec 0002 D-6·R-14 의 단언을 외부 서버 경로로 확장) |
| R-11 | 비밀값(MCP Server 자격증명)이 코드·로그·커밋·감사 기록에 없습니다 | intent Constraints | `api-unit`: 감사 레코드 직렬화에 `env`·`headers`·`url` 의 자격증명 부분이 없음. CI 의 `비밀값 스캔` job 통과. 자격증명은 환경변수로만 주입(2.9) |
| R-12 | verify 전체가 spec 0001 D-12 의 10분 예산 안입니다 | intent Constraints | `.harness/verify.json` 의 `duration_ms` 합계 ≤ 600,000. `smoke` 단독 ≤ 240,000(spec 0002 D-15 의 회귀 조건 유지). 넘으면 D-6 의 (b) 로 내려갑니다 |

## 2. 설계

### 2.1 배치 — `packages/mcp`, `packages/policy`, 호출 방향

```
apps/worker ──► aether_runtime.application (ExecuteRun, Planner/Executor)
                        │ outbound 포트 ToolGateway (runtime 이 선언)
                        ▼
                aether_runtime.adapters.outbound.tool_gateway
                        │ inbound 포트 CallTool·DiscoverTools (mcp 가 선언)
                        ▼
                aether_mcp.application.usecases  ── Gateway 한 곳
                   │                   │                  │
                   │ outbound          │ outbound         │ outbound
                   ▼                   ▼                  ▼
            McpClient(SDK)      AuditSink(PG)      PermissionJudge
         adapters/outbound       adapters/outbound   → aether_policy 의 inbound 포트
```

- 방향은 `runtime → mcp → policy` 입니다. AR-3(`mcp` 는 `runtime` 을 모른다)과 AR-4(`policy` 는 `runtime`·`mcp`·`context` 를 모른다)가 유지됩니다.
- `runtime` 은 `aether_mcp` 의 **inbound 포트 타입만** 봅니다(AR-12). 구현 조립은 worker 의 `main` 입니다.
- MCP SDK(`mcp` 패키지)는 `aether_mcp/adapters/outbound/` 안에만 있습니다(AR-6, AR-9).
- Gateway 는 유스케이스 **하나**(`CallToolUseCase`)입니다. 판정 → 호출 → 감사가 그 안의 고정된 순서이고, 우회할 다른 진입점을 만들지 않습니다.

### 2.2 MCP 클라이언트 (P2-1, 열린 질문 1)

공식 SDK `mcp` 를 씁니다. 2026-09-25 확인: 최신 릴리스 **2.2.0**(2025-12-19), `requires_python >= 3.10`, 전이 의존에 `starlette`·`uvicorn`·`httpx2`·`jsonschema`·`pydantic` 이 있습니다.

| 항목 | 내용 |
| --- | --- |
| 전송 | stdio 와 streamable HTTP 둘. SDK 가 제공하는 것을 그대로 씁니다 — `stdio_client(StdioServerParameters(...))`, `mcp.client.streamable_http.streamable_http_client(url, http_client=...)`, 세션은 `Client` |
| 우리 포트 | `McpClient`(outbound): `discover(server: McpServerRef) -> tuple[Tool, ...]`, `call(server, tool_name, arguments) -> ToolResult`. SDK 타입이 이 포트 밖으로 새지 않습니다 |
| 버전 고정 | `pyproject.toml` 에 `mcp == 2.2.0`, `uv.lock` 에 잠급니다. Air-Gapped 설치는 lock + 휠 캐시로 합니다(새 네트워크 접근을 만들지 않습니다) |
| 전이 의존 주의 | `starlette`·`uvicorn` 이 따라옵니다. AR-9 가 `domain`·`application` 에서 이들을 금지하므로 SDK import 는 `adapters/outbound` 안에만 둡니다 — R-2 가 이것을 계약으로 검사합니다 |

프로토콜을 직접 구현하지 않는 이유는 하나입니다. 우리가 얻을 것은 도구 발견과 호출 두 가지인데, 직접 구현하면 프로토콜 개정을 우리가 따라가야 합니다. 그 비용은 제품 가치와 무관합니다.

### 2.3 저장소 안의 MCP Server 들 (P2-1, P2-5, 열린 질문 없음 + D-7)

| 서버 | 출처 | 왜 |
| --- | --- | --- |
| 테스트 서버(`tools/mcp-servers/echo/`) | 우리가 씀 | R-1 의 판정 대상. 도구 2개(`echo`, `fail`) — 실패 경로도 결정적으로 재현해야 합니다 |
| 시계·계산기(`tools/mcp-servers/builtin/`) | 우리가 씀 | Phase 1 의 프로세스 내부 도구 둘을 그대로 옮깁니다(D-5). 기존 시나리오 테스트가 판정에 계속 쓰입니다 |
| Filesystem | 참조 구현 `@modelcontextprotocol/server-filesystem` | 유지되는 참조 서버입니다(2026-09-25 확인) |
| HTTP(Fetch) | 참조 구현 `@modelcontextprotocol/server-fetch` | 같음 |
| PostgreSQL | **우리가 씀**(`tools/mcp-servers/postgres-readonly/`) | 참조 구현 `@modelcontextprotocol/server-postgres` 는 **archive** 되었습니다(2026-09-25 확인). D-7 |

참조 서버는 npm 패키지이므로 **이미지 빌드 시점에 안으로 넣습니다**. 실행 시점에 `npx` 로 내려받지 않습니다 — Air-Gapped 에서 동작하지 않고, 실행마다 외부에서 코드를 받는 것은 공급망 관점에서도 받을 수 없습니다.

### 2.4 Gateway — 판정·호출·감사의 고정 순서 (P2-2, P2-4, 열린 질문 6)

`CallToolUseCase.__call__(call: ToolCall) -> ToolResult` 한 곳입니다.

1. **판정**: `PermissionJudge(subject=agent_version_id, resource=tool_name)` → allow / deny. **호출마다** 묻습니다(D-6).
2. deny 면 MCP 클라이언트를 부르지 않고 감사 1건을 남기고 `ToolCallDenied` 를 올립니다.
3. allow 면 `McpClient.call(...)`. 예외는 `ToolCallFailed` 로 감싸되 원인 메시지는 감사에만 남깁니다.
4. **감사**: 성공·실패·거부 **세 경우 모두** 1건. 감사 기록 실패는 호출 결과를 바꾸지 않지만 로그와 span 에 남습니다 — 기록이 없으면 그 호출은 사후에 존재하지 않은 것이 되므로, 연속 실패는 Phase 9 의 판단 대상으로 남깁니다(C-3).

Run 시작 시 한 번 묻고 캐시하지 않는 이유: 캐시하면 Run 중의 정책 변경이 반영되지 않습니다. 긴 Run 일수록 그 창이 커지고, 그것이 감사·권한 층을 두는 목적과 충돌합니다. 비용(호출마다 1 판정)은 같은 프로세스 안의 표 조회이므로 측정 대상으로만 둡니다(C-4).

### 2.5 연결 수명 (P2-2, P2-6)

- Run 시작 시 `Agent Version` 에 바인딩된 서버만 연결합니다. 바인딩이 비어 있으면 도구 없이 실행합니다.
- Run 이 종결(성공·실패·취소·타임아웃)하면 연결을 닫습니다. lease 를 잃은 worker 도 닫습니다(spec 0002 D-10).
- 한 서버가 연결 실패면 그 서버의 도구만 Discovery 에서 빠지고 Run 은 계속합니다. 모델이 없는 도구를 부르면 `ToolNotFound` 이고, 그 시도도 감사에 남습니다.
- 재연결은 호출 1회 안에서 1번만 시도합니다. 무한 재시도를 넣지 않습니다(spec 0002 D-10 의 재시도 정책과 같은 이유).

### 2.6 바인딩 — `AgentDefinition` 의 필드로 (P2-6, 열린 질문 2 의 절반)

새 HTTP 경로를 만들지 않습니다. `AgentDefinition`(spec 0002 2.3, D-3)에 필드를 하나 더합니다.

```
mcp_servers: list[McpServerBinding] = []   # 기본 빈 목록
McpServerBinding: {"name": str, "transport": "stdio" | "http", "ref": str}
```

- 바인딩 변경은 `definition` 변경이므로 **기존 `PUT /agents/{id}` 가 그대로 새 Version 을 만듭니다.** Phase 1 의 불변 규칙(Version 1 의 `definition` 은 바뀌지 않음)이 그대로 판정합니다(R-9).
- HTTP 계약의 **경로 수는 9개 그대로**입니다(spec 0002 D-9). `openapi.json` 의 변경은 `AgentDefinition` 스키마에 기본값 있는 필드 하나가 더해지는 **추가 변경**뿐입니다 — 기존 클라이언트는 깨지지 않습니다.
- `ref` 는 배포가 소유합니다 — stdio 면 compose 가 아는 서버 이름, http 면 내부 URL 키입니다. **자격증명이나 절대 URL 을 definition 에 넣지 않습니다**(R-11). 실제 값은 환경변수로 풉니다(2.9).

새 경로(`POST /agents/{id}/mcp-servers`)를 만드는 대안은 기각합니다 — 같은 것을 두 곳에서 바꿀 수 있게 되고, 그중 하나만 Version 을 만들면 불변 규칙이 깨집니다.

### 2.7 데이터 모델 변경 (마이그레이션 0003, 열린 질문 2)

| 대상 | 스키마 | 왜 |
| --- | --- | --- |
| 바인딩 | `control.agent_versions.definition` 안 (새 테이블 없음) | 바인딩은 **선언**입니다. 선언은 `control` 이고, Version 불변성을 공짜로 얻습니다 |
| 감사 | `data.tool_call_audit` (신설) | 감사는 **실행 부산물**입니다. 쓰는 주체가 worker(`aether_data`)이므로 역할 분리(P0-8)가 유지됩니다 — `aether_control` 은 여전히 `data` 에 접근하지 못합니다 |

`data.tool_call_audit` 의 열: `id`, `run_id`, `agent_version_id`, `server_name`, `tool_name`, `decision`(`allow`/`deny`), `outcome`(`ok`/`error`/`denied`), `result_bytes`, `error_kind`(nullable), `started_at`, `duration_ms`. 인자와 결과 **본문은 넣지 않습니다** — 크기와 종류만 남깁니다(R-11, 그리고 DLP 는 Phase 10).

감사표는 **append-only** 입니다(개정 3) — `aether_data` 에 `INSERT`·`SELECT` 만 주고 `UPDATE`·`DELETE` 는 주지 않습니다. 기록을 쓰는 주체가 자기 기록을 지울 수 있으면 사후 추적이 성립하지 않습니다. `control.agent_versions` 의 불변 트리거(P0-8)와 같은 취급입니다.

정책 표는 `control.tool_permissions`(`agent_version_id`, `tool_name`, `decision`)입니다 — 선언이므로 `control` 입니다. `packages/policy` 는 이 표를 자기 outbound 포트로만 읽습니다(AR-4).

### 2.8 감사 조회 (열린 질문 3)

이번 Phase 에는 **기록만** 합니다. 조회 API·대시보드는 Phase 9 입니다(intent Non-goals). 그래서 "남았는가" 를 확인하는 수단은 R-3 의 테스트와 `smoke` 뿐입니다 — 이것이 이 결정의 비용이고, 감수합니다(C-2).

보존 기간도 정하지 않습니다. 정하지 않는다는 것은 무한 보존이라는 뜻이므로, 표가 커지는 속도를 P2-5 의 `smoke` 에서 한 번 실측해 기록합니다(행 수와 바이트). 그 숫자가 Phase 9 의 입력입니다.

### 2.9 설정 (추가되는 환경변수)

| 변수 | 기본 | 누가 읽는가 |
| --- | --- | --- |
| `AETHER_MCP_SERVERS` | (비어 있음) | worker. `name=transport:target` 목록. `definition` 의 `ref` 를 실제 명령·URL 로 푸는 표입니다 |
| `AETHER_MCP_CALL_TIMEOUT_MS` | `30000` | worker. 도구 호출 1회의 상한. Run 타임아웃(spec 0002 2.8)보다 작아야 합니다 |
| `AETHER_MCP_MAX_RESULT_BYTES` | `262144` | worker. 넘으면 잘라내고 감사에 원래 크기를 남깁니다 — 모델 입력이 무한정 커지는 것을 막습니다 |

자격증명은 `AETHER_MCP_SERVERS` 의 target 안에 환경변수 참조로만 들어갑니다. 값 자체를 로그·감사·이벤트에 넣지 않습니다(R-11).

### 2.10 검증 단계 (열린 질문 4)

`harness.config` 의 단계 **수는 늘리지 않습니다.**

- `smoke` 에는 **Filesystem 서버 하나만** 올립니다(R-7). compose 서비스 1개 추가입니다.
- HTTP·PostgreSQL 서버는 `api-integration` 에서만 띄웁니다(R-8) — 프로세스·컨테이너 셋을 `smoke` 에 다 넣으면 spec 0002 D-15 의 `smoke ≤ 4분` 회귀 조건이 위험합니다.
- P2-5 병합 시 `smoke` 와 `api-integration` 의 실측을 `improvement-log/` 에 1건 기록합니다. 예산을 넘으면 그때 단계 분리를 제안합니다(사람 결정, EI-2).

### 2.11 아키텍처 규칙의 변경 (보호 파일 `.importlinter`, 사람이 커밋)

| 계약 | 변경 |
| --- | --- |
| `ar6-mcp-client-only-in-mcp` | `mcp` SDK 를 `aether_mcp.adapters` 밖에서 금지하는 것으로 좁힙니다 — 지금은 `aether_mcp` 전체가 허용이어서 `domain`·`application` 이 SDK 를 봐도 통과합니다 |
| `ar4-policy-judges-only` | 변경 없음. 처음으로 막을 코드가 생깁니다 |
| 새 계약 | `aether_policy` 를 `aether_mcp.application` 이 **inbound 포트로만** 보게 — `aether_mcp` → `aether_policy.adapters` 금지 |

`.importlinter` 는 보호 파일입니다. 변경은 P2-2 병합 **뒤 한 번**, 사람이 커밋합니다(spec 0002 D-13 과 같은 절차, [../harness/rules/harness-change-control.rule.md](../harness/rules/harness-change-control.rule.md)).

### 2.12 `packages/sdk`

`AgentDefinition` 스키마에 `mcp_servers` 가 더해지므로 생성 타입이 갱신됩니다(`scripts/check-sdk-drift.sh` 가 강제). 새 호출 함수는 없습니다 — 경로가 늘지 않기 때문입니다(2.6).

### 2.13 신뢰 경계 (R-10)

외부 서버가 돌려준 내용은 spec 0002 D-6 의 경로를 그대로 탑니다 — `role: tool` + `tool_call_id` + `trust: untrusted`. 이번 Phase 가 더하는 것은 **그 내용의 출처가 처음으로 우리 프로세스 밖**이라는 사실입니다. 그래서 R-10 의 단언을 외부 서버(fake) 경로로 확장하고, 결과 크기 상한(2.9)을 둡니다.

### 2.14 정책 표에 행을 넣는 경로 (개정 1, D-14)

기본값이 deny(허용 목록)이므로 **행을 넣는 경로가 없으면 모든 도구 호출이 거부됩니다** — R-7(Filesystem 도구로 파일을 읽어 `succeeded`)이 원리적으로 불가능해집니다. 리뷰 F-1 이 찾은 구멍입니다.

`aether-api permissions allow --agent-version <uuid> --tool <name>` 과 `... deny ...` 를 CLI 어댑터에 더합니다(`keys create` 와 같은 모양 — inbound 포트 타입만 보고, 조립은 `main.cli`). HTTP 경로는 늘리지 않습니다(D-2 와 같은 이유). `smoke` 는 이 명령으로 Filesystem 도구를 allow 한 뒤 Run 을 돌립니다.

### 2.15 도구 이름 검증의 자리 (개정 1, D-16, spec 0002 D-3 [실질] 개정)

spec 0002 D-3 은 `AgentDefinition` 의 도구 이름을 `aether_runtime.domain.tools.BUILTIN_TOOL_NAMES` 로 검증했습니다. P2-3 뒤에는 도구가 Discovery 에서 오고, api 는 Agent 생성 시점에 어떤 MCP Server 가 붙을지 알 수 없습니다(바인딩은 같은 `definition` 안에 있지만 그 서버가 실제로 무엇을 내놓는지는 연결해야 압니다).

그래서 **생성 시 정적 검증을 없앱니다.** 없는 도구 이름은 Run 시점에 `ToolNotFound` 로 실패하고 감사에 남습니다 — 거부·실패·성공 세 경로가 모두 기록되는 설계(D-9)가 이것을 덮습니다. 대안(생성 시 서버에 연결해 검증)은 기각합니다: Agent 생성이 외부 프로세스 기동에 의존하게 되고, 그 시점의 Discovery 결과가 Run 시점과 다를 수 있어 검증이 보증이 되지 못합니다.

## 3. 우려 지점

| # | 우려 | 지금의 답 |
| --- | --- | --- |
| C-1 | MCP SDK 의 전이 의존(`starlette`·`uvicorn`)이 worker 에 들어옵니다 | 서버를 띄우지 않으므로 런타임 비용은 import 뿐입니다. AR-9·R-2 가 계층으로 격리합니다. 이미지 크기 증가는 P2-5 에서 실측합니다 |
| C-2 | 감사 조회가 없어 "기록이 남는가" 를 사람이 눈으로 볼 수 없습니다 | 열린 질문 3 의 결정입니다(2.8). `smoke` 에서 행 수를 한 번 출력해 기록으로 남깁니다 |
| C-3 | 감사 기록 실패가 호출을 막지 않습니다 — 감사 없는 호출이 가능합니다 | 이번 Phase 의 선택입니다. 막으면 감사 DB 장애가 제품 장애가 됩니다. 연속 실패 임계와 차단 여부는 Phase 9 |
| C-4 | 호출마다 권한 판정이 성능에 닿습니다 | 같은 프로세스 안 표 조회입니다. `smoke --bench` 에 도구 호출 있는 Run 을 1종 더해 P95 를 기록만 합니다 — 기준값은 사람이 정합니다(EI-2) |
| C-5 | 참조 서버(npm)를 이미지에 넣으면 그 버전을 우리가 고정해야 합니다 | `package-lock` 을 이미지 빌드에 포함하고 버전을 compose 에 적습니다. 갱신은 Dependabot 밖이라 사람이 주기적으로 봅니다 — 그 사실을 `docs/` 에 적습니다 |
| C-6 | PostgreSQL 서버를 우리가 쓰면 유지 대상이 하나 늘어납니다 | 참조 구현이 archive 되었으므로 선택지가 좁습니다(D-7). read-only 조회 한 가지로 범위를 묶고, 커뮤니티 구현은 신뢰 경계 때문에 쓰지 않습니다 |
| C-7 | `aether_data` 가 `control` 에서 읽을 수 있는 표가 셋으로 늘어납니다(개정 1, D-15) | 권한 확대이므로 P2-4 의 🔒 검토에 넣고 `test_plane_roles.py` 가 범위를 고정합니다. 쓰기는 여전히 `aether_control` 만 |

## 4. 결정 요청

| # | 결정 | 근거 | 어디 |
| --- | --- | --- | --- |
| D-1 | MCP 클라이언트는 공식 SDK `mcp`, **2.2.0 고정**. SDK import 는 `aether_mcp/adapters/outbound` 안에만 | intent OQ 1 | 2.2, R-2 |
| D-2 | 바인딩은 `control.agent_versions.definition` 안(새 테이블 없음), 감사는 `data.tool_call_audit`(신설). 정책 표는 `control.tool_permissions` | intent OQ 2 | 2.6, 2.7 |
| D-3 | 감사는 이번 Phase 에 **기록만**. 조회 API·보존 정책은 Phase 9. 표 증가 속도를 `smoke` 에서 1회 실측해 기록 | intent OQ 3 | 2.8, C-2 |
| D-4 | `smoke` 에는 **Filesystem 하나**. HTTP·PostgreSQL 은 `api-integration`. 단계 수는 늘리지 않음 | intent OQ 4 | 2.10, R-12 |
| D-5 | P1-4 의 내부 도구 둘(시계·계산기)은 **저장소 안 MCP Server 로 이전**. 기존 시나리오 테스트가 Gateway 경유로 그대로 판정 | intent OQ 5 | 2.3, R-6 |
| D-6 | 권한 판정은 **호출마다**. Run 단위 캐시 없음 | intent OQ 6 (🔒) | 2.4, C-4 |
| D-7 | PostgreSQL MCP Server 는 **저장소 안의 read-only 구현**. 참조 구현이 archive 되었고(2026-09-25 확인) 커뮤니티 구현은 신뢰 경계 때문에 쓰지 않음. **backlog P2-5 의 "PostgreSQL MCP Server" 문구를 이 결정으로 갱신** | 외부 사실 확인 | 2.3, C-6 |
| D-8 | 참조 서버(npm)는 **이미지 빌드 시점에 넣습니다**. 실행 시 `npx` 로 내려받지 않습니다 | DP-4, 공급망 | 2.3, C-5 |
| D-9 | Gateway 는 유스케이스 하나(`CallToolUseCase`)이고 순서는 판정 → 호출 → 감사. 세 결과(성공·실패·거부) 모두 감사 1건 | — | 2.4, R-3, R-4 |
| D-10 | 감사 기록 실패는 호출 결과를 바꾸지 않습니다. 임계·차단은 Phase 9 | — | 2.4, C-3 |
| D-11 | 연결은 Run 수명에 묶입니다. 서버 1개 실패는 그 도구만 제거하고 Run 은 계속. 재연결은 호출당 1회 | — | 2.5 |
| D-12 | 감사에 인자·결과 **본문을 넣지 않습니다** — 크기와 종류만. 결과는 `AETHER_MCP_MAX_RESULT_BYTES` 로 자릅니다 | R-11, DLP 는 Phase 10 | 2.7, 2.9 |
| D-13 | `.importlinter` 변경은 P2-2b 병합 뒤 **한 번**, 사람이 커밋. 내용은 **`aether_mcp` → `aether_policy.adapters` 금지 계약 추가 하나**입니다 — AR-6 좁히기는 취소(개정 2: 기존 AR-6 이 다른 패키지 전부의 `mcp` import 를, AR-9 가 `aether_mcp.domain`·`application` 의 SDK import 를 이미 금지합니다) | CC, EI-2, 개정 2 | 2.11 |
| D-14 | 정책 표에 행을 넣는 경로는 **CLI 서브커맨드**(`aether-api permissions allow --agent-version --tool`)입니다. HTTP 경로는 늘리지 않습니다. 관리 API·UI 는 Phase 9 | 개정 1 (리뷰 F-1) | 2.14 |
| D-15 | 마이그레이션 0003 이 `aether_data` 에 `control.tool_permissions` **SELECT** 를 부여합니다. 그 확대는 `test_plane_roles.py` 의 판정에 들어가고 P2-4 의 🔒 검토 대상입니다 | 개정 1 (리뷰 F-2) | 2.7 |
| D-16 | 도구 이름의 **생성 시 정적 검증을 없앱니다** — 도구는 Discovery 에서 오고 api 는 어떤 서버가 붙을지 모릅니다. 없는 도구는 Run 시점에 `ToolNotFound` 로 감사에 남습니다. spec 0002 D-3 의 `BUILTIN_TOOL_NAMES` 검증 부분을 **[실질] 개정** | 개정 1 (리뷰 F-5) | 2.15 |

## 5. 검증 매핑

| 요구사항 | 단위 | 판정 |
| --- | --- | --- |
| R-1 | P2-1 | `api-unit`: 테스트 서버 stdio Discovery(도구 ≥ 2, 스키마 포함), 소켓 차단 아래 |
| R-2 | P2-2, P2-3 | `api-arch` + `tests/arch/test_real_importlinter_fires.py` 에 AR-6 위반 주입 |
| R-3 | P2-2 | `api-integration`: 호출 3회 = 감사 3행, 필드 일치 |
| R-4 | P2-4 (🔒) | `api-unit`: deny 시 `call_tool` spy 0회 + 감사 1건. `api-integration`: Run `failed`, 사유 `tool_denied` |
| R-5 | P2-4 | `api-arch` + `aether_policy/_bad.py` 주입 |
| R-6 | P2-3 | `api-unit`: Phase 1 시나리오 테스트가 Gateway fake 로 통과. Executor 구조 테스트 |
| R-7 | P2-5 | `smoke`: 오프라인 compose 에서 Filesystem 도구로 파일 읽고 `succeeded` |
| R-8 | P2-5 | `api-integration`: HTTP·PostgreSQL 서버 Discovery + 호출 1회 |
| R-9 | P2-6 | `api-integration`: `PUT` 으로 `mcp_servers` 변경 → Version 2, Version 1 불변. Discovery 가 바인딩된 서버만 |
| R-10 | P2-3, P2-5 | `api-unit`: 지시 문장을 넣은 fake 서버 → `role: tool` + `trust: untrusted` 안에만 |
| R-11 | P2-2, P2-5 | `api-unit`: 감사 직렬화에 자격증명 없음. CI 비밀값 스캔 |
| R-12 | P2-5 | `.harness/verify.json`: 합계 ≤ 600,000 ms, `smoke` ≤ 240,000 ms |

## 6. 이 spec 이 답하지 않는 것

- MCP Firewall·DLP 의 설계(Phase 10). 이번에는 Gateway 안의 호출 지점 하나가 그 자리입니다.
- Policy Engine 의 규칙 언어·평가 순서(Phase 9). 이번 판정은 표 조회 한 번입니다.
- 감사 조회·보존·집계(Phase 9, D-3).
- 도구 결과를 Context 로 압축·선별하는 것(Phase 3).
- 외부 네트워크가 필요한 Integration(GitHub·Slack) — Public Beta 전.

## 개정 이력

| 개정 | 내용 |
| --- | --- |
| 초안 | 2026-09-25. intent 0003 의 열린 질문 6건을 D-1 ~ D-6 으로 고정하고, 외부 사실 확인에서 나온 D-7·D-8 을 더했습니다 |
| 개정 3 | 2026-09-26. **P2-2a 리뷰**에서 감사표를 append-only 로 조였습니다 — `GRANT ALL PRIVILEGES` 였던 것을 `INSERT, SELECT` 로. 조이기 전 테스트가 `DID NOT RAISE InsufficientPrivilege` 로 실패해 권한이 넓었다는 것이 실측으로 확인되었습니다. `control.tool_permissions` 의 PK 는 `(agent_version_id, tool_name)` 복합키이고, 이 가정이 P2-4 의 CLI upsert 설계와 맞는지는 그 단위의 🔒 검토에서 확인합니다 |
| 개정 2 | 2026-09-26. **P2-1 실행이 찾은 사실**로 D-13 의 범위를 줄였습니다 — `.importlinter` 의 `ar6-mcp-client-only-in-mcp` 는 `aether_api`·`aether_worker`·`aether_runtime` 을 포함한 여덟 패키지에서 `mcp` 를 이미 금지하고, `ar9-core-is-framework-free` 는 `aether_mcp.domain`·`application` 에서 `mcp` 를 이미 금지합니다(위반 주입으로 확인). 그래서 R-2 는 계약 **추가**가 아니라 **발화 확인**으로 판정하고, H-1 은 policy 계약 하나만 더합니다 |
| 개정 1 | 2026-09-25. **plan 0003 리뷰(F-1 ~ F-7)가 찾은 구멍 셋**을 D-14 ~ D-16 으로 메웠습니다 — 정책 표 쓰기 경로가 없어 기본 deny 아래 R-7 이 불가능했던 것(F-1), `aether_data` 에 `control.tool_permissions` SELECT 가 없던 것(F-2), 도구 이름 검증이 Discovery 로 바뀌며 자리를 잃은 것(F-5, spec 0002 D-3 **[실질] 개정**). R-3·R-4 의 integration 판정 시점을 P2-3 이후로 정정했습니다(F-3) |
