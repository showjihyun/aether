# aether 문서 지도

이 디렉터리는 aether 를 계획하거나 편집하기 전에 읽는 문서를 담습니다. 진입점 지침은 [../AGENTS.md](../AGENTS.md) 가 소유하고, 여기에는 그 지침이 가리키는 실제 지식이 있습니다. 진입점 문서에 지식을 쌓지 않고 여기로 밀어내는 이유는 [../harness/rules/context-hygiene.rule.md](../harness/rules/context-hygiene.rule.md) 에 있습니다.

| 문서 | 무엇에 답하는가 | 언제 읽는가 |
| --- | --- | --- |
| [architecture.md](architecture.md) | 계층이 무엇이고 의존 방향이 어디로 흐르는가 | 코드를 추가·이동하기 전 |
| [domain.md](domain.md) | Agent, Run, Tool, Context 가 이 제품에서 정확히 무엇을 뜻하는가 | 이름을 붙이거나 스키마를 정하기 전 |
| [roadmap.md](roadmap.md) | 지금이 어느 Phase 이고 다음에 무엇이 오는가 | 범위를 정하기 전 |
| [../intents/intent.md](../intents/intent.md) | 이번 작업이 무엇을 왜 하는가 (활성 intent, intent → spec → plan) | 구현을 시작하기 전 |

## 아직 없는 문서

다음 문서는 해당 Phase 가 시작될 때 만듭니다. 미리 만들어 두면 코드보다 먼저 낡습니다.

| 문서 | 만드는 시점 |
| --- | --- |
| `data-model.md` | Phase 0 에서 PostgreSQL 스키마가 확정될 때 |
| `api.md` | Phase 1 에서 `POST /agents/{id}/run` 계약이 고정될 때 |
| `security.md` | Phase 8 Trust Layer 착수 시. 그 전까지는 [../AGENTS.md](../AGENTS.md) 의 Trust 절이 유일한 규범입니다 |
| `deployment.md` | Phase 11 Air-Gapped Edition 착수 시 |
