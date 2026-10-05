# Plan 0004 — Phase 3: Context Compiler / RAG

| 키 | 값 |
| --- | --- |
| 번호 | 0004 |
| 근거 spec | [../specs/0004-phase-3-context-compiler.md](../specs/0004-phase-3-context-compiler.md) (승인됨 2026-10-05, D-1 ~ D-14) |
| 근거 intent | [../intents/0004-phase-3-context-compiler.md](../intents/0004-phase-3-context-compiler.md) (승인됨 2026-10-05) |
| 작업 단위 | [../intents/mvp-backlog.md](../intents/mvp-backlog.md) P3-1 ~ P3-5 (P3-2 → **2a·2b** 로 분할) |
| 작성일 | 2026-10-05 |
| 상태 | 승인 대기 |
| 승인 | (사람 이름과 날짜. 비어 있으면 구현을 시작하지 않습니다) |

spec 이 정한 요구사항(R-1 ~ R-12)·결정(D-1 ~ D-14)은 반복하지 않습니다. 이 문서는 여섯 단위를 어떤 순서로 하고, 단위마다 어느 파일을 누가 만들며, 무엇으로 판정하는지를 정합니다. 표기 — **A** 에이전트(`implementer`), **M** 주 세션, **H** 사람(보호 파일).

이 plan 이 풀어야 하는 문제는 넷입니다.

1. **깨질 가능성이 가장 큰 것을 가장 먼저 합니다.** pgvector 이미지 교체(D-1)는 Debian/alpine 차이 때문에 init 스크립트·로케일·기존 역할 테스트에 닿습니다(spec C-1). 거기서 깨지면 뒤 단위 전부가 멈추므로 **P3-2a 를 1번**에 둡니다. Phase 1 이 마이그레이션을 앞에 둔 것과 같은 이유입니다.
2. **지금 코드로는 적재가 반드시 실패합니다.** 어댑터가 채팅 모델 id 를 `/embeddings` 로 보냅니다(spec D-3, `openai_compatible.py` 231행). 그 수정을 **P3-2a 범위에 넣습니다** — 적재 파이프라인을 만들기 전에 임베딩이 되는 것을 확인해야 합니다.
3. **순수 로직을 인프라와 분리합니다.** Context Compiler(P3-1)는 DB·네트워크가 없는 조립 규칙이고, 결정성·예산이 그 단위의 전부입니다. pgvector 작업과 섞지 않습니다.
4. **`.importlinter` 예외의 필요 여부는 미리 적지 않습니다.** Phase 2 에서 미리 적었다가 틀렸습니다(spec 0003 개정 2). 조립을 만든 뒤 실측으로 판단하고, 필요하면 **P3-1 병합 뒤 한 번** 사람이 커밋합니다(spec D-14).

## 1. 순서

| Wave | 단위 | 왜 이 자리인가 | 사람 손 |
| --- | --- | --- | --- |
| 1 | **P3-2a** pgvector 교체 · 마이그레이션 0004 · 임베딩 모델 분리 | 가장 위험한 것이 먼저. 여기서 깨지면 뒤가 전부 멈춥니다. 임베딩 호출이 되는 것까지 이 단위에서 확인합니다 | — |
| 2 | **P3-1** Context Compiler v1 | DB 없는 순수 로직. 결정성(R-1)·예산(R-2)·Executor 전환(R-3)·AR-3 발화(R-4) | — |
| — | (경계) | `.importlinter` 예외가 필요하면 한 번 | **H-1**(필요 시) |
| 3 | **P3-2b** 적재 파이프라인 | Connector → Indexer → Embedder → Store. P3-2a 의 표와 확장 위에서 | — |
| 4 | **P3-3** 검색 결과를 Context 에 | Compiler(P3-1)와 Store(P3-2b)가 둘 다 있어야 성립. 바인딩·표지·출처 | — |
| 5 | **P3-4** Memory v1 | Compiler 에 소스 하나를 더하는 일. 저장소 분리가 판정의 핵심 | — |
| 6 | **P3-5** KPI 계측 | 앞의 소스가 모두 있어야 소스별 토큰 수가 의미를 갖습니다 | **H-2**(evaluation, 필요 시) |

P3-2 를 2a·2b 로 쪼갠 것과 P3-2a 를 P3-1 앞에 둔 것이 backlog 번호 순서와 다릅니다. 근거는 1절 문제 1·2 이고, backlog 에 행을 추가하는 것은 **M** 이 이 plan 승인과 같은 커밋에서 합니다.

## 2. 단위별 계획

모든 단위는 **red(실패하는 테스트, 실행해 기록) → green → refactor** 순서입니다. `ModuleNotFoundError` 하나로 여러 단언을 갈음하지 않습니다 — 모듈이 생긴 뒤에도 각 단언이 **자기 이유로** 한 번은 실패하는 것을 보여야 합니다(Phase 2 P2-2b 에서 그 기준을 세웠습니다). 단위마다 브랜치 하나(`p3-2a-pgvector`), PR 하나, 커밋 trailer `Unit: P3-2a`.

### P3-2a pgvector 교체 · 마이그레이션 0004 · 임베딩 모델 분리 (A)

| 항목 | 내용 |
| --- | --- |
| 고치는 것 | `infra/docker/compose.yaml`·`compose.smoke.yaml`·`compose.ci.yaml` 의 PostgreSQL 이미지를 `pgvector/pgvector:pg16`(다이제스트 핀 — **실제 조회로 확인**하고 값을 보고에 적습니다). `infra/docker/postgres/init/01-roles.sh` 가 그 이미지에서 그대로 도는지 확인 |
| 만드는 것 | `apps/api/migrations/versions/0004_*.py` — `CREATE EXTENSION IF NOT EXISTS vector`, spec 2.8 의 네 표(`control.knowledge_sets`·`control.knowledge_ingestions`·`data.knowledge_chunks`·`data.agent_memory`), GRANT. 벡터 열 차원은 `AETHER_EMBED_DIM`(기본 768) |
| 임베딩 분리 | `AETHER_EMBED_MODEL_ID`(기본 `nomic-embed-text`)를 설정에 더하고 `OpenAiCompatibleModelGateway.embed` 가 **그 모델**을 보냅니다(spec D-3). 채팅 경로는 바뀌지 않습니다 |
| 판정 | `api-integration`: 빈 DB 에서 마이그레이션 up/down 왕복, `vector` 확장 존재, 역할 테스트 전부 통과(기존 `test_plane_roles.py` 무회귀 + 새 네 표의 GRANT 범위). `api-unit`: `embed` 가 임베딩 모델 id 를 보내고 채팅은 채팅 모델 id 를 보내는 것(`httpx.MockTransport`) |
| 추가 확인 | compose 로 PG 를 띄워 `select extname from pg_extension` 에 `vector` 가 있는지 손으로 1회. 이미지 크기 변화도 적습니다 |
| 주의 | **여기서 깨지면 멈추고 보고하십시오.** alpine → Debian 전환이 init·로케일·기존 테스트에 닿습니다(spec C-1). 우회(예: 확장 없이 진행)를 만들지 마십시오 |

### P3-1 Context Compiler v1 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `packages/context/src/aether_context/domain/`(소스 종류·예산·`ContextReport`) · `application/ports/inbound/compile_context.py` · `application/ports/outbound/{knowledge_search,memory_reader,embedder,token_counter}.py`(이 단위에서는 Knowledge·Memory 는 **빈 구현을 꽂아** 쓰지 않습니다) · `application/usecases/compile_context.py` · `packages/runtime/.../ports/outbound/context_compiler.py` 와 `adapters/outbound/context_compiler/` |
| 고치는 것 | `packages/runtime/.../application/usecases/execute_run.py` — 메시지 직접 조립을 Compiler 호출로 교체 |
| 판정 | `api-unit`: 같은 입력 100회 동일 출력(R-1). 예산 3배 입력이 예산 이하로 줄고 `ContextReport` 의 제거 기록이 **D-7 순서**(R-2). Phase 1·2 시나리오 회귀 통과 + 구조 테스트로 직접 조립 0건(R-3). `api-arch`: AR-3 위반 주입이 발화(R-4) |
| 주의 | 결정성을 깨는 것은 대개 집합·딕셔너리 순회입니다. 정렬된 키만 씁니다(spec D-12). 토큰 근사는 **과대 추정 방향**이어야 합니다(spec D-6·C-2) — 그 방향을 테스트로 고정하십시오 |

### H-1 (경계, 필요 시) `.importlinter` — 사람이 커밋

조립이 `aether_context.adapters` 를 보게 되어 계약이 깨지면, 그때만 예외 한 줄을 제안합니다. **필요 여부를 미리 단정하지 않습니다**(spec D-14). 필요하면 후보를 scratchpad 로 넘기고 `lint-imports` 통과 기록을 함께 올립니다.

### P3-2b 적재 파이프라인 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `aether_context` 의 `Connector`(Filesystem)·`Indexer`(문자 1000/겹침 200)·`KnowledgeStore` 포트와 pgvector 어댑터 · 적재 유스케이스 · api 의 적재 선언 경로와 worker 의 실행 경로(spec D-4, `control.runs` 와 같은 모양) |
| 판정 | `api-integration`: pgvector testcontainer 에 문서 3개 적재 → 고유 문장으로 검색해 그 청크가 1위(R-5). `api-unit`: fake gateway 의 `embed` 호출 수 = 청크 수(R-6), 청크에 모델 id·차원이 저장됨(D-9). `api-arch`: `aether_context` 가 `httpx`·벤더 SDK 를 import 하지 않음 |
| 주의 | 임베딩은 `Embedder` 포트를 지납니다 — `aether_context` 가 `aether_runtime` 을 import 하지 않습니다(AR-3). 조립은 worker 의 `main` |

### P3-3 검색 결과를 Context 에 (A, 표는 M)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | Compiler 의 Knowledge 소스 · `AgentDefinition.knowledge`(집합 이름 목록)·`context_budget_tokens`·`knowledge_top_k`(spec D-5) · 검색 결과 블록(표지 `trust: untrusted` + 출처) |
| 고치는 것 | `packages/sdk/openapi.json` 과 생성 타입(**추가 변경만**, 경로 0개) |
| 판정 | `api-integration`: 적재된 사실을 묻는 Run 이 출처와 함께 답하고 블록이 system 에 섞이지 않음(R-8). `PUT` 으로 `knowledge` 만 바꿔 Version 2·Version 1 불변, 미바인딩 집합 미검색(R-9) |
| M | `docs/api.md` 의 `AgentDefinition` 표에 세 필드 — 실행자는 행 초안만 보고에 |

### P3-4 Memory v1 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `packages/memory` 의 도메인·포트·PG 어댑터 · Compiler 의 Memory 소스(표지 `verified: false`) · Run 종결 시 Executor 가 **명시적으로 넘긴 것만** 저장 |
| 판정 | `api-integration`: `data.agent_memory` 와 `data.knowledge_chunks` 의 표·인덱스가 겹치지 않음을 **DB 카탈로그로** 확인(R-10). `api-unit`: Memory 블록의 표지가 Knowledge 와 다르고, 예산 초과 시 **가장 먼저** 빠짐(D-7) |
| 주의 | 두 소스를 한 쿼리로 합치지 마십시오. 자동 요약·승격은 범위 밖입니다 |

### P3-5 KPI 계측 (A, 문서는 M)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `ContextReport` 의 숫자를 span 속성으로(`context.tokens.*`·`context.budget`·`context.dropped.*`) · 집계 쿼리 예시 |
| 판정 | `api-unit`: 인메모리 `Tracer` 에서 속성 확인(R-11). `smoke`: collector 출력에 그 속성이 나타남. `.harness/verify.json` 합계 ≤ 600,000 ms(R-12) |
| 기록 | `smoke`·`api-integration` 실측과 pgvector 교체 전후의 이미지 크기를 `improvement-log/` 1건으로 |
| M | 집계 쿼리와 "이 숫자를 단일 목표로 주지 않는다"(EI-3 제품판)를 `docs/` 에 한 절로 |

## 3. 사람 손

| 순간 | 언제 | 사람이 하는 일 |
| --- | --- | --- |
| **H-1**(필요 시) | P3-1 병합 뒤 | `.importlinter` 예외 한 줄. 필요 여부는 P3-1 의 실측이 정합니다 |
| **H-2**(필요 시) | P3-5 | `evaluation/` 문구 — Context 예산을 겨냥한 task 를 더할지는 **이번 Phase 에서 결정하지 않습니다**(intent Non-goals). 더하지 않으면 사람 손 없음 |
| 수동 확인 | P3-2b 또는 P3-3 | 로컬 LLM 으로 실제 임베딩·검색 1회(spec D-13). 모델 다운로드를 CI 에 넣지 않습니다 |

`harness.config` 와 CI 워크플로는 바뀌지 않습니다(단계 수 불변, spec 2.10).

## 4. 판정 절차

`TESTCONTAINERS_RYUK_DISABLED=true ./harness/scripts/verify.sh` 하나가 판정입니다(18단계). 문서·기록만 고친 커밋은 `--changed` 로 범위를 좁힐 수 있습니다(2026-10-04-001).

**단위별 추가 확인**(verify 가 아직 못 보는 것 — 보고에 "손으로 실행", 실행하지 않았으면 "미측정"):

| 단위 | 추가 확인 |
| --- | --- |
| P3-2a | compose 로 PG 를 띄워 `vector` 확장 존재 확인. 이미지 크기 변화 |
| P3-1 | 결정성 테스트가 **정렬 제거**로 실제 깨지는지 1회(그 뒤 되돌림) |
| P3-2b | 로컬 LLM 으로 실제 임베딩 1회(되면), 안 되면 사유 |
| P3-3 | compose 에서 적재 → 질문 Run → 출처 포함 응답 1회 |
| P3-4 | `\d+` 로 두 표의 인덱스 목록을 눈으로 1회 |
| P3-5 | collector 출력에서 `context.tokens.*` 1회 |

**보고에 반드시**: `red 증거`(각 단언이 자기 이유로 실패한 기록), 판정 명령 exit 표, 미측정, spec/plan 과의 불일치, `docs/` 에 옮길 표 초안.

## 5. 예산과 중단

[../AGENTS.md](../AGENTS.md) Loop 와 `harness/rules/loop-budget.rule.md` 를 그대로 씁니다. 다른 것만 적습니다.

| 항목 | 값 |
| --- | --- |
| 쪼개기 | P3-2 는 **처음부터** 2a·2b. 포트에 메서드를 더하는 변경이 들어가면 그 fake 가 몇 곳인지 먼저 세십시오(2026-09-28-001 — P2-6 에서 39개 테스트가 깨졌습니다) |
| 위임 기준 | 단일 파일·기계적 변경은 **주 세션이 직접** 합니다. 위임은 여러 파일에 걸친 기능 단위와 red→green 이 실제로 여러 번 도는 일에만(2026-10-04 결정) |
| Docker | pgvector 이미지로 교체되므로 기존 볼륨과 **호환되지 않을 수 있습니다**. 격리 프로젝트 이름을 반드시 쓰고, 개발 볼륨을 지우는 명령을 쓰지 마십시오 |
| verify 동시 실행 | 금지됩니다(락이 막습니다, 2026-10-03-001). 위임 세션이 돌리는 동안 주 세션은 돌리지 않습니다 |
| 시간 예산 | 합계 10분. 넘으면 **선택 실패**로 집계되고 사람이 판단합니다 |

## 6. Phase 완료

backlog 의 Phase 3 완료 판정 + spec 0004 의 R-1 ~ R-12 전부가 통과하고 여섯 단위가 병합되면 완료입니다. 그때 **M** 이 하는 일: intent 0004 의 상태를 `완료` 로, [../intents/intent.md](../intents/intent.md) 의 활성 intent 를 다음 건으로, backlog 의 Phase 3 상태 행, [../docs/roadmap.md](../docs/roadmap.md) 의 Phase 행. 그리고 spec 0002 의 개정 이력에 D-3(임베딩 모델 분리)을 적습니다.

## 관련 문서

- [../specs/0004-phase-3-context-compiler.md](../specs/0004-phase-3-context-compiler.md) — 요구사항·결정
- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — 단위의 범위
- [../docs/architecture.md](../docs/architecture.md) — AR-3·AR-5·AR-9·AR-12
- [../docs/domain.md](../docs/domain.md) — `Context`·`Knowledge`·`Memory` 와 그 분리 규칙
- [../AGENTS.md](../AGENTS.md) — Loop, Trust
