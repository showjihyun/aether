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

## 이 Phase 에서 하네스 자신에게 생긴 일

제품과 별개로 하네스가 두 번 바뀌었습니다. 둘 다 보호 파일 변경이고 사람이 병합했습니다.

| 무엇 | 왜 | 근거 |
| --- | --- | --- |
| `verify.sh` 의 단일 실행 락, 원자적 `verify.json` 쓰기, 시간 예산 자기 판정, 범위 지문(`--changed`) | 동시 실행이 `verify.json` 을 깨 **없는 실패를 보고**했고, 문서만 고친 커밋이 매번 440초를 썼습니다 | 2026-10-03-001, 2026-10-04-001 |
| `api-unit` 한 단계를 `api-unit` · `harness-arch` · `harness-scripts` 셋으로 쪼갬 | 그 한 단계가 합계의 절반이었고 **그 안에서 무엇이 느린지 보이지 않았습니다**. 쪼개 보니 제품 테스트 전부가 23초이고 하네스 자신의 스크립트 테스트가 261초였습니다 | 2026-10-06-002 (PR #119) |

예산을 올리는 쪽을 고르지 않은 이유가 중요합니다 — 올렸다면 "느린 것은 제품이 아니라 하네스 자신" 이라는 사실이 그대로 가려졌을 것입니다(EI-2: 임계값은 사람이 소유합니다).

## 남긴 것

- **사람 몫 중 끝난 것**: 로컬 LLM 임베딩 왕복 1회(spec D-13) — 위 "D-13 수동 확인".
- **사람 몫 중 남은 것**: 적재 → 질문 Run → **출처 포함 응답** 1회(plan 의 추가 확인). 임베딩은 확인했지만 채팅 모델은 돌리지 않았으므로 응답 쪽은 미확인입니다. Knowledge 적재·검색 시나리오를 `smoke` 에 넣는 시점도 미결입니다(spec 2.9.1) — 지금 `smoke` 는 95초이고 예산 여유가 2026-10-09-001 에 걸려 있습니다.
- **결정하지 않은 것**: Context 토큰 수를 겨냥한 평가 task 를 더할지(plan 의 H-2)는 intent Non-goals 에 따라 이번 Phase 에서 결정하지 않았습니다.
- **새 verify 단계를 더하지 않았습니다.** 이 디렉터리를 강제하는 검사(`tests/scripts/test_step_result_pages.py`)는 기존 `quality` 계층 단계에서 함께 돕니다. 단계를 늘리면 `harness.config`(보호 파일)가 바뀌고 시간 예산도 다시 판단해야 하는데, 지금 예산의 여유는 2026-10-09-001 이 다루는 중입니다 — 하네스 변경은 한 번에 하나씩입니다([../../harness/rules/harness-change-control.rule.md](../../harness/rules/harness-change-control.rule.md)).
- 열린 후보: 2026-10-06-001(스위트 순서 의존 플레이키), 2026-10-09-001(`tests/scripts` 의 번들 복사 비용), 2026-10-09-002(임베딩 배치 부재), 2026-10-10-001(한 Run 안에서 같은 질의를 여러 번 검색), 2026-10-10-002(pgvector 이미지 크기가 어느 단계에서도 기록되지 않음).
