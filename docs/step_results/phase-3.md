# Phase 3 — Context Compiler / RAG (완료 2026-10-10)

intent [0004](../../intents/0004-phase-3-context-compiler.md) · spec [0004](../../specs/0004-phase-3-context-compiler.md) · plan [0004](../../plans/0004-phase-3-context-compiler.md).

이 Phase 부터는 **단위당 한 장**입니다. 이 페이지는 입구이고 내용은 단위 페이지가 소유합니다.

그림: [diagrams/phase-3.html](diagrams/phase-3.html)

| 단위 | 무엇 | 페이지 | PR |
| --- | --- | --- | --- |
| P3-2a | pgvector 교체 · 마이그레이션 0004 · 임베딩 모델 분리 | [p3-2a.md](p3-2a.md) | #117 |
| P3-1 | Context Compiler v1 (예산과 조립 규칙) | [p3-1.md](p3-1.md) | #118 |
| P3-2b | Knowledge 적재 파이프라인 | [p3-2b.md](p3-2b.md) | #120 |
| P3-3 | 검색 결과를 Context 에 | [p3-3.md](p3-3.md) | #133 |
| P3-4 | Memory v1 (Knowledge 와 분리) | [p3-4.md](p3-4.md) | #134 |
| P3-5 | KPI 계측 (Task Success / Context Token) | [p3-5.md](p3-5.md) | #135 |

plan 이 정한 순서는 P3-2a → P3-1 → P3-2b → P3-3 → P3-4 → P3-5 입니다. **가장 깨질 가능성이 큰 것(PostgreSQL 이미지 교체)을 먼저** 했습니다.

## 완료 판정

intent 0004 의 Phase 완료 조건은 "모델 호출마다 Compiler 가 예산 안에서 다섯 소스를 조립하고, Knowledge 는 로컬 Vector DB 에서 검색되며, Memory 는 Knowledge 와 다른 저장소에 검증 전 표시를 달고, Run 마다 컨텍스트 토큰 수가 트레이스에 남는다" 입니다. 단위 여섯이 전부 병합됐고(위 표), 요구사항 R-1 ~ R-12 는 `verify` 의 `api-unit` · `api-integration` · `api-arch` · `smoke` 단계가 판정합니다.

사람 몫 하나가 남아 있었고 아래에서 실행했습니다. 남은 미결은 "남긴 것" 이 소유합니다.

## D-13 수동 확인 (2026-10-10)

spec 0004 D-13 은 "로컬 LLM 으로 실제 임베딩 확인 1회" 를 CI 밖 수동 확인으로 남겨 뒀습니다. 그전까지 임베딩 경로의 증거는 **전부 fake 또는 결정적 해시 임베더**였습니다 — 즉 "우리 어댑터가 실제 임베딩 서버와 말이 통하는가" 는 단위 다섯이 끝날 때까지 한 번도 확인되지 않았습니다. 특히 D-3(임베딩 모델을 채팅 모델과 분리)이 고친 것이 실제 서버에서 성립하는지는 이 확인에만 달려 있었습니다.

| 항목 | 값 |
| --- | --- |
| 서버 | `ollama/ollama:0.34.0`, digest `684d8674b4315fa18f4f0e973a118ec2652ed96f67563277839985175858e0ba` — `infra/docker/compose.yaml` 의 `llm` 프로파일이 고정한 **그** 이미지. `/api/version` 이 `0.34.0` 로 응답 |
| 모델 | `nomic-embed-text` (`AETHER_EMBED_MODEL_ID` 기본값) |
| 경로 | `OpenAICompatibleGateway.embed`(httpx → `/v1/embeddings`) → `ModelGatewayEmbedder` → `IngestKnowledgeUseCase` / `PostgresKnowledgeSearch` / `WriteAgentMemoryUseCase` / `ReadAgentMemoryUseCase` → pgvector(`pgvector/pgvector:pg16`, `tests/support/pg.py` 와 같은 digest, alembic `head`) |
| 차원 | 응답 768 · `AETHER_EMBED_DIM` 768 · 저장된 열 `vector_dims` 768 — 셋이 일치 |

**Knowledge.** 서로 무관한 세 문서(quokka · sourdough · Mount Fuji)를 디렉터리로 적재하고, **본문과 단어가 겹치지 않는** 질문 셋으로 검색했습니다. 어휘 겹침으로는 맞출 수 없게 고른 질문입니다 — 통합 테스트의 해시 임베더는 이 질문들에서 맞출 수 없습니다.

| 질문 | 1위 | 1위 거리 | 2위 거리 |
| --- | --- | --- | --- |
| "Which animal lives near Perth in Australia?" | `quokka.txt` | 0.2631 | 0.6167 |
| "How does baking dough get its rise?" | `sourdough.txt` | 0.3096 | 0.6005 |
| "When did the Japanese volcano erupt?" | `fuji.txt` | 0.2097 | 0.5552 |

셋 다 1위가 정답이고 2위와의 간격이 두 배 이상입니다. 같은 스크립트를 두 번 돌려 거리값이 소수 네 자리까지 같았습니다 — 임베딩이 결정적입니다(R-1 의 전제).

**Memory.** 같은 임베더로 기억 둘("metric units and a 24-hour clock", "air-gapped on-premise cluster")을 쓰고 `"Should I write times as 3 PM or 15:00?"` 으로 읽었습니다. 1위가 시각 표기 쪽(거리 0.3707), 2위가 배포 쪽(0.6674)입니다. `data.agent_memory` 의 두 행 모두 `embed_model_id = nomic-embed-text`, `embed_dim = 768`, 저장된 벡터 차원 768.

확인하지 않은 것을 적어 둡니다.

- **이 확인은 사람이 아니라 에이전트가 돌렸습니다.** spec 은 "사람의 수동 확인" 이라고 적었고, 실제로는 사용자의 지시로 주 세션이 실행했습니다. 뜻은 "CI 밖에서 1회" 이고 그것은 충족했지만, 문구와 실행자가 다른 것은 그대로 남깁니다.
- **채팅 모델은 돌리지 않았습니다.** `qwen3.8:27b`(약 18 GB, VRAM 18 GB 이상)은 이 확인의 범위가 아닙니다 — D-13 은 임베딩에 대한 것입니다. 그래서 "적재 → 질문 Run → 출처 포함 응답" 의 **응답** 부분은 여전히 미확인입니다(plan 의 추가 확인).
- **egress 차단 아래에서 돌리지 않았습니다.** 모델을 먼저 당겨와야 했으므로 이 실행은 오프라인이 아닙니다. R-7 의 오프라인 판정은 `smoke` 가 fake 어댑터로 합니다.
- **compose 네트워크가 아니라 호스트에서 접속했습니다.** 고정 이미지를 그대로 쓰되 포트를 `127.0.0.1` 로 열어 붙였습니다. compose 안의 `http://llm:11434` 경로는 이 확인이 지나지 않았습니다.
- 스크립트는 저장소에 넣지 않았습니다 — CI 에 들어가지 않는 일회성 확인이고(D-13), 저장소에 두면 다음 사람이 verify 단계로 착각할 수 있습니다.

## P3-3 수동 확인: 출처 포함 응답 (2026-10-12)

plan 의 P3-3 추가 확인("compose 에서 적재 → 질문 Run → 출처 포함 응답 1회")이 Phase 3 완료 시점에 남아 있던 **유일한 실행형 사람 몫**이었습니다. D-13(2026-10-10)은 임베딩만 확인했으므로 "응답" 쪽은 미확인이었습니다 — 즉 "실제 채팅 모델이 우리가 조립한 Context 를 받고 **출처를 달아** 답하는가" 는 Phase 3 이 끝날 때까지 한 번도 확인되지 않았습니다. `api-integration` 의 R-8 판정은 fake 모델이 받은 요청의 **모양**만 봅니다.

| 항목 | 값 |
| --- | --- |
| 스택 | `docker compose -p aether-p33` + `compose.yaml` + `compose.smoke.yaml` — postgres · redis · migrate · otel-collector · api · worker 전부 healthy. 개발 스택과 `aether-smoke`(verify 가 쓰는 프로젝트) 둘 다 건드리지 않았습니다 |
| 채팅 모델 | `qwen3:8b` (`AETHER_MODEL_ADAPTER=openai_compatible`) |
| 임베딩 모델 | `nomic-embed-text`, `AETHER_EMBED_DIM=768` |
| 모델 서버 | 호스트의 ollama `0.40.2`, GPU. 컨테이너에서 `http://host.docker.internal:11434/v1` 로 접속 |
| 적재 | `POST /knowledge-sets` → `POST /knowledge-sets/{id}/ingestions` (`source=/tmp/p33-docs`, worker 컨테이너 안) → `GET /knowledge-ingestions/{id}` 가 `succeeded`. 문서 3개, 16.1초 |
| 청크 | `data.knowledge_chunks` 3행 — `alloy-spec.txt`·`depot-rules.txt`·`ferry-schedule.txt` 각 chunk 0, 전부 `embed_model_id=nomic-embed-text`, `embed_dim=768`, 저장된 벡터 차원 768 |

문서의 사실은 **전부 지어낸 것**입니다. 모델이 사전 지식으로 맞출 수 없어야 "적재한 문서를 읽고 답했다" 가 성립합니다.

**질문과 응답.** Agent 는 `knowledge` 에 그 집합을 바인딩하고 `knowledge_top_k=3`, `memory_enabled=true` 로 만들었습니다. system prompt 는 "모든 사실 주장은 블록의 `source=` 값을 그대로 적어라" 입니다.

> **질문** We are about to machine a batch of TR-88 hinges. How many hours of heat treatment does the material need first, and which document says so?
>
> **응답** The TR-88 material requires six hours of annealing before machining, as specified in the **alloy-spec.txt** document. This heat treatment prevents brittleness below freezing.

사실("six hours")과 출처(`alloy-spec.txt`) 둘 다 맞습니다.

**출처가 블록에서 왔다는 근거.** 문자열 `alloy-spec.txt` 는 **문서 본문에도 질문에도 없습니다** — 본문은 `Alloy TR-88 is a tungsten-bearing steel…` 로 시작하고 자기 파일명을 담지 않습니다. 모델이 그 문자열을 얻을 수 있는 곳은 `render_knowledge_block` 이 붙이는 `[knowledge source=alloy-spec.txt chunk=0 trust=untrusted]` 의 `source=` 속성 하나뿐입니다. 그래서 이 응답은 "블록이 출처를 달고 들어갔고 모델이 그것을 읽었다" 의 간접 증거가 됩니다.

**Compiler 를 지났다는 근거.** collector 출력(`infra/docker/out/otel-p33/spans.jsonl`)의 `model.complete` span:

| 속성 | 1차(위 질문) | 2차(아래 반대 확인) |
| --- | --- | --- |
| `context.budget` | 8192 | 8192 |
| `context.tokens.system` | 85 | 85 |
| `context.tokens.conversation` | 35 | 23 |
| `context.tokens.knowledge` | **200** | **200** |
| `context.tokens.memory` | (없음) | **71** |
| `context.tokens.total` | 320 | 379 |

1차에 `memory` 가 없는 것이 맞습니다 — Memory 는 종결 **뒤에** 쓰입니다. 2차의 71 토큰은 1차의 응답이 기억으로 넘어온 것이고, 이것으로 **P3-4 의 Memory 왕복도 실제 모델에서 처음 확인**됐습니다(그전 증거는 전부 결정적 해시 임베더였습니다).

**반대 확인.** 같은 Agent·같은 Knowledge 로, 문서가 답하지 않는 질문을 던졌습니다.

> **질문** What is the melting point of alloy TR-88 in degrees Celsius, and which document states it?
>
> **응답** The melting point of alloy TR-88 is not specified in any of the provided documents. The knowledge blocks only describe its composition, annealing requirements, and properties related to brittleness, but none mention its melting point.

이것이 중요한 이유: 이 Run 도 `context.tokens.knowledge = 200` 입니다. 검색이 **됐는데도** 없다고 답했으므로, "모르겠다" 가 검색 실패의 결과가 아닙니다. 그리고 블록에 실제로 있는 것(조성·어닐링·취성)을 열거했으므로 인용 형식을 흉내 낸 것도 아닙니다.

**응답 본문을 어디서 읽었는가 — 다음 사람을 위해.** 제품은 모델의 응답 본문을 **어느 API 로도 내지 않습니다.** `model.completed` 이벤트는 `finish_reason`·`usage` 만 담고, `model.delta` 는 2.7 의 예약이라 Phase 1 은 발생시키지 않으며, trace 속성에는 본문을 넣지 않습니다(D-11). 그래서 이 확인은 `memory_enabled=true` 로 켜고 `data.agent_memory.content` 를 읽었습니다 — 종결이 확정된 뒤 마지막 assistant 본문을 그대로 남기는 경로입니다(`execute_run.py` 의 `_remember`). 같은 확인을 다시 하려면 이 경로를 쓰십시오.

확인하지 않은 것을 적어 둡니다.

- **배포 기본 모델로 돌리지 않았습니다.** `AETHER_MODEL_ID` 의 기본값은 `qwen3.8:27b` 이고, 레지스트리 매니페스트로 확인한 크기는 **17.7 GB**(레이어 4개)입니다. 이 기계는 VRAM 12 GB(RTX 4070 SUPER)이고 실행 시점의 여유 RAM 이 5.6 GB 였습니다 — GPU 에도 CPU 에도 올라가지 않습니다. 그래서 같은 계열의 `qwen3:8b` 로 돌렸습니다. 27B 가 더 잘 답할 것인지는 이 확인이 말하지 않습니다.
- **compose 가 고정한 ollama 이미지를 쓰지 않았습니다.** `llm` 서비스는 GPU 예약이 없어 CPU 전용이고, 위의 RAM 여유로는 모델을 올릴 수 없었습니다. 그래서 호스트의 ollama(`0.40.2`, GPU)를 썼습니다. 고정 이미지(`0.34.0`)는 D-13 이 임베딩으로 확인했고, `http://llm:11434` 의 **네트워크 내부 경로**는 이번에도 지나지 않았습니다.
- **프롬프트를 직접 보지 못했습니다.** 본문이 어디에도 안 나가므로(D-11) "검색 결과가 system 메시지에 섞이지 않았다"(R-8 의 나머지 절반)는 여전히 `api-integration` 의 fake 모델 판정이 소유합니다. 위의 `source=` 논증은 블록이 출처를 달았다는 것까지만 보입니다.
- **egress 차단 아래에서 돌리지 않았습니다.** 모델이 이미 호스트에 있었으므로 이 실행은 네트워크를 쓰지 않았지만, 오프라인 판정(R-7)은 `smoke` 가 fake 어댑터로 합니다.
- **모델 하나, 질문 둘입니다.** 벤치마크가 아닙니다. "한 번은 된다" 를 보인 것이고, spec 이 요구한 것도 1회입니다.
- 스크립트는 저장소에 넣지 않았습니다 — CI 에 들어가지 않는 일회성 확인이고, 저장소에 두면 다음 사람이 verify 단계로 착각할 수 있습니다(D-13 과 같은 이유).

## 이 Phase 에서 하네스 자신에게 생긴 일

제품과 별개로 하네스가 두 번 바뀌었습니다. 둘 다 보호 파일 변경이고 사람이 병합했습니다.

| 무엇 | 왜 | 근거 |
| --- | --- | --- |
| `verify.sh` 의 단일 실행 락, 원자적 `verify.json` 쓰기, 시간 예산 자기 판정, 범위 지문(`--changed`) | 동시 실행이 `verify.json` 을 깨 **없는 실패를 보고**했고, 문서만 고친 커밋이 매번 440초를 썼습니다 | 2026-10-03-001, 2026-10-04-001 |
| `api-unit` 한 단계를 `api-unit` · `harness-arch` · `harness-scripts` 셋으로 쪼갬 | 그 한 단계가 합계의 절반이었고 **그 안에서 무엇이 느린지 보이지 않았습니다**. 쪼개 보니 제품 테스트 전부가 23초이고 하네스 자신의 스크립트 테스트가 261초였습니다 | 2026-10-06-002 (PR #119) |

예산을 올리는 쪽을 고르지 않은 이유가 중요합니다 — 올렸다면 "느린 것은 제품이 아니라 하네스 자신" 이라는 사실이 그대로 가려졌을 것입니다(EI-2: 임계값은 사람이 소유합니다).

## 남긴 것

- **사람 몫 중 끝난 것**: 로컬 LLM 임베딩 왕복 1회(spec D-13) — 위 "D-13 수동 확인". 적재 → 질문 Run → **출처 포함 응답** 1회(plan 의 P3-3 추가 확인) — 위 "P3-3 수동 확인"(2026-10-12). 이 둘로 **실행형 사람 몫은 모두 끝났습니다.**
- **남은 것은 결정뿐입니다**: Knowledge 적재·검색 시나리오를 `smoke` 에 넣는 시점이 미결입니다(spec 2.9.1). 2026-10-11 의 계층 분리(improvement-log 2026-10-11-003)로 `smoke` 는 로컬 기본에서 빠지고 CI 에서만 도므로, 이 결정의 비용은 "로컬 전량이 느려진다" 가 아니라 "CI 가 길어진다" 로 바뀌었습니다.
- **결정하지 않은 것**: Context 토큰 수를 겨냥한 평가 task 를 더할지(plan 의 H-2)는 intent Non-goals 에 따라 이번 Phase 에서 결정하지 않았습니다.
- **새 verify 단계를 더하지 않았습니다.** 이 디렉터리를 강제하는 검사(`tests/scripts/test_step_result_pages.py`)는 기존 `quality` 계층 단계에서 함께 돕니다. 단계를 늘리면 `harness.config`(보호 파일)가 바뀌고 시간 예산도 다시 판단해야 하는데, 지금 예산의 여유는 2026-10-09-001 이 다루는 중입니다 — 하네스 변경은 한 번에 하나씩입니다([../../harness/rules/harness-change-control.rule.md](../../harness/rules/harness-change-control.rule.md)).
- 열린 후보: 2026-10-06-001(스위트 순서 의존 플레이키), 2026-10-09-001(`tests/scripts` 의 번들 복사 비용), 2026-10-09-002(임베딩 배치 부재), 2026-10-10-001(한 Run 안에서 같은 질의를 여러 번 검색), 2026-10-10-002(pgvector 이미지 크기가 어느 단계에서도 기록되지 않음).
