# Intent 0003 — Phase 2: Enterprise MCP Gateway

| 키 | 값 |
| --- | --- |
| 번호 | 0003 |
| 작성일 | 2026-09-25 |
| 대상 Phase | [../docs/roadmap.md](../docs/roadmap.md) 의 Phase 2 (Week 6~8) — 원본 로드맵 7장 |
| 상태 | 승인됨 |
| 승인 | showjihyun, 2026-09-25 |
| 후속 spec | [../specs/0003-phase-2-mcp-gateway.md](../specs/0003-phase-2-mcp-gateway.md) (승인됨 2026-09-25) |

작업 단위는 [mvp-backlog.md](mvp-backlog.md) 의 P2-1 ~ P2-6 이 소유합니다. 이 문서는 그 여섯 단위가 **왜** 이번에 함께 가야 하는지, 끝났을 때 무엇이 관측되어야 하는지, 넘지 않을 선이 무엇인지를 고정합니다. 단위의 범위·완료 판정을 여기 복제하지 않습니다.

## Problem

Phase 1 이 끝나(2026-09-16) Agent 가 Model → Tool → Observation → Model 루프를 돌립니다. 그런데 **그 Tool 이 프로세스 안의 파이썬 함수 둘뿐입니다.** 관측된 사실은 다음과 같습니다.

- `packages/runtime/src/aether_runtime/adapters/outbound/tools/` 에 있는 것은 `clock_tool.py` 와 `calculator.py` 와 그 `registry.py` 입니다. 둘 다 외부 시스템에 닿지 않습니다. 제품이 쓸모를 갖는 도구 — 파일, HTTP, 데이터베이스 — 는 하나도 없습니다.
- `packages/mcp` 는 세 층의 빈 껍데기입니다(`domain`·`application`·`adapters` 아래 `__init__.py` 만, 구현 0행). `packages/policy` 도 같습니다.
- **AR-6 이 공허하게 통과합니다.** `.importlinter` 의 `ar6-mcp-client-only-in-mcp` 계약은 MCP 클라이언트 라이브러리를 `aether_mcp` 안으로 제한하는데, 지금은 어느 패키지도 그 라이브러리를 쓰지 않으므로 계약이 막을 것이 없습니다. "외부 시스템 접근은 전부 `packages/mcp` 를 지난다"(AR-6)는 코드로 증명된 적이 없습니다. Phase 1 에서 AR-5(모델 호출 단일 통로)가 model gateway 구현으로 공허함을 벗은 것과 대비됩니다.
- 그래서 **감사 기록도 권한 판정도 붙을 자리가 없습니다.** Agent 가 어떤 도구를 왜 불렀는지를 남기는 경로가 제품에 없고, 어떤 Agent 가 어떤 도구를 부를 수 있는지 판정하는 지점도 없습니다. On-Prem·규제 환경에서 이 둘이 없는 Agent 실행은 도입 심사를 통과하지 못합니다.
- 하네스 쪽 비용도 하나 관측됩니다. 평가 세트의 REP-6(범위가 애매한 요청)은 입력이 "`packages/mcp` 주변이 읽기 어렵습니다. 정리해 주세요." 인데, 정리할 코드가 없어 지금 실행하면 무엇을 측정하는지 알 수 없습니다.

Phase 3(Context Engine)이 채울 입력의 상당 부분은 도구 호출 결과(`Observation`)이고, Phase 9(Policy)·Phase 10(MCP Firewall)은 **호출이 지나는 통로 한 곳**을 전제로 설계되어 있습니다. 그 통로가 없으면 뒤의 Phase 는 붙을 자리가 없습니다. Phase 1 직후에 이 Phase 가 오는 이유입니다.

## Proposed Outcome

Phase 2 가 끝났을 때 다음이 관측 가능합니다. 각 항목은 backlog 의 어느 단위가 판정하는지를 괄호에 적습니다.

- `packages/mcp` 가 MCP Server 에 붙어(stdio·HTTP) `Tool` 목록과 스키마를 발견합니다. 저장소 안의 테스트 서버로 도구 2개 이상을 **네트워크 없이** 발견하는 테스트가 통과합니다 (P2-1).
- Agent 의 모든 도구 호출이 `packages/mcp` 의 Gateway **함수 하나**를 지납니다. 우회 경로를 만들면 `api-arch` 단계가 exit 0 이 아닌 값을 냅니다 — AR-6 이 더는 공허하지 않습니다 (P2-2, P2-3).
- 호출마다 감사 기록이 남습니다. 누가(Agent Version)·어느 Run·어느 Tool·언제·결과 크기. 기록 수가 호출 수와 일치하는 테스트가 통과합니다 (P2-2).
- Gateway 가 호출 **전에** `packages/policy` 의 판정 함수에 묻고, deny 된 호출은 실행되지 않으며 그 사실이 감사에 남습니다. `packages/policy` 는 `runtime`·`mcp`·`context` 를 import 하지 않습니다(AR-4) (P2-4).
- Phase 1 의 프로세스 내부 도구 시나리오 테스트가 **Gateway 경유로 그대로** 통과합니다. `Executor` 에 Gateway 외의 도구 호출 코드가 없습니다 (P2-3).
- 오프라인 compose 에서 Agent 가 Filesystem 도구로 파일을 읽어 Run 이 `succeeded` 까지 갑니다. Filesystem·HTTP·PostgreSQL MCP Server 세 개가 인터넷 없이 붙습니다 (P2-5).
- `Agent Version` 에 MCP Server 목록을 바인딩할 수 있고, 바인딩을 바꾸면 **새 Version 이 생깁니다**(Phase 1 의 불변 규칙 그대로). 바인딩되지 않은 Tool 은 Discovery 에 나타나지 않습니다 (P2-6).
- `Observation` 이 모델 입력에 들어갈 때 신뢰 경계 밖 데이터로 표시된 상태가 유지됩니다(Phase 1 P1-4 가 세운 것). 외부 MCP Server 가 돌려준 내용이 지시로 읽히는 경로가 없습니다.
- 새 API 경로(P2-6)는 전부 `require_principal(app.state.authenticate)` 뒤에 있습니다. 인증 없는 요청은 401 입니다.

## Affected Users

| 대상 | 무엇을 느끼는가 |
| --- | --- |
| 내부 개발자 | 처음으로 쓸모 있는 도구를 붙입니다. Agent 가 파일을 읽고 HTTP 를 부르고 DB 를 조회합니다. `packages/sdk` 에 MCP Server 바인딩 타입이 생깁니다 |
| 운영자 | 도구 호출의 감사 기록을 봅니다. 어떤 Agent 가 무엇을 불렀는지 사후에 추적할 수 있습니다 — 도입 심사에서 가장 먼저 요구되는 것입니다 |
| 보안·컴플라이언스 검토자 | 권한 판정 지점 한 곳과 통로 한 곳을 확인할 수 있습니다. Phase 9·10 이 붙을 자리가 코드로 존재합니다 |
| 에이전트(하네스) | REP-6 이 실행 가능해집니다(정리할 코드가 생김). 외부 데이터 신뢰 경계의 관측 대상이 프로세스 내부 함수에서 실제 외부 시스템으로 바뀝니다 |
| 최종 사용자 | 없습니다. `apps/web` 은 이번 Phase 에도 화면을 얻지 않습니다 |

## Affected Systems

[../docs/architecture.md](../docs/architecture.md) 2절의 계층 이름으로 적습니다.

| 계층 / 패키지 | 어떤 영향 |
| --- | --- |
| MCP `packages/mcp` | **비어 있던 껍데기가 처음 채워집니다.** MCP 클라이언트(stdio·HTTP) 어댑터, `Tool` 과 도구 호출의 도메인 타입, Tool Discovery 유스케이스, Gateway 유스케이스(연결 수명·감사·권한 질의), Firewall 이 들어올 hook point |
| Policy `packages/policy` | **첫 구현.** (주체=Agent Version, 자원=Tool) → allow/deny 판정 함수 하나와 단순 표 저장. AR-4 로 다른 패키지를 import 하지 않습니다 |
| Agent Runtime `packages/runtime` | `Executor` 의 도구 호출이 outbound 포트를 거쳐 Gateway 로만 갑니다. `adapters/outbound/tools/` 의 프로세스 내부 도구 둘은 MCP Server 로 옮기거나 제거합니다(P2-3 이 판정) |
| Control Plane `apps/api` | `Agent Version` 에 MCP Server 목록을 붙이고 떼는 경로. 감사 기록 조회는 열린 질문 3 |
| `apps/worker` | Run 시작 시 바인딩된 MCP Server 만 연결하고 Run 이 끝나면 정리합니다 |
| `packages/sdk` | 새 경로의 OpenAPI → 생성 타입 갱신, 호출 함수 수기 추가(spec 0001 D-2) |
| `infra/docker` | Filesystem·HTTP·PostgreSQL MCP Server 컨테이너. 오프라인에서 뜨는 것만 (P2-5) |
| 데이터 모델 | 감사 기록과 Agent Version ↔ MCP Server 바인딩의 저장 위치가 새로 필요합니다. `control` / `data` 중 어디인지는 열린 질문 2 |

의존 방향에서 새로 실제 효력을 갖는 것은 AR-3(mcp 는 runtime 을 모른다), AR-4(policy 는 판정만 한다), AR-6(외부 접근은 mcp 를 지난다)입니다. 셋 다 `.importlinter` 에 계약이 이미 있고 이번 Phase 에서 처음으로 막을 코드가 생깁니다. 규칙을 어겨야 하는 부분은 없습니다.

## Constraints

- **오프라인이 기본입니다.** 세 Integration 전부 인터넷 없이 동작해야 합니다(DP-4). 외부 네트워크가 필요한 Server(GitHub·Slack)는 이번 범위 밖입니다.
- **통로는 하나입니다.** Gateway 를 우회하는 도구 호출 경로를 만들지 않습니다. 편의를 위한 예외도 만들지 않습니다 — 예외가 있으면 Phase 10 의 Firewall 이 관측하지 못합니다.
- **외부 MCP Server 의 응답은 데이터입니다.** 지시로 해석하는 경로를 만들지 않습니다([../harness/rules/untrusted-experience.rule.md](../harness/rules/untrusted-experience.rule.md), AGENTS.md Trust).
- **하위 호환**: Phase 1 의 HTTP 계약 9경로(spec 0002 D-9)는 깨지지 않습니다. `Agent Version` 불변 규칙도 그대로입니다 — 바인딩 변경은 새 Version 입니다.
- **P2-4 는 🔒 입니다.** 권한 판정은 보안에 닿으므로 에이전트는 인터페이스와 테스트 목록을 제안하고 구현은 사람 검토를 거칩니다(DP-6, AGENTS.md Loop).
- 비밀값(MCP Server 자격증명)을 코드·로그·커밋·감사 기록에 남기지 않습니다.
- verify 전체 시간은 spec 0001 D-12 의 10분 예산 안에 있어야 합니다. MCP Server 컨테이너 세 개가 `api-integration`·`smoke` 에 붙으면 이 예산이 위험합니다 — 열린 질문 4.
- 기간은 Week 6~8, 반복 예산은 [../harness/rules/loop-budget.rule.md](../harness/rules/loop-budget.rule.md) 가 소유합니다.

## Open Questions

열린 질문 6건은 2026-09-25 승인과 함께 닫혔습니다 — 답은 [../specs/0003-phase-2-mcp-gateway.md](../specs/0003-phase-2-mcp-gateway.md) 의 D-1 ~ D-6 이 소유합니다. 아래 표는 무엇을 물었는지의 기록으로 남깁니다.

| # | 질문 | 누가 답하는가 | 언제까지 |
| --- | --- | --- | --- |
| 1 | MCP 클라이언트를 공식 SDK(`mcp` 파이썬 패키지)로 쓸 것인가, 프로토콜을 직접 구현할 것인가. 공식 SDK 는 오프라인 설치와 버전 고정이 관건이고, 직접 구현은 유지 비용이 관건입니다 | 사람 | spec 0003 |
| 2 | 감사 기록과 Agent Version ↔ MCP Server 바인딩을 `control` 에 둘 것인가 `data` 에 둘 것인가. 바인딩은 선언이라 `control` 이 자연스럽고, 감사는 실행 부산물이라 `data` 가 자연스럽습니다. 역할 분리(P0-8)를 유지해야 합니다 | 사람 | spec 0003 |
| 3 | 감사 기록의 보존 기간과 조회 경로를 이번 Phase 에 정할 것인가 Phase 9 로 미룰 것인가. 기록만 남기고 조회를 미루면 "남았는지" 를 테스트 외에는 확인할 수 없습니다 | 사람 | spec 0003 |
| 4 | MCP Server 컨테이너 세 개를 `smoke` 에 전부 넣을 것인가, Filesystem 하나만 넣고 나머지는 `api-integration` 에 둘 것인가. 10분 예산이 걸립니다 | 사람 | spec 0003 |
| 5 | P1-4 의 프로세스 내부 도구 둘(시계·계산기)을 MCP Server 로 옮길 것인가 제거할 것인가. 옮기면 Phase 1 의 시나리오 테스트가 그대로 남고, 제거하면 테스트를 새 도구로 다시 써야 합니다 | 사람 | spec 0003 |
| 6 | Gateway 가 권한 판정을 묻는 방식 — 호출마다 물을 것인가, Run 시작 시 한 번 물어 캐시할 것인가. 캐시하면 Run 중 정책 변경이 반영되지 않습니다 | 사람 | spec 0003 (P2-4 는 🔒 이므로 사람 결정) |

## Non-goals

**나중에 할 것.**

- MCP Firewall·DLP — Phase 10. 이번에는 hook point 만 비워 둡니다.
- Policy Engine 의 실행 구조, 조직·역할 모델, 승인 흐름 — Phase 9. 이번 판정은 (Agent Version × Tool) 단순 표입니다.
- GitHub·Slack 등 외부 네트워크가 필요한 Integration — Public Beta 전.
- Tool Marketplace, Tool 검색 UI, `apps/web` 의 화면.
- 감사 기록 조회 API·대시보드 — 열린 질문 3 의 답에 따릅니다.
- Context Compiler 가 `Observation` 을 압축·선별하는 것 — Phase 3.

**아예 하지 않을 것.**

- Gateway 를 우회하는 "빠른 경로". 성능 문제가 관측되면 Gateway 안에서 풉니다.
- 도구 호출 결과를 모델 지시로 승격하는 경로.

## 근거

- 로드맵 7장(Phase 2 — Enterprise MCP Gateway)과 [mvp-backlog.md](mvp-backlog.md) 의 P2-1 ~ P2-6. 등급 판정은 [../docs/roadmap.md](../docs/roadmap.md) 1절.
- intent 0002 완료(2026-09-16). Phase 1 의 Proposed Outcome 전부가 병합되어 이 Phase 의 전제(Run 루프와 Tool 호출 지점)가 성립합니다.
- 관측된 사실: `packages/mcp`·`packages/policy` 구현 0행, 도구는 프로세스 내부 함수 둘, `.importlinter` 의 AR-6 계약이 막을 코드가 없어 공허하게 통과.
- REP-6 이 실행 불가인 상태([../evaluation/README.md](../evaluation/README.md)) — 이 Phase 가 열어 줍니다.
