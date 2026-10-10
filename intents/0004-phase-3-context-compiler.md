# Intent 0004 — Phase 3: Context Compiler / RAG

| 키 | 값 |
| --- | --- |
| 번호 | 0004 |
| 작성일 | 2026-10-05 |
| 대상 Phase | [../docs/roadmap.md](../docs/roadmap.md) 의 Phase 3 (Week 9~12) — 원본 로드맵 8장 |
| 상태 | 완료 |
| 승인 | showjihyun, 2026-10-05 |
| 완료 | 2026-10-10 — P3-2a·P3-1·P3-2b·P3-3·P3-4·P3-5 전부 병합(마지막 PR #135). spec 개정 1~7 이 실행 중에 찾은 구멍을 메웠고, D-13 의 수동 확인 1회를 같은 날 실행했습니다([../docs/step_results/phase-3.md](../docs/step_results/phase-3.md)) |
| 후속 spec | [../specs/0004-phase-3-context-compiler.md](../specs/0004-phase-3-context-compiler.md) (승인됨 2026-10-05, 개정 1~7) |

작업 단위는 [mvp-backlog.md](mvp-backlog.md) 의 P3-1 ~ P3-5 가 소유합니다. 이 문서는 그 다섯 단위가 **왜** 이번에 함께 가야 하는지, 끝났을 때 무엇이 관측되어야 하는지, 넘지 않을 선이 무엇인지를 고정합니다. 단위의 범위·완료 판정을 여기 복제하지 않습니다.

## Problem

Phase 2 가 끝나(2026-10-03) Agent 가 Gateway 한 곳을 지나 실제 도구를 부릅니다. 그런데 **모델에게 무엇을 보낼지 결정하는 구성 요소가 없습니다.** 관측된 사실은 다음과 같습니다.

- 모델 입력은 `ExecuteRunUseCase` 가 직접 조립합니다 — 빈 목록에서 시작해 `system_prompt` 한 줄을 넣고, 그 뒤 대화와 도구 결과를 **그대로 append** 합니다(`application/usecases/execute_run.py` 235~308행). 무엇을 넣고 무엇을 뺄지 정하는 규칙이 없고, **예산 개념이 없습니다.** 긴 Run 은 모델의 컨텍스트 한계에 그냥 부딪힙니다.
- `packages/context` 와 `packages/memory` 는 세 층의 빈 껍데기입니다(구현 0행). `runtime` 은 `aether_context` 를 한 줄도 import 하지 않습니다 — 그래서 **AR-3(runtime → context 단방향)이 공허하게 통과**합니다. Phase 2 에서 AR-6 이 같은 상태였고, 코드가 생기면서 비로소 발화했습니다.
- **`embed` 는 포트와 어댑터 둘이 이미 있는데 부르는 코드가 없습니다**(`model_gateway.py` 91행, fake·OpenAI-호환 어댑터 각각 구현). Phase 1 이 만들어 둔 자리가 Phase 3 을 기다리고 있습니다. AR-5 의 "임베딩도 gateway 를 지난다" 도 아직 코드로 증명되지 않았습니다.
- Vector DB 가 없습니다. 그래서 `Knowledge`(조직이 소유한 사실)를 적재하거나 검색할 방법이 없고, 제품은 "문서를 아는 Agent" 를 만들 수 없습니다.
- `Memory`(에이전트가 남긴 경험)도 없습니다. [../docs/domain.md](../docs/domain.md) 3절은 `Memory` 와 `Knowledge` 를 **같은 저장소에 섞지 않는다**고 정했는데, 지금은 둘 다 없어서 그 규칙이 지켜지는지 확인할 수단도 없습니다.
- 컨텍스트 비용이 관측되지 않습니다. Run 의 span 에 컨텍스트 토큰 수가 없으므로, "무엇이 예산을 먹는가" 를 사람이 알 수 없고 최적화의 기준선도 없습니다.

`Context` 는 도메인 문서가 **"예산이 있는 자원"** 이라고 정의한 것입니다([../docs/domain.md](../docs/domain.md) 3절). 그 예산을 아무도 관리하지 않는 동안에는 Agent 의 품질이 입력 길이에 좌우되고, 그 좌우됨을 측정할 수도 없습니다.

## Proposed Outcome

Phase 3 이 끝났을 때 다음이 관측 가능합니다. 각 항목은 backlog 의 어느 단위가 판정하는지를 괄호에 적습니다.

- **모델 호출마다 `Context Compiler` 가 입력을 조립합니다.** 같은 입력에 같은 출력이고(결정성), 예산을 넘는 입력은 예산 안으로 줄어들며, **무엇을 먼저 빼는지가 코드에 규칙으로** 있습니다. `Executor` 는 모델을 부르기 전에 그것을 지납니다 (P3-1).
- `runtime → context` 단방향이 코드로 실재하고, 위반을 주입하면 `api-arch` 가 exit 0 이 아닌 값을 냅니다 — AR-3 이 더는 공허하지 않습니다 (P3-1).
- **디렉터리 하나를 적재하면 로컬 Vector DB 에서 검색됩니다.** Connector(Filesystem) → Indexer(청크) → Embedding → Vector DB 가 **오프라인 compose 에서** 동작하고, 임베딩은 `ModelGateway.embed` 를 지납니다(AR-5) (P3-2).
- 적재된 문서의 사실을 묻는 Run 이 **출처와 함께** 답합니다. 검색 결과는 `Observation` 과 같은 방식으로 **신뢰 경계 밖 데이터로 표시**되어 Context 에 들어갑니다. `Agent Version` 에 Knowledge 집합을 바인딩할 수 있습니다 (P3-3).
- **`Memory` 는 `Knowledge` 와 다른 저장소에 있습니다.** 같은 테이블·같은 인덱스를 쓰지 않고, Context 에 들어갈 때 **"검증 전" 표시**가 붙습니다. 그 분리를 테스트가 고정합니다 (P3-4).
- Run 마다 **소스별 컨텍스트 토큰 수**와 성공 여부가 span 속성으로 남고, 트레이스에서 Task Success / Context Token 을 계산할 수 있습니다 (P3-5).
- 위 전부가 **네트워크 없이** 통과합니다 — fake 모델·fake 임베딩으로 결정적으로, 그리고 로컬 LLM 으로 1회 실제 확인(P3-3).
- 새 API 경로는 전부 인증 뒤에 있습니다. 인증 없는 요청은 401 입니다.

## Affected Users

| 대상 | 무엇을 느끼는가 |
| --- | --- |
| 내부 개발자 | 처음으로 "문서를 아는 Agent" 를 만듭니다. 적재 API 로 디렉터리를 올리고, 그 사실을 묻는 Run 이 출처와 함께 답합니다 |
| 운영자 | Run 의 컨텍스트 비용을 봅니다 — 어느 소스가 예산을 먹는지 트레이스에 숫자로 남습니다 |
| 보안·컴플라이언스 검토자 | 검색 결과와 Memory 가 신뢰 경계 밖 데이터로 표시되는 것을 확인할 수 있습니다. `Memory` 가 `Knowledge` 로 승격되지 않는다는 규칙이 저장소 분리로 지켜집니다 |
| 에이전트(하네스) | 컨텍스트 토큰 수가 생기면서 품질·비용을 함께 보는 첫 기준선이 생깁니다. REP 세트에 "예산 안에서 조립하는가" 류의 task 를 더할 근거가 생깁니다(이번 Phase 에서는 더하지 않습니다) |
| 최종 사용자 | 없습니다. `apps/web` 은 이번 Phase 에도 화면을 얻지 않습니다 |

## Affected Systems

[../docs/architecture.md](../docs/architecture.md) 2절의 계층 이름으로 적습니다.

| 계층 / 패키지 | 어떤 영향 |
| --- | --- |
| Context `packages/context` | **비어 있던 껍데기가 처음 채워집니다.** 예산·소스·조립 규칙의 도메인 타입, `CompileContext` inbound 포트, 조립 유스케이스, Knowledge 검색 outbound 포트 |
| Memory `packages/memory` | **첫 구현.** Run 이 남기는 경험의 저장과 조회. `Knowledge` 와 **다른 저장소**이고 읽을 때 검증 전 표시가 붙습니다 |
| Agent Runtime `packages/runtime` | `Executor` 가 모델 입력을 직접 조립하지 않고 `CompileContext` 를 지납니다. `ModelGateway.embed` 가 처음 실제로 호출됩니다 |
| Control Plane `apps/api` | Knowledge 적재 API 와 진행 상태. `Agent Version` 에 Knowledge 집합 바인딩(Phase 2 의 `mcp_servers` 와 같은 방식이 후보 — spec 결정) |
| `apps/worker` | 적재 작업의 실행 자리(동기 API 로 할지 worker 로 넘길지는 열린 질문 3) |
| `infra/docker` | 로컬 Vector DB(열린 질문 1). 오프라인에서 뜨는 것만 |
| 데이터 모델 | Knowledge 청크·임베딩, 적재 작업 상태, Memory 항목의 저장 위치. `control` / `data` 중 어디인지와 Vector DB 가 PostgreSQL 안인지 밖인지가 함께 결정됩니다(열린 질문 1·4) |
| `packages/sdk` | 새 경로의 생성 타입과 호출 함수 |

의존 방향에서 새로 실제 효력을 갖는 것은 **AR-3**(`runtime` 은 `context`·`mcp` 를 쓰고 역방향은 없다)과 **AR-5**(임베딩도 model gateway 를 지난다)입니다. 둘 다 `.importlinter` 에 계약이 있고 이번 Phase 에서 처음으로 막을 코드가 생깁니다. Phase 2 의 경험으로 보면 **조립 지점에서 예외 한 줄이 필요해질 수 있습니다**(AR-6 이 그랬습니다) — 그것은 spec 에서 판단합니다.

## Constraints

- **오프라인이 기본입니다.** Vector DB·임베딩·검색이 인터넷 없이 동작해야 합니다(DP-4). 임베딩 모델은 로컬 LLM 서버가 내는 것을 씁니다.
- **`Context` 는 예산이 있는 자원입니다.** 조립은 결정적이어야 하고(같은 입력 → 같은 출력), 예산 초과 시 무엇을 빼는지가 코드에 있어야 합니다. "알아서 잘" 은 받지 않습니다.
- **`Memory` 와 `Knowledge` 를 같은 저장소에 섞지 않습니다**([../docs/domain.md](../docs/domain.md) 3절). 섞이면 검증되지 않은 경험이 사실로 승격됩니다.
- **검색 결과와 Memory 는 데이터입니다.** 지시로 해석되는 경로를 만들지 않습니다 — Phase 2 의 `Observation` 처리(spec 0002 D-6)와 같은 취급입니다.
- **하위 호환**: Phase 1·2 의 HTTP 계약과 `Agent Version` 불변 규칙은 깨지지 않습니다. 기존 Run 경로는 Context Compiler 를 지나도 같은 결과를 내야 합니다(회귀).
- 비밀값(Vector DB 자격증명 등)을 코드·로그·커밋·span 에 남기지 않습니다.
- **verify 예산**: 합계 10분(spec 0001 D-12). Vector DB 서비스가 늘면 `api-integration`·`smoke` 가 길어집니다 — 넘으면 선택 실패로 집계되므로(2026-09-26-001 적용) 그 시점에 사람이 판단합니다.
- 기간은 Week 9~12 이고 반복·중단 예산은 [../harness/rules/loop-budget.rule.md](../harness/rules/loop-budget.rule.md) 가 소유합니다.

## Open Questions

열린 질문 6건은 2026-10-05 승인과 함께 spec 으로 넘어갔습니다 — 답은 [../specs/0004-phase-3-context-compiler.md](../specs/0004-phase-3-context-compiler.md) 의 D-1 ~ D-7·D-9 가 소유합니다. 아래 표는 무엇을 물었는지의 기록으로 남깁니다.

| # | 질문 | 누가 답하는가 | 언제까지 |
| --- | --- | --- | --- |
| 1 | **Q7** — 로컬 Vector DB 를 무엇으로 할 것인가. PostgreSQL 확장(pgvector: 새 서비스를 늘리지 않고 백업·권한 모델을 재사용)과 전용 서비스(검색 기능은 풍부하지만 compose·운영·오프라인 이미지가 하나 늘어남) 사이의 결정입니다 | 사람 | spec 0004 |
| 2 | 토큰 수를 무엇으로 세는가. 모델별 토크나이저를 들이면 의존이 늘고, 근사(문자/4)로 세면 예산 판정이 모델과 어긋납니다. 어긋남의 허용 범위를 정해야 합니다 | 사람 | spec 0004 |
| 3 | 적재를 동기 API 로 할 것인가 worker 작업으로 넘길 것인가. 동기는 단순하지만 큰 디렉터리에서 요청이 길어지고, worker 는 진행 상태 모델이 하나 더 필요합니다 | 사람 | spec 0004 |
| 4 | 예산과 Knowledge 바인딩을 어디에 두는가. `AgentDefinition` 의 필드(Phase 2 의 `mcp_servers` 처럼 새 경로 0개, 바인딩 변경이 새 Version)인가, 별도 표인가 | 사람 | spec 0004 |
| 5 | 예산 초과 시 빼는 순서. Memory → 오래된 대화 → Knowledge 하위 순위가 기본 후보지만, 그 순서가 품질에 미치는 영향은 측정 전입니다. v1 의 고정 순서를 정하고 근거를 남겨야 합니다 | 사람 | spec 0004 |
| 6 | 임베딩 모델과 차원을 고정할 것인가. 모델이 바뀌면 기존 벡터가 무효가 되므로, 재적재 정책(또는 차원 메타데이터)을 v1 에 둘지 결정해야 합니다 | 사람 | spec 0004 |

## Non-goals

**나중에 할 것.**

- Ranking·Reranker·Compression — Context Compiler v1.1 이후. v1 은 결정적 조립과 예산만 합니다.
- Connector 를 늘리는 것(Filesystem 하나만), 증분 갱신, 권한별 검색 — Phase 3 범위 밖.
- Memory 의 자동 승격·요약·망각 정책 — 승격은 사람의 판정이 있어야 합니다.
- 인용 UI·대시보드, `apps/web` 의 화면.
- 컨텍스트 최적화 자체 — 이번에는 **측정만** 합니다(P3-5).
- Workflow·HITL(Phase 4 이후), Policy Engine(Phase 9), MCP Firewall(Phase 10).

**아예 하지 않을 것.**

- `Memory` 와 `Knowledge` 를 한 저장소에 두는 것.
- 검색 결과나 Memory 를 system 지시로 올리는 경로.
- 컨텍스트 토큰 수를 단일 목표로 주는 것(EI-3 의 제품판) — 줄이는 것 자체가 목적이 되면 품질이 조용히 깎입니다.

## 근거

- 로드맵 8장(Phase 3 — Context Compiler / RAG)과 [mvp-backlog.md](mvp-backlog.md) 의 P3-1 ~ P3-5. 등급 판정은 [../docs/roadmap.md](../docs/roadmap.md) 1절.
- intent 0003 완료(2026-10-03). Phase 2 의 Proposed Outcome 전부가 병합되어 이 Phase 의 전제(도구 호출이 지나는 통로, Run 루프)가 성립합니다.
- 관측된 사실: 모델 입력을 `ExecuteRunUseCase` 가 직접 조립하며 예산 개념이 없음, `packages/context`·`packages/memory` 구현 0행, `embed` 포트·어댑터는 있으나 호출자 0건, Vector DB 없음, 컨텍스트 토큰 수 미관측.
- [../docs/domain.md](../docs/domain.md) 3절이 정의한 `Context`·`Knowledge`·`Memory` 와 그 분리 규칙. 이 Phase 는 그 정의에 코드를 붙입니다.
