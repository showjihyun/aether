# Phase 2 — Enterprise MCP Gateway (완료 2026-10-03)

단위 일곱(P2-1 ~ P2-6)과 사람 손 둘(H-1, H-2). intent [0003](../../intents/0003-phase-2-mcp-gateway.md) · spec [0003](../../specs/0003-phase-2-mcp-gateway.md) · plan [0003](../../plans/0003-phase-2-mcp-gateway.md).

그림: [diagrams/phase-2.html](diagrams/phase-2.html)

## 무엇이 생겼는가

| 단위 | 생긴 것 | PR |
| --- | --- | --- |
| P2-1 | `packages/mcp` — MCP Server 에 붙는 클라이언트(stdio, streamable HTTP)와 `Tool Discovery`. 저장소 안의 테스트용 MCP Server | #91 |
| P2-2a | 마이그레이션 0003 — `data.tool_call_audit`(**append-only**: `GRANT INSERT, SELECT` 만) 과 `control.tool_permissions`. `AuditSink` 포트와 PostgreSQL 어댑터 | #92 |
| P2-2b | Gateway 함수 하나 — 모든 도구 호출의 유일한 통로. 연결 수명 관리, 호출마다 감사, Firewall 자리(hook point) | #94 (반려 1회 뒤 재작업) |
| P2-3 | Executor 의 도구 호출이 전부 Gateway 경유. 프로세스 내부 도구 제거 | #96 |
| P2-4 | 🔒 `packages/policy` 의 판정 함수 하나 — (Agent Version, server, tool) → allow/deny, **기본 deny**. 행을 넣는 `aether-api permissions` CLI | #93 |
| P2-5 | Filesystem·HTTP·PostgreSQL MCP Server 를 compose 에. 참조 구현은 **이미지 빌드 시점**에 넣고(런타임 `npx` 없음), PostgreSQL 은 저장소 안의 read-only 구현 | #98 |
| P2-6 | `Agent Version` 의 `mcp_servers` 바인딩. 붙이고 떼면 새 Version. Run 시작 시 그 목록만 연결 | #97 |

## 왜 그렇게 했는가

- **판정 → 호출 → 감사 순서**를 코드에 고정했습니다. deny 된 호출은 **실행되지 않고** 감사에만 남습니다(R-4) — 순서가 뒤바뀌면 "거부된 호출이 이미 실행된" 상태가 됩니다.
- **기본값은 deny** 입니다(D-14). 그래서 행을 넣는 경로(CLI)가 같은 단위에 들어가야 했습니다 — 넣는 길이 없으면 모든 호출이 거부되고 그것은 기능이 아닙니다.
- **감사는 append-only** 입니다 — `GRANT` 에서 UPDATE·DELETE 를 주지 않았습니다. 지울 수 있는 감사는 감사가 아닙니다.
- **권한의 키를 `(agent_version_id, server_name, tool_name)`** 으로 넓혔습니다 — 서로 다른 서버가 같은 도구 이름을 가질 수 있습니다.
- **참조 서버를 이미지 빌드 시점에** 넣었습니다(D-7·D-8). 런타임 `npx` 는 인터넷을 요구하고 그것은 DP-4(Offline-capable)를 깹니다.

## 하네스 근거

| 줄 | 내용 |
| --- | --- |
| **요구** | spec 0003 R-1 ~ R-12. 핵심은 R-2(통로 하나 — 우회하면 아키텍처 단계 실패) · R-3(호출마다 감사) · R-4(deny 는 실행되지 않음) · R-5(policy 는 runtime·mcp·context 를 모름) · R-6(Phase 1 의 도구 시나리오가 Gateway 경유로 그대로 통과) · R-9(바인딩 변경은 새 Version) · R-10(외부 응답은 데이터) · R-11(비밀값 부재) |
| **결정** | D-2(바인딩을 `AgentDefinition` 에) · D-7·D-8(참조 서버를 빌드 시점에) · D-14(기본 deny 와 CLI) · D-16(도구 이름 검증을 Run 시점으로) |
| **단계** | `architecture`(AR-6 이 이 Phase 에서 처음으로 검사할 코드를 가짐) · `api-unit` · `api-integration` · `smoke` |
| **증거** | PR #91 ~ #98. P2-2b 는 **반려 1회**(red → green 순서 역전) 뒤 재작업했습니다 — 그 반려가 이 Phase 의 중요한 증거입니다 |
| **후보** | 2026-09-26-001, 2026-09-28-001. 보호 파일 블록이 반복돼 2026-09-23-001(증거와 게이트의 분리)을 이 Phase 에서 적용했습니다 |

## 정한 것과 다른 점

- H-1 의 범위가 **줄었습니다**(spec 개정 2). "`.importlinter` 가 SDK 누출을 막지 않는다" 는 전제가 틀렸습니다 — `ar9` 계약이 이미 덮고 있었고 실행자가 그것을 증명했습니다. 중복 테스트를 지웠습니다.
- 권한 키를 `(tool)` 에서 `(server, tool)` 로 넓히면서 마이그레이션 0003 을 **직접 수정**했습니다(아직 배포 전이므로 새 마이그레이션을 쌓지 않았습니다).

## 남긴 것

- MCP **Firewall** 은 자리(hook point)만 비워 뒀습니다 — Phase 10.
- P2-6 의 감사 귀속 결함(알 수 없는 도구 호출을 첫 번째 바인딩 서버에 귀속)은 리뷰에서 잡혀 `(unbound)` 센티넬로 고쳤습니다.
