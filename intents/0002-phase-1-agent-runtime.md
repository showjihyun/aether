# Intent 0002 — Phase 1: Agent Runtime

| 키 | 값 |
| --- | --- |
| 번호 | 0002 |
| 작성일 | 2026-09-12 |
| 대상 Phase | [../docs/roadmap.md](../docs/roadmap.md) 의 Phase 1 (Week 3~5) — 원본 로드맵 6장 |
| 상태 | 승인됨 |
| 승인 | showjihyun, 2026-09-12 |
| 후속 spec | [../specs/0002-phase-1-agent-runtime.md](../specs/0002-phase-1-agent-runtime.md) (승인됨 2026-09-12) |

작업 단위는 [mvp-backlog.md](mvp-backlog.md) 의 P1-1 ~ P1-9 가 소유합니다. 이 문서는 그 아홉 단위가 **왜** 이번에 함께 가야 하는지, 끝났을 때 무엇이 관측되어야 하는지, 넘지 않을 선이 무엇인지를 고정합니다. 단위의 범위·완료 판정을 여기 복제하지 않습니다.

## Problem

Phase 0 이 끝났지만(intent 0001, 2026-09-11) 저장소에는 **아직 Agent 를 실행하는 코드가 없습니다.** 관측된 사실은 다음과 같습니다.

- `apps/api` 가 답하는 경로는 `/healthz` 와 OpenAPI 문서뿐입니다. 로드맵이 "핵심 API" 로 적은 `POST /agents`, `GET /agents`, `POST /agents/{id}/run`, `GET /runs/{id}`, `POST /runs/{id}/cancel` 은 하나도 없습니다.
- 데이터 모델 v1([../docs/data-model.md](../docs/data-model.md))의 `control.agents`, `control.agent_versions`, `control.runs`, `data.run_executions` 는 마이그레이션과 테스트만 읽고 씁니다. 불변 트리거와 역할 분리는 검증되었지만 **제품 코드가 한 행도 넣지 않았습니다.**
- `apps/worker` 는 Redis Streams `aether:runs:requested` 를 소비하는 뼈대만 있습니다. 메시지를 받아도 실행할 것이 없습니다.
- `packages/runtime` 은 세 층(`domain` / `application` / `adapters`)의 빈 껍데기입니다. model gateway 가 없으므로 AR-5(모델 호출 단일 통로)는 `.importlinter` 에 계약으로 등록만 되어 있고 **공허하게 통과**합니다. DP-3(Model-agnostic)은 아직 어떤 코드로도 증명되지 않았습니다.
- OpenTelemetry 는 초기화 코드만 있고, 의미 있는 span 은 하나도 만들지 않습니다(DP-4 의 "부팅 경로 외부 호출 0건" 만 성립).
- 하네스 평가 세트([../evaluation/README.md](../evaluation/README.md))의 REP-2·REP-4·REP-8 은 대상 동작이 없어 실행할 수 없고, `{{성능_기준}}` 은 자리표시자입니다. 성숙도 L2 진입은 평가 기준선이 없어 멈춰 있습니다.

로드맵이 제품의 심장으로 그린 루프 `User → Agent → Model → Tool → Observation → Model → Result` 는 구현이 0 입니다. 이 상태로는 Phase 2(MCP Gateway)가 붙을 자리도, Phase 3(Context Engine)이 채울 입력도 없습니다.

## Proposed Outcome

Phase 1 이 끝났을 때 다음이 관측 가능합니다. 각 항목은 backlog 의 어느 단위가 판정하는지를 괄호에 적습니다.

- `POST /agents` 로 만든 Agent 에 `Agent Version` 1 이 함께 생기고, 수정하면 Version 2 가 생기며 Version 1 은 그대로입니다(P0-8 의 불변 트리거가 제품 경로에서 처음 실제로 걸림). `GET /agents`, `GET /agents/{id}` 가 그것을 보여줍니다 (P1-1).
- `POST /agents/{id}/run` 이 `queued` 상태의 Run id 를 즉시 돌려주고, worker 가 그 Run 을 집어 Model → Tool → Observation → Model 루프를 돌아 `GET /runs/{id}` 가 `succeeded` / `failed` / `cancelled` / `timed_out` 중 하나로 끝납니다. `POST /runs/{id}/cancel` 뒤에는 `cancelled` 입니다 (P1-2, P1-4, P1-5).
- Run 의 이벤트(상태 전이, 모델 토큰, 도구 호출·결과)가 SSE 로 흘러나오고, 이벤트 순서가 상태 전이 순서와 같으며, 클라이언트가 끊겨도 Run 은 계속됩니다 (P1-6).
- Run 타임아웃이 `timed_out` 으로, 재시도 한도 초과가 사유 있는 `failed` 로 남습니다. 그 테스트는 실제 시계가 아니라 **주입된 시계**로 결정적으로 통과합니다 (P1-7).
- 한 Run 의 span 트리(Run → Task → 모델 호출 / 도구 호출)가 compose 의 로컬 collector 에서 보이고, `GET /runs/{id}` 응답에 trace id 가 있습니다 (P1-8).
- 위 전부가 **fake 모델 어댑터로 네트워크 없이** 통과하고, 설정을 바꾸면 OpenAI-호환 API 를 내는 로컬 LLM 서버로도 같은 코드가 돕니다 (P1-3). AR-5 와 AR-7 이 더는 공허하지 않습니다 — 위반 코드를 넣으면 `api-arch` 가 실제로 exit 0 이 아닌 값을 냅니다.
- `harness.config` 에 `smoke`(compose up → agent 생성 → run → `succeeded`)가 집계되고, verify 전체는 spec 0001 D-12 의 10분 예산 안에 있습니다. 별도 단계로 두는지 기존 단계에 접는지는 열린 질문 8 입니다. `{{성능_기준}}` 의 값이 **사람이** 고정한 숫자로 evaluation/README 에 적힙니다 (P1-9).
- 새 경로는 전부 P0-9 의 `require_principal(app.state.authenticate)` 뒤에 있습니다. 인증 없는 요청은 401, `/healthz` 와 문서 경로만 예외입니다.

## Affected Users

| 대상 | 무엇을 느끼는가 |
| --- | --- |
| 내부 개발자 | 처음으로 "동작하는 제품" 을 봅니다. `packages/sdk` 의 생성 타입에 Agent·Run 이 생기고, compose 한 번에 Agent 를 만들어 실행할 수 있습니다 |
| 에이전트(하네스) | `smoke` 단계로 끝에서 끝까지의 피드백을 얻습니다. REP-2·REP-4·REP-8 이 실행 가능해져 평가 기준선을 만들 수 있습니다 |
| 운영자 | compose 에 collector 가 생겨 Run 의 trace 를 봅니다. 아직 외부에 노출되는 것은 없습니다 |
| 최종 사용자 | 없습니다. `apps/web` 은 이번 Phase 에 화면을 얻지 않습니다 |

## Affected Systems

[../docs/architecture.md](../docs/architecture.md) 2절의 계층 이름으로 적습니다.

| 계층 / 패키지 | 어떤 영향 |
| --- | --- |
| Control Plane `apps/api` | Agent Registry API, Run API(선언·조회·취소), SSE 스트림. 전부 `adapters/inbound/http/` 라우터 + `application/usecases` + 포트, 조립은 `main.py`(AR-8 ~ AR-12) |
| Agent Runtime `apps/worker` | 실행 프로세스. `aether:runs:requested` 를 집어 `packages/runtime` 의 루프를 돌리고 `data.run_executions` 를 갱신. 상태 변화를 `aether:runs:status` 로 알림 |
| Agent Runtime `packages/runtime` | **비어 있던 껍데기가 처음 채워집니다.** Run 상태 기계·Task·State 영속 포트(P1-2), model gateway 와 fake·OpenAI-호환 어댑터(P1-3), Planner/Executor 루프와 프로세스 내부 도구 둘(P1-4), 재시도·타임아웃 정책(P1-7), span 생성(P1-8) |
| Model `packages/runtime` 의 model gateway | Model 계층의 첫 구현. 계층 7 은 이 gateway 뒤에만 존재합니다 |
| `packages/sdk` | 새 경로의 OpenAPI → 생성 타입 갱신, 호출 함수 수기 추가(spec 0001 D-2) |
| Experience `apps/web` | 변경 없음(Non-goals) |
| `infra/docker` | OpenTelemetry collector 서비스 1개. 로컬 LLM 서버는 선택 프로파일(Q6) |
| 데이터 모델 | 기존 네 테이블을 제품 코드가 처음 읽고 씁니다. 재시도·타임아웃 정책은 `agent_versions.definition` 안에 두는 것이 1안 — 스키마 변경이 필요하면 Alembic 마이그레이션과 spec 결정(D)으로만 |
| `harness.config`(보호) | `smoke` 단계 추가 — 사람(P1-9) |
| `evaluation/README.md`(보호) | `{{성능_기준}}` 값 고정 — 사람(P1-9, EI-2) |

의존 방향 규칙에 걸리는 지점:

- **AR-2**: `apps/api` 와 `apps/worker` 가 `packages/runtime` 을 쓰기 시작합니다. 역방향(`packages/runtime` → `apps/*`)이 생기지 않는지 `.importlinter` 가 이미 봅니다.
- **AR-5**: 모델 호출이 처음 생깁니다. LLM SDK·HTTP 호출은 `packages/runtime` 의 model gateway 어댑터 안에만 있어야 하고, 위반은 `api-arch` 가 잡아야 합니다. 계약은 있으니 이번에 **실제로 걸리는지** 부정 테스트로 확인합니다(P0-6 방식).
- **AR-7**: `apps/api` 는 Run 을 `control.runs` 에 **선언**하고 스트림에 넣을 뿐, worker 를 import 하지도 `data.run_executions` 를 직접 읽지도 않습니다(역할 `aether_control` 은 `data` 스키마 권한이 없습니다). `GET /runs/{id}` 는 spec 0001 2.8·D-11 대로 `control.runs` 의 투영 열만 읽고, 그 열은 worker 의 `aether:runs:status` 알림으로 갱신됩니다(투영 열 추가는 P1-5). 누가 그 알림을 소비하는지가 열린 질문 2 입니다.
- **AR-8 ~ AR-12**: `packages/runtime` 안에도 `domain` / `application` / `adapters` 배치가 그대로 적용됩니다. LLM 어댑터·Redis·OTel 은 `adapters/outbound`, 루프와 상태 기계는 `domain`·`application` 에 두어 fake 만으로 테스트됩니다.

## Constraints

- **Offline-capable**(DP-4). fake 어댑터 경로는 네트워크 0 으로 전부 통과합니다. OpenAI-호환 어댑터는 로컬 서버만 대상이며, 테스트·CI·smoke 에서 클라우드 LLM 을 호출하지 않습니다. compose 는 이미지 pull 외에 인터넷이 없어도 뜹니다(P0-5 의 `probe` 가 계속 성립).
- **Model-agnostic**(DP-3, AR-5). 벤더별 동작에 기대는 코드를 gateway 밖에 두지 않습니다. 어댑터는 `complete` / `stream` / `embed` 하나의 인터페이스만 구현합니다.
- **Control Plane 은 선언만**(AR-7). Phase 0 에서 정한 역할·스키마 분리를 이번 편의를 위해 풀지 않습니다. 역할 권한을 넓히는 변경은 spec 의 [실질] 개정과 사람 승인이 필요합니다.
- **API-first**(DP-1). 라우트마다 OpenAPI 가 먼저 커밋되고 `packages/sdk` 드리프트 테스트가 그것을 지킵니다. SSE 이벤트 스키마도 계약입니다 — 바꾸면 파괴적 변경 판정을 먼저 합니다.
- **인증은 P0-9 그대로**(DP-6, 🔒). 새 경로는 `require_principal` 뒤에 둡니다. 새 인증 방식·Permission·조직 모델을 만들지 않습니다. 인증에 닿는 변경이 필요해지면 그 단위는 🔒 로 표시하고 사람 검토를 거칩니다.
- **결정적 테스트.** 시간은 주입된 시계, 모델은 fake 어댑터, 난수는 주입. `sleep` 으로 시계를 움직이는 테스트는 받지 않습니다(improvement-log `2026-09-11-016` 의 관측).
- **verify 예산과 단계 상한.** 전체 실행 시간은 D-12 의 10분 안에 있어야 하고, 통합 테스트는 testcontainers 하나로 묶습니다. spec 0001 D-7 은 제품 단계를 **10개까지**로 확정했고 지금 10개가 다 차 있습니다 — `smoke` 를 11번째 단계로 더하면 그 상한을 넘습니다. 기존 단계에 접을지, 상한을 다시 정할지(사람 결정, `improvement-log/` 근거)는 열린 질문 8 이며, 어느 쪽이든 게이트를 약화하는 방향은 아닙니다.
- **TDD 와 PR 게이트는 Phase 0 과 같습니다.** 단위마다 implementer 의 `red 증거`, 브랜치 → PR → CI → 사람 병합, `Unit: P1-n` trailer.
- **라우터 조립 함정.** `Depends` 를 쓰는 파일에서 `from __future__ import annotations` 와 함수 안 지역 `Annotated` 를 함께 쓰면 422 가 납니다(`2026-09-11-017`). 라우터는 모듈 수준에서 정의하거나 이 조합을 피합니다. lint 로 승격할지는 승격 판정이 정합니다.
- **기간.** 로드맵 Week 3~5. 단위 아홉, 사람 손이 필요한 순간은 Q6 채택, `harness.config` 의 `smoke`, `{{성능_기준}}` 고정, 그리고 단위마다의 PR 병합입니다.

## Open Questions

| # | 질문 | 누가 답하는가 | 언제까지 |
| --- | --- | --- | --- |
| 1 | **Q6** 로컬 LLM 서버의 기본 후보. OpenAI-호환 API 를 내면 어댑터는 같으므로 후보(Ollama, vLLM, llama.cpp server 등)만 여기 두고 채택은 spec 에서. **모델은 답함(2026-09-12, showjihyun): 로컬 LLM 경로의 기본 테스트 모델은 Qwen3.8 27B 양자화.** 단위 테스트·CI 는 fake 어댑터(네트워크 0) 그대로. 남은 것: 그 모델을 내는 서버, 정확한 모델 태그와 양자화 형식, 필요한 자원(VRAM) | 사람(모델) · spec(서버·태그) | **닫힘** 2026-09-12 · 답: **Ollama**, 태그 `qwen3.8:27b`(실재 확인), 판정은 fake (spec 0002 D-1) |
| 2 | `control.runs` 의 투영 열(`status`, `finished_at`, spec 0001 2.8·D-11)을 **누가** `aether:runs:status` 에서 갱신하는가 — api 프로세스 안의 소비자인가 별도 프로세스인가, 소비 실패·중복 전달 시 재처리는 어떻게 하는가 | spec 작성자 → 사람 승인 | **닫힘** 2026-09-12 · 답: api 프로세스 안의 소비자, `seq` 단조 증가로 멱등, 커밋 뒤 ack (D-2) |
| 3 | `agent_versions.definition` 의 내용과 `schema_version` 규칙 — 시스템 프롬프트, 모델 id, 도구 목록, 재시도·타임아웃 정책이 여기 들어가는가 | spec 작성자 → 사람 승인 | **닫힘** 2026-09-12 · 답: 전부 들어감 — `AgentDefinition` v1, 도구 이름은 `BUILTIN_TOOL_NAMES` 로 검증, 어댑터 종류·thinking 은 배포 설정 (D-3) |
| 4 | SSE 이벤트 스키마와 이벤트 id 의 의미(P1-6 은 재접속 이어보기를 범위 밖으로 두되 id 는 남깁니다) | spec 작성자 | **닫힘** 2026-09-12 · 답: 봉투 `v/run_id/seq/at/type/payload`, 8종, Run 별 Redis Stream explicit ID `<seq>-0`, `events.schema.json` (D-4) |
| 5 | P1-4 의 프로세스 내부 도구 인터페이스를 지금부터 MCP tool 스키마(JSON Schema 인자)와 같은 모양으로 두어 Phase 2 가 전송 계층만 바꾸게 할 것인가 | spec 작성자 → 사람 승인 | **닫힘** 2026-09-12 · 답: 예 — MCP tool 모양 (D-5) |
| 6 | compose 의 collector 이미지와, CI 의 `smoke` 가 collector 까지 띄우는가(예산) | spec 작성자 | **닫힘** 2026-09-12 · 답: `otel-collector` 기본 서비스, `debug` + `file`(host bind mount), smoke 가 띄움 (D-7) |
| 7 | `{{성능_기준}}` 의 측정 정의(Run 생성 응답 P95, 환경, 표본 수). 값 자체는 P1-9 에서 사람이 고정 | 사람 | **닫힘** 2026-09-12 · 측정 정의는 답함(P95, 순차 200회, 워밍업 20 제외, 환경 이름 — D-8). **값은 P1-9 에서 사람** |
| 8 | `smoke` 를 verify 에 어떻게 넣는가. spec 0001 D-7 의 제품 단계 상한 10개가 이미 찼으므로 — 기존 단계(예: `api-integration`)에 compose 시나리오로 접는가, 상한을 재해석하는가(EI-2 상 사람 결정, 후보 기록) | 사람 | **닫힘** 2026-09-12 · 답: 별도 11번째 단계, spec 0001 D-7 [실질] 개정, 회귀 조건 숫자 (D-15) |

여덟 질문 전부 2026-09-12 spec 0002 승인으로 닫혔습니다(7 은 측정 정의만 — 값은 P1-9 에서 사람이 고정). 답의 근거는 spec 0002 4절이 소유합니다.

## Non-goals

| 항목 | 언제 하는가 |
| --- | --- |
| MCP Gateway·Firewall, 외부 시스템 연동 | Phase 2 (intent 0003). P1-4 의 도구는 프로세스 내부 함수 둘뿐 |
| Context Compiler, RAG, Memory, Knowledge | Phase 3. 이번 모델 입력은 System Context + 대화만 |
| HITL, Approval, Workflow | Phase 4 |
| Permission, Policy, 조직·사용자 모델, SSO | Trust Layer (Phase 8). 인증은 API 키 하나 그대로 |
| Model Registry, 벤더별 SDK 다수, 프롬프트 캐싱·비용 집계 | Phase 6 |
| `apps/web` 의 화면(Agent 목록, Run 보기) | Experience 계층의 Phase. 이번엔 SDK 타입만 갱신 |
| WebSocket, SSE 재접속 이어보기 | 이후. 이벤트 id 만 남겨 둡니다 |
| 부하 테스트(`load` 단계), 대시보드, 샘플링 정책 | 이후 |
| Kubernetes 실배포, Air-Gapped 번들 | Month 6 / Phase 11 |

## 근거

- 원본 로드맵 6장 "Phase 1 — Agent Runtime": 기능 목록(Agent, Agent Version, Run, Task, State, Streaming, Retry, Timeout, Cancellation, Error Handling), 핵심 API 다섯 개, "인터넷 없이도 Runtime 자체가 실행 가능해야 한다". 등급은 [../docs/roadmap.md](../docs/roadmap.md) 1절.
- [mvp-backlog.md](mvp-backlog.md) Phase 1 — P1-1 ~ P1-9 의 범위·의존·완료 판정. Phase 완료 판정 문장은 이 intent 의 Proposed Outcome 과 같은 것을 가리킵니다.
- intent 0001 완료(2026-09-11): Phase 0 이 만든 데이터 모델·인증·게이트가 이번 단위들의 선행 조건입니다. P1-1 은 P0-8·P0-9 에, P1-5 는 P0-4 에 의존합니다.
- 관측된 실패: 제품 실패는 없습니다(제품 동작이 아직 없으므로). 과정에서 관측된 후보 두 건이 제약으로 들어왔습니다 — `improvement-log/2026-09-11-016.yaml`(시계 해상도로 거짓 red → 주입된 시계), `improvement-log/2026-09-11-017.yaml`(PEP 563 + `Depends` 422 → 라우터 조립 방식). 둘은 후보이지 규칙이 아니며, 이 intent 가 그것을 규칙으로 승격하지는 않습니다.
