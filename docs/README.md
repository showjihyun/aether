# aether 문서 지도

이 디렉터리는 aether 를 계획하거나 편집하기 전에 읽는 문서를 담습니다. 진입점 지침은 [../AGENTS.md](../AGENTS.md) 가 소유하고, 여기에는 그 지침이 가리키는 실제 지식이 있습니다. 진입점 문서에 지식을 쌓지 않고 여기로 밀어내는 이유는 [../harness/rules/context-hygiene.rule.md](../harness/rules/context-hygiene.rule.md) 에 있습니다.

| 문서 | 무엇에 답하는가 | 언제 읽는가 |
| --- | --- | --- |
| [architecture.md](architecture.md) | 계층이 무엇이고 의존 방향이 어디로 흐르는가 | 코드를 추가·이동하기 전 |
| [domain.md](domain.md) | Agent, Run, Tool, Context 가 이 제품에서 정확히 무엇을 뜻하는가 | 이름을 붙이거나 스키마를 정하기 전 |
| [data-model.md](data-model.md) | PostgreSQL 스키마·역할·테이블·열·제약·트리거의 열 단위 정본이 무엇인가 | 마이그레이션을 고치거나 저장소 접근 코드를 쓰기 전 |
| [api.md](api.md) | `apps/api` 의 HTTP 계약과 Plane 사이 스트림 계약의 읽기용 요약(정본은 `openapi.json`·spec) | 경로·요청·응답·오류 코드를 부르거나 바꾸기 전 |
| [roadmap.md](roadmap.md) | 지금이 어느 Phase 이고 다음에 무엇이 오는가 | 범위를 정하기 전 |
| [../intents/intent.md](../intents/intent.md) | 이번 작업이 무엇을 왜 하는가 (활성 intent, intent → spec → plan) | 구현을 시작하기 전 |
| [../DESIGN.md](../DESIGN.md) | `apps/web` 의 표현 규약 — 결정은 shadcn/ui 기본값, 토큰만, 도메인 → 표현 표 | 화면을 만들거나 고치기 전 |

## 아직 없는 문서

다음 문서는 해당 Phase 가 시작될 때 만듭니다. 미리 만들어 두면 코드보다 먼저 낡습니다.

| 문서 | 만드는 시점 |
| --- | --- |
| `security.md` | Phase 8 Trust Layer 착수 시. 그 전까지는 [../AGENTS.md](../AGENTS.md) 의 Trust 절이 유일한 규범입니다 |
| `deployment.md` | Phase 11 Air-Gapped Edition 착수 시 |
