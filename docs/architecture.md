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
| 2 | Control Plane | Agent Registry, Model Registry, Policy, Evaluation, Identity, Config, Deployment, Marketplace | `apps/api`. 제품 Evaluation 은 `packages/evaluation` |
| 3 | Trust | Permission, Policy, Approval, Provenance, Audit | `packages/policy` |
| 4 | Agent Runtime | Planner, Executor, State, Memory, Scheduler, HITL | `packages/runtime`, `packages/workflow`. 실행 프로세스는 `apps/worker` |
| 5 | Context Engine | Context Compiler, RAG, Memory, Knowledge, Skills | `packages/context`, `packages/memory` |
| 6 | MCP | MCP Gateway, Firewall, Auth, Permission, DLP | `packages/mcp` |
| 7 | Model | Cloud LLM, Local LLM, VLM, Embedding, Reranker | `packages/runtime` 의 model gateway |
| 8 | Enterprise Systems | DB, ERP, CRM, Groupware, File, Legacy, API | 저장소 밖 |

## 3. 의존 방향 규칙

이 절과 3.1 이 `arch-test` 단계가 기계로 판정할 계약입니다. 지금은 코드가 없어 검사가 비활성이며, Phase 0 에서 `packages/` 가 생기는 즉시 `.importlinter`(Python)와 `.dependency-cruiser.cjs`(TypeScript)로 옮겨 적습니다. 자연어로 남겨 두면 리뷰 이후에야 위반이 드러납니다([../harness/references/harness-elements.md](../harness/references/harness-elements.md) HE-4).

| ID | 규칙 |
| --- | --- |
| AR-1 | `apps/web` 은 `apps/api` 의 HTTP 계약만 압니다. `packages/*` 를 직접 import 하지 않습니다(공용 타입은 `packages/sdk` 경유). |
| AR-2 | `apps/api` 는 `packages/*` 를 씁니다. `packages/*` 는 `apps/*` 를 알지 못합니다. |
| AR-3 | `packages/runtime` 은 `packages/mcp` 와 `packages/context` 를 씁니다. 역방향 참조를 만들지 않습니다. |
| AR-4 | `packages/policy`(Trust)는 어느 계층에서도 호출될 수 있으나 스스로는 `runtime`·`mcp`·`context` 를 호출하지 않습니다. 판정만 하고 실행하지 않습니다. |
| AR-5 | 모델 호출은 `packages/runtime` 의 model gateway 한 곳을 지납니다. 다른 패키지에서 LLM SDK 를 직접 부르지 않습니다. Model-agnostic 원칙이 여기서 성립합니다. |
| AR-6 | 외부 시스템 접근은 전부 `packages/mcp` 를 지납니다. 우회 경로를 만들면 MCP Firewall 이 관측하지 못합니다. |
| AR-7 | Control Plane 은 Data Plane 을 **호출하지 않고 선언만** 합니다. On-Prem 에서 Data Plane 이 고객 데이터센터 안에만 있어도 성립해야 하기 때문입니다. |

### 3.1 패키지 안의 의존 방향 (AR-8 ~ AR-12)

AR-1 ~ AR-7 은 패키지 **사이**의 방향입니다. 패키지 **안**에도 방향이 있어야 합니다. 없으면 FastAPI 핸들러가 SQLAlchemy 세션을 직접 만들고, 그 순간 유스케이스 하나를 테스트하려면 DB 가 필요해집니다. 클린 아키텍처의 의존성 규칙과 헥사고날 아키텍처의 포트·어댑터를 가져옵니다. 무엇을 가져오고 무엇을 뺐는지는 [../PROVENANCE.md](../PROVENANCE.md) 7절이 소유합니다.

#### 용어

포트와 어댑터는 디렉터리 이름이 아니라 개념입니다. 먼저 뜻을 고정합니다.

| 용어 | 뜻 | 어디에 |
| --- | --- | --- |
| **포트** (Port) | 애플리케이션 경계에 놓인 **인터페이스**. `Protocol` 로 선언합니다. 기술을 모릅니다 | `application/ports` — 안쪽이 소유 |
| inbound 포트 | 바깥이 안을 **부르는** 계약. 유스케이스의 인터페이스. "이것을 해 달라" | `application/ports/inbound` |
| outbound 포트 | 안이 바깥에 **요구하는** 계약. 저장소, 큐, 모델, 시계. "이것이 필요하다" | `application/ports/outbound` |
| **유스케이스** (Use case) | inbound 포트의 구현. outbound 포트만 통해 바깥을 봅니다 | `application/usecases` |
| **어댑터** (Adapter) | 포트와 기술을 잇는 바깥 코드. 기술을 압니다 | `adapters` |
| inbound 어댑터 | inbound 포트를 **부르는** 쪽. HTTP 라우터, CLI, 스트림 소비자 | `adapters/inbound` |
| outbound 어댑터 | outbound 포트를 **구현하는** 쪽. PostgreSQL 저장소, Redis 발행자, LLM SDK 호출 | `adapters/outbound` |
| **조립** (Composition root) | 유스케이스에 outbound 어댑터를 꽂고, inbound 어댑터에 유스케이스를 포트 타입으로 건네는 곳. 양쪽을 다 아는 유일한 코드 | `apps/*/main.py` |

포트는 **안쪽이 소유**합니다. 어댑터가 포트의 모양을 정하면 기술이 애플리케이션의 모양을 정하게 되고, 그것이 헥사고날이 막으려는 바로 그 일입니다.

#### 구조

모든 Python 패키지 — `packages/*` 와 `apps/*` 둘 다 — 는 같은 구조를 가집니다.

```text
aether_<이름>/
  domain/                    엔티티·값 객체·도메인 규칙. 표준 라이브러리와 domain 만 import
  application/
    ports/
      inbound/               유스케이스 인터페이스 (Protocol)
      outbound/              바깥에 요구하는 인터페이스 (Protocol)
    usecases/                inbound 포트의 구현. domain 과 ports 만 import
  adapters/
    inbound/                 inbound 포트를 부름. ports.inbound 와 domain 만 import
    outbound/                outbound 포트를 구현. ports.outbound 와 domain 만 import
  main.py                    apps/* 에만. 조립
```

#### 규칙

| ID | 규칙 |
| --- | --- |
| AR-8 | 의존은 **안쪽으로만** 흐릅니다: `adapters` → `application` → `domain`. `domain` 은 `application` 을, `application` 은 `adapters` 를 import 하지 않습니다. |
| AR-9 | `domain` 과 `application` 은 **프레임워크와 I/O 를 import 하지 않습니다** — `fastapi`, `starlette`, `uvicorn`, `sqlalchemy`, `alembic`, `psycopg`, `asyncpg`, `redis`, `httpx`, `aiohttp`, `requests`, `opentelemetry`, 그리고 AR-5·AR-6 의 SDK. 바깥이 필요하면 outbound 포트를 선언하고 `adapters/outbound` 가 구현합니다. 검증 라이브러리(pydantic)는 I/O 가 아니므로 막지 않되, `domain` 은 표준 `dataclass` 를 권장합니다. |
| AR-10 | 포트에 어댑터를 꽂는 **조립은 `apps/*` 의 `main.py` 한 곳**입니다. `packages/*` 안에 조립 코드가 있으면 그 패키지가 배포 모드를 알게 됩니다. |
| AR-11 | `adapters/inbound` 와 `adapters/outbound` 는 **서로를 import 하지 않습니다.** 둘은 `application` 을 통해서만 만납니다. 라우터가 저장소를 직접 부르면 유스케이스가 사라지고, 그 경로는 테스트도 정책도 지나지 않습니다. |
| AR-12 | **어댑터는 포트로만 애플리케이션을 만납니다.** `adapters` 는 `application.ports` 만 import 하고 `application.usecases` 를 import 하지 않습니다. inbound 어댑터가 유스케이스 구현을 직접 부르면 포트는 장식이 되고, 테스트에서 유스케이스를 fake 로 바꿀 수 없습니다. 유스케이스 인스턴스는 조립(AR-10)이 포트 타입으로 건넵니다. |

#### 방향과 신뢰 경계

헥사고날의 핵심은 대칭입니다. inbound(driving) 어댑터는 시스템을 **움직이는** 쪽이고 outbound(driven) 어댑터는 시스템이 **움직이는** 쪽인데, 둘 다 안을 **포트로만** 만납니다. 같은 inbound 포트에 HTTP 와 CLI 가 둘 다 붙는 것(`aether-api` 의 라우터와 `keys create`)이 이 대칭의 첫 실례입니다 — 유스케이스는 누가 자기를 불렀는지 모릅니다.

신뢰 경계도 여기 놓입니다. `Observation` 처럼 바깥에서 온 데이터는 outbound 어댑터를 지나 들어오므로, 그것이 데이터이지 지시가 아님을 표시하는 일은 어댑터의 몫이고 `domain` 은 이미 표시된 값만 봅니다([domain.md](domain.md) 1절).

#### 이미 있는 규칙과의 관계

AR-5 의 model gateway 는 outbound 포트 하나(`application/ports/outbound` 의 `ModelGateway`)와 `adapters/outbound/model_gateway/` 의 어댑터들입니다. AR-6 의 MCP Gateway 도 같은 모양입니다. AR-8 ~ AR-12 는 그 두 특수 사례를 일반 규칙으로 올린 것입니다.

#### 이 규칙에 달린 두 이득

| 이득 | 어떻게 |
| --- | --- |
| TDD | 유스케이스 테스트는 inbound 포트로 부르고 outbound 포트에 fake 를 꽂습니다 — 컨테이너 없이 돕니다(AR-9). 어댑터는 **포트 계약 테스트**로 검사합니다: 같은 테스트를 fake 어댑터와 실제 어댑터에 둘 다 돌려, 둘이 같은 계약을 지킴을 증명합니다. `api-unit` 이 빠른 것이 관행이 아니라 규칙이 되고, 실제 어댑터만 `api-integration` 으로 갑니다 |
| 운영 | DP-3(Model-agnostic)·DP-4(Offline)가 "outbound 어댑터를 바꿔 꽂는다" 로 환원됩니다. Cloud 는 원격 LLM 어댑터, Air-Gapped 는 로컬 어댑터. 바꿔 꽂아도 된다는 주장은 포트 계약 테스트가 증명합니다. `domain` 은 어느 쪽인지 모릅니다 |

#### 기계 판정

AR-8 은 import-linter `layers` 계약 하나(`containers` 로 전 패키지), AR-9 는 `forbidden`(`include_external_packages`), AR-11 은 `forbidden` 두 개, AR-12 는 `forbidden` 하나(`adapters` → `application.usecases`). AR-10 은 어댑터가 실제로 생기는 Phase 1 에 승격하고 그 전에는 리뷰 항목입니다. 계약 본문은 [../plans/0001-phase-0-foundation.md](../plans/0001-phase-0-foundation.md) 부록 D. TypeScript 쪽(`apps/web`)은 지금 페이지 하나라 판정하지 않고, Phase 5 Agent Builder 에서 다시 봅니다.

코드가 비어 있는 지금 이 규칙을 붙이는 이유는 단순합니다. 지금 붙이면 공허하게 통과하고, 코드가 생긴 뒤 붙이면 리팩터링이 됩니다.

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

Phase 0 은 끝났습니다(2026-09-11). `apps/{api,web,worker}` 와 `infra/docker` 는 있고 동작하며, `apps/api` 에는 API 키 인증(spec 0001 2.9 — inbound 포트 `Authenticate`·`IssueApiKey`, outbound 포트 `ApiKeyStore`, PostgreSQL 어댑터, `main.py` 조립)이 3.1 의 배치 그대로 들어 있습니다. `packages/*` 는 세 층(3.1)의 **빈 껍데기**입니다 — 구현은 Phase 1 부터. AR-1 ~ AR-12(AR-10 제외)는 `.importlinter`·`.dependency-cruiser.cjs` 로 verify 의 `api-arch`·`web-arch` 단계에서 판정되고 있습니다(EL-6). 문서와 코드가 다르면 한쪽을 조용히 고르지 않고 불일치를 보고합니다.

## 관련 문서

- [domain.md](domain.md) — 여기 나온 용어의 정의
- [roadmap.md](roadmap.md) — 어느 Phase 에서 무엇이 생기는가
- [../AGENTS.md](../AGENTS.md) — 진입점 지침
