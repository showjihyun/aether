# aether 아키텍처

이 문서는 코드를 추가하거나 옮기기 전에 읽습니다. 구조를 추측으로 재구성하지 않습니다. 근거가 되는 제품 정의는 [roadmap.md](roadmap.md) 가 가리키는 원본 로드맵이며, 이 문서는 그중 **에이전트가 편집 판단에 실제로 쓰는 부분만** 옮겨 적은 것입니다.

## 1. 한 줄 정의

aether 는 Cloud / Private Cloud / On-Premise / Air-Gapped / Edge 에서 **같은 AI Runtime** 을 실행하는 Open Hybrid Enterprise AI OS 입니다. 배포 모드는 부가 옵션이 아니라 제품 구조의 축입니다. 그러므로 "이 코드는 클라우드에만 있으면 된다" 는 가정을 코드에 넣지 않습니다.

가치 흐름은 다음 순서로 고정합니다.

```text
Build → Connect → Contextualize → Verify → Execute → Evaluate
```

## 2. 계층

위에서 아래로 흐릅니다. 위 계층은 아래 계층을 알지만, 아래 계층은 위 계층을 알지 못합니다.

| # | 계층 | 책임 | 패키지 자리 |
| --- | --- | --- | --- |
| 1 | Experience | Chat, Agent Builder, Workflow, Admin, Analytics | `apps/web` |
| 2 | Control Plane | Agent Registry, Model Registry, Policy, Evaluation, Identity, Config, Deployment, Marketplace | `apps/api` |
| 3 | Trust | Permission, Policy, Approval, Provenance, Audit | `packages/policy` |
| 4 | Agent Runtime | Planner, Executor, State, Memory, Scheduler, HITL | `packages/runtime` |
| 5 | Context Engine | Context Compiler, RAG, Memory, Knowledge, Skills | `packages/context`, `packages/memory` |
| 6 | MCP | MCP Gateway, Firewall, Auth, Permission, DLP | `packages/mcp` |
| 7 | Model | Cloud LLM, Local LLM, VLM, Embedding, Reranker | `packages/runtime` 의 model gateway |
| 8 | Enterprise Systems | DB, ERP, CRM, Groupware, File, Legacy, API | 저장소 밖 |

## 3. 의존 방향 규칙

이 절이 `arch-test` 단계가 기계로 판정할 계약입니다. 지금은 코드가 없어 검사가 비활성이며, Phase 0 에서 `packages/` 가 생기는 즉시 `.importlinter`(Python)와 `.dependency-cruiser.cjs`(TypeScript)로 옮겨 적습니다. 자연어로 남겨 두면 리뷰 이후에야 위반이 드러납니다([../harness/references/harness-elements.md](../harness/references/harness-elements.md) HE-4).

| ID | 규칙 |
| --- | --- |
| AR-1 | `apps/web` 은 `apps/api` 의 HTTP 계약만 압니다. `packages/*` 를 직접 import 하지 않습니다(공용 타입은 `packages/sdk` 경유). |
| AR-2 | `apps/api` 는 `packages/*` 를 씁니다. `packages/*` 는 `apps/*` 를 알지 못합니다. |
| AR-3 | `packages/runtime` 은 `packages/mcp` 와 `packages/context` 를 씁니다. 역방향 참조를 만들지 않습니다. |
| AR-4 | `packages/policy`(Trust)는 어느 계층에서도 호출될 수 있으나 스스로는 `runtime`·`mcp`·`context` 를 호출하지 않습니다. 판정만 하고 실행하지 않습니다. |
| AR-5 | 모델 호출은 `packages/runtime` 의 model gateway 한 곳을 지납니다. 다른 패키지에서 LLM SDK 를 직접 부르지 않습니다. Model-agnostic 원칙이 여기서 성립합니다. |
| AR-6 | 외부 시스템 접근은 전부 `packages/mcp` 를 지납니다. 우회 경로를 만들면 MCP Firewall 이 관측하지 못합니다. |
| AR-7 | Control Plane 은 Data Plane 을 **호출하지 않고 선언만** 합니다. On-Prem 에서 Data Plane 이 고객 데이터센터 안에만 있어도 성립해야 하기 때문입니다. |

## 4. Control Plane / Data Plane

```text
                 aether
                   │
        ┌──────────┴──────────┐
        ↓                     ↓
   Control Plane          Data Plane
   (Management)           (Execution)
        │                     │
        └──────────┬──────────┘
                   ↓
              Agent Runtime
```

| Plane | 포함 | 배포 |
| --- | --- | --- |
| Control | Organization, User, Agent Registry, Workflow, Model Registry, Policy, Evaluation, Marketplace, Deployment, Configuration | Cloud 또는 고객 내부 |
| Data | Agent Runtime, LLM, MCP Gateway, Context, Memory, Vector DB, Documents, Enterprise Data, Secrets, Logs | On-Prem 에서는 **전부** 고객 데이터센터 내부 |

이 분리가 깨지는 전형적인 방법은 Control Plane 코드가 Data Plane 의 저장소를 직접 읽는 것입니다. AR-7 이 그것을 막습니다.

## 5. 개발 원칙

로드맵 4장의 12개 원칙 중 **코드 편집 판단에 직접 걸리는 것**만 옮깁니다.

| ID | 원칙 | 편집할 때 무엇을 뜻하는가 |
| --- | --- | --- |
| DP-1 | API-first | 구현보다 계약을 먼저 고정합니다. 계약 변경은 파괴적 변경 여부를 먼저 판정합니다. |
| DP-2 | MCP-native | 새 연동은 전용 클라이언트가 아니라 MCP 서버로 붙입니다. |
| DP-3 | Model-agnostic | 특정 모델 벤더의 동작에 의존하는 코드를 게이트 밖에 두지 않습니다(AR-5). |
| DP-4 | Offline-capable | 인터넷 없이 Runtime 이 뜹니다. 부팅 경로에 외부 네트워크 호출을 넣지 않습니다. |
| DP-5 | Modular Monolith 부터 | 지금은 서비스로 쪼개지 않습니다. 경계는 패키지 경계로 표현합니다. |
| DP-6 | Security / Policy / Audit 를 초기부터 | 인증·권한·비밀값에 닿는 변경은 사람 검토로 에스컬레이션합니다([../AGENTS.md](../AGENTS.md) Trust). |

## 6. 지금 없는 것

Phase 0 미착수이므로 `apps/`, `packages/`, `infra/` 는 아직 존재하지 않습니다. 이 문서의 경로는 **만들 때 놓을 자리**이지 현재 상태가 아닙니다. 문서와 코드가 다르면 한쪽을 조용히 고르지 않고 불일치를 보고합니다.

## 관련 문서

- [domain.md](domain.md) — 여기 나온 용어의 정의
- [roadmap.md](roadmap.md) — 어느 Phase 에서 무엇이 생기는가
- [../AGENTS.md](../AGENTS.md) — 진입점 지침
