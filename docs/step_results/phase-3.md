# Phase 3 — Context Compiler / RAG (진행 중)

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

## 이 Phase 에서 하네스 자신에게 생긴 일

제품과 별개로 하네스가 두 번 바뀌었습니다. 둘 다 보호 파일 변경이고 사람이 병합했습니다.

| 무엇 | 왜 | 근거 |
| --- | --- | --- |
| `verify.sh` 의 단일 실행 락, 원자적 `verify.json` 쓰기, 시간 예산 자기 판정, 범위 지문(`--changed`) | 동시 실행이 `verify.json` 을 깨 **없는 실패를 보고**했고, 문서만 고친 커밋이 매번 440초를 썼습니다 | 2026-10-03-001, 2026-10-04-001 |
| `api-unit` 한 단계를 `api-unit` · `harness-arch` · `harness-scripts` 셋으로 쪼갬 | 그 한 단계가 합계의 절반이었고 **그 안에서 무엇이 느린지 보이지 않았습니다**. 쪼개 보니 제품 테스트 전부가 23초이고 하네스 자신의 스크립트 테스트가 261초였습니다 | 2026-10-06-002 (PR #119) |

예산을 올리는 쪽을 고르지 않은 이유가 중요합니다 — 올렸다면 "느린 것은 제품이 아니라 하네스 자신" 이라는 사실이 그대로 가려졌을 것입니다(EI-2: 임계값은 사람이 소유합니다).

## 남긴 것

- **사람 몫**: 로컬 LLM 으로 실제 임베딩·검색 1회 수동 확인(spec D-13). 모델 다운로드를 CI 에 넣지 않습니다. Knowledge 적재·검색 시나리오를 `smoke` 에 넣는 시점은 P3-3 뒤로 미뤘습니다(spec 2.9.1).
- **새 verify 단계를 더하지 않았습니다.** 이 디렉터리를 강제하는 검사(`tests/scripts/test_step_result_pages.py`)는 기존 `quality` 계층 단계에서 함께 돕니다. 단계를 늘리면 `harness.config`(보호 파일)가 바뀌고 시간 예산도 다시 판단해야 하는데, 지금 예산의 여유는 2026-10-09-001 이 다루는 중입니다 — 하네스 변경은 한 번에 하나씩입니다([../../harness/rules/harness-change-control.rule.md](../../harness/rules/harness-change-control.rule.md)).
- 열린 후보: 2026-10-06-001(스위트 순서 의존 플레이키), 2026-10-09-001(`tests/scripts` 의 번들 복사 비용), 2026-10-09-002(임베딩 배치 부재), 2026-10-10-001(한 Run 안에서 같은 질의를 여러 번 검색), 2026-10-10-002(pgvector 이미지 크기가 어느 단계에서도 기록되지 않음).
