# Spec 0004 — Phase 3: Context Compiler / RAG

| 키 | 값 |
| --- | --- |
| 번호 | 0004 |
| 작성일 | 2026-10-05 |
| 선행 intent | [../intents/0004-phase-3-context-compiler.md](../intents/0004-phase-3-context-compiler.md) (승인됨 2026-10-05) |
| 상태 | 승인됨 |
| 승인 | showjihyun, 2026-10-05 |
| 대상 단위 | [../intents/mvp-backlog.md](../intents/mvp-backlog.md) 의 P3-1 ~ P3-5 (P3-2 는 plan 에서 2a·2b 로 분할) |
| 후속 plan | [../plans/0004-phase-3-context-compiler.md](../plans/0004-phase-3-context-compiler.md) (승인 대기) |

이 문서는 intent 0004 의 열린 질문 6건을 결정(D-1 ~ D-14)으로 고정하고, 다섯 단위의 완료 판정을 **검증 가능한 명제**(R-1 ~ R-12)로 옮깁니다. 단위의 범위는 backlog 가 소유합니다.

Phase 1·2 의 결정(spec 0002 D-1 ~ D-19, spec 0003 D-1 ~ D-16)은 그대로 유효합니다. 이 spec 이 그중 무엇을 개정하면 해당 항목에 `[실질] 개정` 을 명시합니다.

## 1. 요구사항

| # | 요구사항 | 근거 | 어떻게 판정하는가 |
| --- | --- | --- | --- |
| R-1 | `Context Compiler` 가 모델 입력을 **결정적으로** 조립합니다 — 같은 입력에 같은 출력 | Outcome 1 (P3-1) | `api-unit`: 같은 소스 집합·같은 예산으로 100회 조립해 결과가 전부 동일. 딕셔너리 순회 순서나 집합 순서에 의존하지 않음을 그 테스트가 고정 |
| R-2 | 예산을 넘는 입력이 예산 안으로 줄고, **무엇을 뺐는지가 결과에 남습니다** | Outcome 1 (P3-1) | `api-unit`: 예산의 3배 입력 → 조립 결과의 토큰 추정이 예산 이하. 뺀 소스와 양이 `ContextReport`(2.3)에 들어 있고 D-7 의 순서를 따름 |
| R-3 | `Executor` 가 모델을 부르기 전에 Compiler 를 지납니다. 직접 조립 경로가 남지 않습니다 | Outcome 1 (P3-1) | `api-unit`: Phase 1·2 의 Run 시나리오가 Compiler 를 거쳐 그대로 통과(회귀). 구조 테스트로 `execute_run.py` 에 `Message(` 직접 조립이 0건 |
| R-4 | `runtime → context` 단방향이 실재하고 위반을 주입하면 아키텍처 단계가 실패합니다 | Outcome 2, AR-3 | `api-arch` + `tests/arch/test_real_importlinter_fires.py` 에 `aether_context/_bad.py`(`import aether_runtime.application`) 주입 케이스 1건 |
| R-5 | 디렉터리 하나를 적재하면 로컬 Vector DB 에서 검색됩니다 | Outcome 3 (P3-2) | `api-integration`: testcontainers 로 pgvector 를 띄워 문서 3개를 적재하고, 그중 하나의 고유 문장으로 검색해 그 청크가 1위로 나옴 |
| R-6 | 임베딩은 `ModelGateway.embed` 를 지납니다 | Outcome 3, AR-5 | `api-arch`: `aether_context` 가 `httpx`·벤더 SDK 를 import 하지 않음(AR-5·AR-9). `api-unit`: fake gateway 의 `embed` 호출 수가 청크 수와 일치 |
| R-7 | 적재가 **오프라인에서** 동작합니다 | Outcome 3, DP-4 | `smoke`: egress 차단 compose 에서 디렉터리 적재 → 검색 1건 성공. 임베딩은 로컬 LLM 서버의 `/v1/embeddings` |
| R-8 | 적재된 사실을 묻는 Run 이 **출처와 함께** 답하고, 검색 결과는 신뢰 경계 밖 데이터로 표시됩니다 | Outcome 4 (P3-3) | `api-integration`: fake 모델이 받은 요청에서 Knowledge 블록이 `trust: untrusted` + 출처(문서 경로·청크 id)를 달고 있고 system 메시지에 섞이지 않음. 로컬 LLM 1회 수동 확인(2.10) |
| R-9 | `Agent Version` 에 Knowledge 집합을 바인딩할 수 있고, 바인딩 변경은 **새 Version** 입니다 | Outcome 4 (P3-3), D-5 | `api-integration`: `PUT /agents/{id}` 로 `knowledge` 만 바꿔 `current_version == 2`, Version 1 불변. 바인딩되지 않은 집합은 검색되지 않음 |
| R-10 | `Memory` 와 `Knowledge` 가 **같은 테이블·같은 인덱스를 쓰지 않습니다**. Memory 는 Context 에 들어갈 때 "검증 전" 표시가 붙습니다 | Outcome 5 (P3-4), domain 3절 | `api-integration`: 두 테이블 이름과 인덱스 목록이 겹치지 않음을 DB 카탈로그로 확인. `api-unit`: Memory 블록에 `verified: false` 표지가 있고 Knowledge 블록과 다른 표지를 씀 |
| R-11 | Run 마다 **소스별 컨텍스트 토큰 수**와 성공 여부가 span 속성으로 남습니다 | Outcome 6 (P3-5) | `api-unit`: 인메모리 `Tracer` 에서 `context.tokens.{system,conversation,knowledge,memory,tools}` 와 `context.budget`·`context.dropped` 속성 확인. `smoke`: collector 출력에 그 속성이 나타남 |
| R-12 | verify 전체가 10분 예산 안입니다 | intent Constraints | `.harness/verify.json` 의 합계 ≤ 600,000 ms. 넘으면 선택 실패로 집계되고(2026-09-26-001) 사람이 판단합니다 |

## 2. 설계

### 2.1 배치와 호출 방향

```
apps/worker ──► aether_runtime.application (Planner/Executor)
                      │ outbound 포트 ContextCompiler (runtime 이 선언)
                      ▼
              aether_runtime.adapters.outbound.context_compiler
                      │ inbound 포트 CompileContext (context 가 선언)
                      ▼
              aether_context.application.usecases  ── 조립 한 곳
                 │                  │                   │
                 │ outbound         │ outbound          │ outbound
                 ▼                  ▼                   ▼
          KnowledgeSearch      MemoryReader        TokenCounter
        (pgvector 어댑터)    (aether_memory 포트)   (근사, D-6)
```

- 방향은 `runtime → context → memory` 입니다. AR-3(`context` 는 `runtime` 을 모른다)과 AR-4 계열이 유지됩니다.
- `runtime` 은 `aether_context` 의 **inbound 포트 타입만** 봅니다(AR-12). 조립은 worker 의 `main` 입니다 — Phase 2 에서 AR-6 예외가 필요했던 것과 같은 자리이므로, `.importlinter` 예외가 필요해지면 **P3-1 병합 뒤 한 번**에 사람이 처리합니다(D-14).
- 임베딩은 `aether_context` 가 `aether_runtime` 의 `ModelGateway` 를 직접 보지 않습니다 — `Embedder` outbound 포트를 선언하고 worker 가 runtime 의 gateway 를 꽂습니다(AR-3 방향 유지).

### 2.2 조립 규칙과 예산 (P3-1, 열린 질문 2·5)

입력은 소스 다섯입니다 — `system`(Agent 의 `system_prompt`), `conversation`(지금까지의 메시지), `knowledge`(검색 결과), `memory`(경험), `tools`(도구 스키마).

조립은 **고정된 순서**로 합니다. 먼저 전부를 담고 토큰을 추정한 뒤, 예산을 넘으면 D-7 의 순서로 뺍니다. 같은 입력이면 같은 출력이어야 하므로 집합·딕셔너리를 순회할 때 **항상 정렬된 키**를 씁니다(R-1).

예산은 `AgentDefinition.context_budget_tokens`(D-5)입니다. 기본값은 모델 한계가 아니라 **보수적인 고정값**(8192)으로 둡니다 — 모델별 한계를 알아내는 것은 이 Phase 의 범위 밖이고, 작게 시작해 늘리는 쪽이 조용한 품질 저하를 피합니다.

### 2.3 `ContextReport` — 무엇을 넣고 뺐는가

조립 결과는 모델 입력(메시지 목록)과 함께 보고를 돌려줍니다. 보고에는 소스별 토큰 추정, 예산, 뺀 소스와 양이 들어갑니다. 이것이 R-2 의 판정 대상이고 R-11 의 span 속성 원천입니다. **보고에 본문을 넣지 않습니다** — 숫자와 종류만입니다(감사표와 같은 이유, spec 0003 D-12).

### 2.4 Knowledge 적재 (P3-2, 열린 질문 1·3·6)

`Connector(Filesystem) → Indexer(청크) → Embedder → KnowledgeStore` 네 단계입니다.

| 항목 | 결정 |
| --- | --- |
| Vector DB | **pgvector**(D-1). 새 서비스를 늘리지 않고 백업·권한·마이그레이션 경로를 재사용합니다 |
| 청크 | 문자 기준 고정 크기 + 겹침(기본 1000/200). 토큰 기준이 아닌 이유는 D-6 과 같습니다 |
| 임베딩 모델 | **별도 핀**(D-3). 지금 어댑터는 채팅 모델 id 를 `/embeddings` 로 보냅니다 — 그대로 두면 적재가 실패합니다 |
| 실행 자리 | **worker 작업**(D-4). api 는 적재를 **선언**하고 worker 가 실행합니다 — Run 과 같은 모양입니다 |
| 진행 상태 | `control.knowledge_ingestions`(선언·상태). 청크·벡터는 `data.knowledge_chunks`. **쓰는 주체는 api 뿐입니다**(개정 5) — `aether_data` 는 그 표에 SELECT 만 가지므로(P3-2a 의 GRANT) worker 는 상태를 직접 쓸 수 없고 **상태 스트림으로 api 에 되돌려 보냅니다**. Run 의 `aether:runs:status` 와 같은 모양입니다 |

### 2.5 검색 결과를 Context 에 (P3-3)

검색 결과는 `Observation` 과 같은 취급입니다 — `trust: untrusted` 표지와 출처(문서 경로·청크 id)를 달고 **전용 블록**으로 들어갑니다. system 메시지에 섞지 않습니다(R-8). 출처가 없는 청크는 Context 에 넣지 않습니다 — 출처 없는 사실은 검증할 수 없습니다.

### 2.6 Memory v1 (P3-4)

Run 이 종결할 때 남길 것이 있으면 `data.agent_memory` 에 적습니다(Agent 단위). 읽을 때는 **`verified: false`** 표지가 붙어 Context 에 들어갑니다. `Knowledge` 와 **다른 테이블·다른 인덱스**이고, 둘을 한 쿼리로 합치지 않습니다(R-10).

무엇을 남길지는 v1 에서 **Executor 가 명시적으로 넘긴 것만** 입니다 — 자동 요약·자동 승격은 Non-goal 입니다.

**트리거와 내용(개정 6).** `AgentDefinition.memory_enabled`(기본 거짓)가 참이고 Run 이 `succeeded` 로 **종결된 뒤**, Executor 가 **마지막 assistant 메시지의 본문 그대로** 한 건을 넘깁니다. 본문이 비어 있으면 넘기지 않습니다. 쓰기 실패는 Run 의 결과를 바꾸지 않습니다 — Memory 는 부산물이고, 경고에 본문을 남기지 않습니다(C-5, Trust). `memory_enabled` 는 **읽기도** 막습니다 — 끈 Agent 는 예전 기억이 있어도 읽지 않습니다. 읽기의 상위 k 기본값은 3 이고, 다른 임베딩 모델로 만든 기억은 D-9 의 오류가 아니라 **조용한 제외**입니다(재적재할 원본이 없습니다).

### 2.7 KPI 계측 (P3-5)

`ContextReport`(2.3)의 숫자를 span 속성으로 올립니다 — `context.tokens.*`, `context.budget`, `context.dropped.*`. Task Success 는 Run 의 종결 상태에서 옵니다. 집계 쿼리 하나를 `docs/` 에 예시로 둡니다. **이 숫자를 단일 목표로 주지 않습니다**(EI-3 제품판, intent Non-goals).

### 2.8 데이터 모델 변경 (마이그레이션 0004)

| 대상 | 스키마 | 왜 |
| --- | --- | --- |
| `control.knowledge_sets` | `control` | 선언입니다(Agent 가 바인딩하는 집합의 이름) |
| `control.knowledge_ingestions` | `control` | 적재 **선언**과 상태. api 가 쓰고 worker 가 읽습니다 — `control.runs` 와 같은 모양 |
| `data.knowledge_chunks` | `data` | 실행 부산물(청크 본문·임베딩·출처). worker 가 씁니다 |
| `data.agent_memory` | `data` | 같은 이유. **`knowledge_chunks` 와 다른 테이블·다른 인덱스**(R-10) |

GRANT 는 Phase 2 의 방향을 따릅니다 — `aether_control` 은 `control` 전부, `aether_data` 는 `data` 전부와 `control` 의 필요한 표 **SELECT 만**. 감사표처럼 append-only 가 필요한 표는 없습니다(청크는 재적재 시 교체).

### 2.9 설정 (추가되는 환경변수)

| 변수 | 기본 | 누가 읽는가 |
| --- | --- | --- |
| `AETHER_EMBED_MODEL_ID` | `nomic-embed-text` | worker. 채팅 모델과 **다른** 모델입니다(D-3) |
| `AETHER_EMBED_DIM` | `768` | worker·마이그레이션. 벡터 열의 차원이고 모델과 함께 바뀝니다(D-9) |
| `AETHER_CONTEXT_BUDGET_TOKENS` | `8192` | worker. `AgentDefinition` 이 지정하지 않았을 때의 기본값 |
| `AETHER_KNOWLEDGE_CHUNK_CHARS` / `AETHER_KNOWLEDGE_CHUNK_OVERLAP_CHARS` | `1000` / `200` | worker (개정 5: 축약 표기를 정식 이름으로) |

### 2.9.1 smoke 의 적재·검색 시나리오 (개정 5)

R-7(오프라인 적재 → 검색)은 **P3-3 이후에 `smoke` 에 들어갑니다.** P3-2b 시점에는 검색의 HTTP
경로가 없어(그것이 P3-3 의 범위) `smoke` 가 API 로 확인할 방법이 없습니다. 보조 스크립트로
어댑터를 직접 부르는 것은 smoke 가 "제품이 쓰는 경로" 를 보는 단계라는 성질을 깨므로 하지
않습니다. 그 사이의 판정은 `api-integration` 의 pgvector 테스트가 같은 경로를 덮습니다(R-5).

### 2.10 검증 단계

단계 **수는 늘리지 않습니다.** `smoke` 에 적재·검색 시나리오를 더하고(R-7), 나머지는 `api-integration` 에서 pgvector testcontainer 로 판정합니다(R-5·R-8·R-9·R-10). 로컬 LLM 으로 실제 임베딩을 한 번 확인하는 것은 **사람의 수동 확인**입니다(spec 0002 2.5 와 같은 취급) — 모델 다운로드를 CI 에 넣지 않습니다.

### 2.11 아키텍처 규칙 (보호 파일 `.importlinter`, 사람)

| 계약 | 변경 |
| --- | --- |
| `ar3-mcp-and-context-must-not-import-runtime` | 변경 없음. 처음으로 막을 코드가 생깁니다 |
| AR-5 | `aether_context` 가 이미 금지 목록에 있습니다. 임베딩을 포트로 받으므로 그대로 통과해야 합니다 |
| 새 예외(필요 시) | worker 의 조립이 `aether_context.adapters` 를 보면 Phase 2 와 같은 `ignore_imports` 한 줄이 필요합니다. P3-1 병합 뒤 한 번, 사람이 커밋(D-14) |

## 3. 우려 지점

| # | 우려 | 지금의 답 |
| --- | --- | --- |
| C-1 | pgvector 이미지는 Debian 계열이고 지금 쓰는 것은 `postgres:16-alpine` 입니다. 이미지를 바꾸면 init 스크립트·로케일·크기가 함께 바뀝니다 | 교체는 P3-2 의 첫 작업이고, 기존 마이그레이션·역할 테스트가 그대로 통과하는지가 그 단위의 완료 판정입니다. 통과하지 않으면 거기서 멈추고 보고합니다 |
| C-2 | 토큰 근사(D-6)는 모델의 실제 토크나이저와 어긋납니다 | 예산을 보수적으로(8192) 두고, 어긋남의 방향을 **과대 추정**으로 고정합니다 — 과소 추정은 모델 한계를 넘기지만 과대 추정은 조금 덜 넣는 것에서 끝납니다 |
| C-3 | 임베딩 모델을 바꾸면 기존 벡터가 무효입니다 | 차원과 모델 id 를 청크와 함께 저장하고(D-9), 불일치가 검색에서 발견되면 **재적재를 요구하는 오류**를 냅니다. 자동 재적재는 하지 않습니다 |
| C-4 | 적재가 worker 작업이면 진행 상태 모델이 하나 늘어납니다 | `control.runs` 와 같은 모양을 그대로 씁니다(선언 → 상태 전이). 새 패턴을 만들지 않습니다. 양방향 스트림 두 개(요청·상태)가 그 모양의 일부입니다(개정 5) |
| C-5 | Memory 가 Context 를 조용히 오염시킬 수 있습니다 | 표지(`verified: false`)와 D-7 의 **첫 번째 제거 대상**이 그 위험을 제한합니다. 자동 승격은 Non-goal 입니다 |
| C-6 | pgvector 와 testcontainers 가 verify 시간을 늘립니다 | 기존 PG 컨테이너를 pgvector 이미지로 **교체**하므로 컨테이너 수는 늘지 않습니다. 실측은 P3-2 에서 기록합니다(R-12) |

## 4. 결정 요청

| # | 결정 | 근거 | 어디 |
| --- | --- | --- | --- |
| D-1 | 로컬 Vector DB 는 **pgvector**. compose 의 PostgreSQL 이미지를 `pgvector/pgvector:pg16`(다이제스트 핀)으로 교체하고 확장을 마이그레이션에서 `CREATE EXTENSION` 합니다. 새 서비스는 늘리지 않습니다 | intent OQ 1 (**Q7**) | 2.4, C-1 |
| D-2 | 벡터 검색은 코사인 거리 + HNSW 인덱스. 상위 k 는 기본 5 이고 `AgentDefinition` 이 바꿀 수 있습니다 | — | 2.4 |
| D-3 | 임베딩 모델은 **채팅 모델과 별도 핀**(`AETHER_EMBED_MODEL_ID`, 기본 `nomic-embed-text`). 지금 어댑터는 채팅 모델 id 를 `/embeddings` 로 보내므로 그대로 두면 적재가 실패합니다 — spec 0002 2.5 를 **[실질] 개정**합니다 | 실측(어댑터 231행) | 2.9 |
| D-4 | 적재는 **worker 작업**. api 는 선언하고 worker 가 실행합니다 | intent OQ 3 | 2.4, C-4 |
| D-5 | 예산·Knowledge 바인딩·상위 k 는 **`AgentDefinition` 의 필드**. 새 HTTP 경로를 만들지 않고, 바인딩 변경은 기존 `PUT` 이 새 Version 을 만듭니다(Phase 2 의 `mcp_servers` 와 같은 방식) | intent OQ 4 | 2.2, R-9 |
| D-6 | 토큰은 **근사**로 셉니다 — 문자 수 ÷ 4 를 올림. 토크나이저 의존을 들이지 않습니다. 어긋남은 **과대 추정 방향으로 고정**합니다 | intent OQ 2 | 2.2, C-2 |
| D-7 | 예산 초과 시 빼는 순서는 **Memory → 오래된 대화 → Knowledge 하위 순위 → 도구 스키마의 설명** 입니다. `system` 과 가장 최근 대화 한 쌍은 빼지 않습니다 | intent OQ 5 | 2.2, R-2 |
| D-8 | 검색 결과·Memory 는 전용 블록에 `trust: untrusted`·`verified: false` 표지와 출처를 달고 들어갑니다. 출처 없는 청크는 넣지 않습니다 | Trust, spec 0002 D-6 | 2.5, 2.6 |
| D-9 | 청크와 함께 **임베딩 모델 id 와 차원**을 저장합니다. 불일치는 검색에서 **재적재를 요구하는 오류**로 드러냅니다. 자동 재적재는 없습니다 | intent OQ 6 | 2.4, C-3 |
| D-10 | 데이터 모델은 2.8 의 네 표. 선언은 `control`, 부산물은 `data`. Memory 와 Knowledge 는 다른 표·다른 인덱스 | domain 3절 | 2.8, R-10 |
| D-11 | `Context Compiler` 는 모델 입력과 함께 `ContextReport` 를 돌려줍니다. 보고에 **본문을 넣지 않습니다**(숫자·종류만) | R-2, R-11 | 2.3 |
| D-12 | 조립은 결정적이어야 하고 그것을 100회 반복 테스트로 고정합니다. 정렬되지 않은 순회를 쓰지 않습니다 | R-1 | 2.2 |
| D-13 | 로컬 LLM 으로 실제 임베딩 확인은 **사람의 수동 확인** 1회. 모델 다운로드를 CI 에 넣지 않습니다. **2026-10-10 실행 완료**(개정 7) — 기록은 [../docs/step_results/phase-3.md](../docs/step_results/phase-3.md) | DP-4, 시간 예산 | 2.10 |
| D-14 | `.importlinter` 변경이 필요해지면 **P3-1 병합 뒤 한 번**, 사람이 커밋합니다. 필요 여부는 조립을 만든 뒤에 압니다 — Phase 2 에서 미리 적었다가 틀렸습니다(spec 0003 개정 2) | CC, EI-2 | 2.11 |

## 5. 검증 매핑

| 요구사항 | 단위 | 판정 |
| --- | --- | --- |
| R-1 | P3-1 | `api-unit`: 100회 반복 동일 출력 |
| R-2 | P3-1 | `api-unit`: 예산 3배 입력 → 예산 이하 + `ContextReport` 의 제거 기록이 D-7 순서 |
| R-3 | P3-1 | `api-unit` 회귀 + 구조 테스트(직접 조립 0건) |
| R-4 | P3-1 | `api-arch` + 위반 주입 |
| R-5 | P3-2 | `api-integration`: pgvector testcontainer, 적재 → 검색 1위 |
| R-6 | P3-2 | `api-arch`(AR-5·AR-9) + `api-unit`(embed 호출 수 = 청크 수) |
| R-7 | P3-2 | `smoke`: egress 차단에서 적재 → 검색 |
| R-8 | P3-3 | `api-integration`: 표지·출처 확인, system 미혼입 |
| R-9 | P3-3 | `api-integration`: `PUT` 으로 Version 2, 미바인딩 집합 미검색 |
| R-10 | P3-4 | `api-integration`: 카탈로그로 표·인덱스 분리 확인. `api-unit`: `verified: false` |
| R-11 | P3-5 | `api-unit`: 인메모리 `Tracer` 속성. `smoke`: collector 출력 |
| R-12 | P3-2, P3-5 | `.harness/verify.json` 합계 ≤ 600,000 ms |

## 6. 이 spec 이 답하지 않는 것

- Ranking·Reranker·Compression(Context Compiler v1.1).
- Connector 확장·증분 갱신·권한별 검색.
- Memory 의 자동 승격·요약·망각.
- 컨텍스트 최적화 자체 — 이번에는 측정만 합니다.
- 인용 UI·대시보드, `apps/web` 의 화면.

## 개정 이력

| 개정 | 내용 |
| --- | --- |
| 개정 7 | 2026-10-10. **D-13 의 수동 확인을 1회 실행했습니다**(Phase 3 완료 판정). compose 가 고정한 ollama 이미지(`0.34.0`, digest `684d8674…`)에 `nomic-embed-text` 를 올려 `OpenAICompatibleGateway.embed` → `ModelGatewayEmbedder` → pgvector 로 Knowledge 적재·검색과 Memory 쓰기·읽기를 왕복했습니다. 숫자와 한계는 [../docs/step_results/phase-3.md](../docs/step_results/phase-3.md) "D-13 수동 확인" 이 소유합니다. 이 실행으로 **D-3 이 고친 것이 실제 서버에서 성립함**이 처음 확인됐습니다 — 그전까지 임베딩 경로의 증거는 전부 fake 또는 결정적 해시 임베더였습니다. 함께: spec 0002 2.5 에 그 문서가 D-3 으로 개정됐다는 사실을 남겼습니다(spec 0002 개정 9) |
| 개정 6 | 2026-10-10. **2.6 의 트리거를 구체화했습니다** — "Run 이 종결할 때 남길 것이 있으면" 과 "Executor 가 명시적으로 넘긴 것만" 은 구현마다 다르게 읽히고, 다르게 읽히는 것은 테스트할 수 없습니다. P3-4 를 시작하기 전에 주 세션이 `memory_enabled` ∧ `succeeded` ∧ "마지막 assistant 본문 그대로" 로 좁혔고, 구현과 테스트가 그것을 고정했습니다. 실행 중에 나온 해석 하나도 함께 적습니다 — `memory_enabled` 가 **읽기도** 막습니다 |
| 개정 5 | 2026-10-09. **P3-2b 실행이 찾은 구멍 하나와 표기 둘** — (1) 2.4 의 "진행 상태" 가 `control.knowledge_ingestions` 라고만 적고 **누가 쓰는지** 적지 않았습니다. P3-2a 의 GRANT 가 `aether_data` 에 SELECT 만 주므로 worker 는 그 표에 쓸 수 없고, 상태를 api 로 되돌리는 스트림이 구조적으로 필요합니다 — 실행자가 그것을 만들고 근거를 신고했고 받아들였습니다. (2) 2.9 의 `_OVERLAP` 축약을 정식 이름 `AETHER_KNOWLEDGE_CHUNK_OVERLAP_CHARS` 로 고쳤습니다. (3) R-7 의 smoke 시나리오가 P3-3 이후인 이유를 2.9.1 로 적었습니다 |
| 초안 | 2026-10-05. intent 0004 의 열린 질문 6건을 D-1 ~ D-7·D-9 로 고정했습니다. 외부 사실 확인에서 나온 것 둘 — pgvector 이미지에 `pg16` 태그가 있고(D-1), Ollama 의 OpenAI 호환 `/v1/embeddings` 는 **전용 임베딩 모델**을 요구합니다(D-3, 지금 어댑터는 채팅 모델 id 를 보냅니다). spec 0002 2.5 를 D-3 으로 [실질] 개정합니다 |
