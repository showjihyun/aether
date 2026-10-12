# Intent 0005 — Phase 4: Workflow Engine

| 키 | 값 |
| --- | --- |
| 번호 | 0005 |
| 작성일 | 2026-10-12 |
| 대상 Phase | [../docs/roadmap.md](../docs/roadmap.md) 의 Phase 4 (Week 13~16) — 원본 로드맵 9장 |
| 상태 | 초안 |
| 승인 | (비어 있습니다 — 승인 전에는 spec 을 쓰지 않습니다) |
| 후속 spec | (승인 뒤 `specs/0005-phase-4-workflow-engine.md`) |

작업 단위는 [mvp-backlog.md](mvp-backlog.md) 의 P4-1 ~ P4-5 가 소유합니다. 이 문서는 그 다섯 단위가 **왜** 이번에 함께 가야 하는지, 끝났을 때 무엇이 관측되어야 하는지, 넘지 않을 선이 무엇인지를 고정합니다. 단위의 범위·완료 판정을 여기 복제하지 않습니다.

## Problem

Phase 3 이 끝나(2026-10-10) Agent 는 도구를 부르고(Phase 2) 예산 안에서 Knowledge·Memory 를 포함한 Context 를 받습니다(Phase 3). 그런데 **Agent 하나보다 큰 일을 표현할 방법이 없습니다.** 지금 제품이 실행할 수 있는 것은 "Agent 하나를 한 번 돌리는 것" 뿐입니다 — 조건에 따라 갈라지거나, 둘을 나란히 돌리거나, 중간에 사람이 보고 승인하는 일은 표현할 자리조차 없습니다.

관측된 사실은 다음과 같습니다.

- **`packages/workflow` 는 빈 껍데기입니다.** `__init__.py` 10개로 세 층의 디렉터리만 있고 구현이 **0행**이며, `tests/` 디렉터리도 없습니다. Phase 3 시작 시점의 `packages/context`·`packages/memory` 와 같은 모양입니다.
- **방향 규칙이 workflow 에는 없습니다.** `.importlinter` 의 `ar3-runtime-direction` 계약은 `source_modules` 가 `aether_mcp`·`aether_context` 둘뿐이고, `aether_workflow` 는 **어느 방향 계약에도 들어 있지 않습니다**(root_packages 와 AR-2·AR-5·AR-8·AR-9·AR-11·AR-12 의 일반 계약에만 있습니다). [../docs/architecture.md](../docs/architecture.md) 38행의 AR-3 문구도 workflow 를 말하지 않습니다. [mvp-backlog.md](mvp-backlog.md) 의 P4-2 는 "걸리는 규칙 AR-3: workflow 가 runtime 을 쓰고 역방향은 없음" 이라고 적었지만 **그 규칙은 문서에도 계약에도 없습니다.** 지금은 `runtime → workflow` 역참조를 아무도 막지 않습니다.
- **도메인 문서에 `Workflow` 가 정의되어 있지 않습니다.** [../docs/domain.md](../docs/domain.md) 에 `Workflow`·`Node`·`Approval` 항이 없습니다. architecture.md 는 `Workflow` 를 Experience 층(21행)과 Control Plane 의 구성요소(133행)에 **이름으로만** 적습니다. Phase 3 은 domain.md 3절이 정의해 둔 `Context`·`Knowledge`·`Memory` 에 코드를 붙이는 작업이었는데, Phase 4 에는 그 닻이 없습니다 — 용어를 코드가 먼저 정하면 문서가 코드를 따라가게 됩니다.
- **`waiting` 이 이미 다른 뜻으로 쓰입니다.** `RunStatus.WAITING` 은 enum·전이표·마이그레이션 0001 의 `data.run_execution_status` 에 있고, `execute_run.py` 672행이 **도구 호출을 기다릴 때** 그 상태를 알립니다. P4-4 의 "승인 대기" 를 같은 값으로 두면 "도구를 기다리는 중" 과 "사람을 기다리는 중" 이 상태만으로 구별되지 않습니다.
- **Workflow 의 영속 자리가 없습니다.** 마이그레이션은 0001~0004 뿐이고 workflow 관련 표가 하나도 없습니다. Workflow 정의·버전·실행 상태를 `control` 과 `data` 중 어디에 둘지도 정해진 바가 없습니다.
- **한 Run 의 완료를 다른 프로세스가 기다릴 수단이 요청 쪽만 있습니다.** api → worker 는 `aether:runs:requested` 스트림으로 밀지만, 완료를 기다리는 쪽에는 `GET /runs/{id}` 폴링과 SSE 밖에 없습니다. AGENT 노드는 Run 을 만들고 **기다려야** 하므로 그 수단이 정해져야 합니다 — 그리고 기다리는 동안 worker 슬롯을 점유하면 Workflow 하나가 다른 Run 을 굶깁니다.
- **사람 개입이 제품에 없습니다.** Phase 1 의 P1-7 이 "사람 개입(HITL 은 Phase 4)" 으로 미뤘고 그 뒤 어떤 단위도 집지 않았습니다. 지금은 Run 이 시작되면 끝까지 가거나 실패하거나 취소되는 셋뿐이고, **중간에 사람이 보고 통과시키는 지점이 없습니다.**

이것이 비용인 이유는 하나입니다. 제품의 약속은 "Agent 를 실행하는 것" 이 아니라 **"조직의 일을 AI Runtime 에서 돌리는 것"** 이고, 조직의 일에는 거의 언제나 분기와 승인이 있습니다. 승인 지점이 없는 자동화는 돌려 봐도 되는 일에만 쓸 수 있고, 그것은 가장 가치가 낮은 일들입니다.

## Proposed Outcome

Phase 4 가 끝났을 때 다음이 관측 가능합니다. 각 항목은 backlog 의 어느 단위가 판정하는지를 괄호에 적습니다.

- **`START → AGENT → CONDITION → HUMAN → AGENT → END` 인 Workflow 하나가 worker 에서 끝까지 실행됩니다.** 승인 노드에서 멈추고, 사람의 승인 API 호출로 재개되어 END 에 도달합니다 (P4-2, P4-4).
- **잘못된 그래프는 실행 전에 거부됩니다.** END 가 없거나 고아 노드가 있거나 START 가 둘인 정의는 저장·실행되지 않고 사유가 돌아옵니다. Workflow Version 은 불변이고, 정의를 바꾸면 새 Version 이 됩니다 (P4-1).
- **분기 양쪽이 각각 테스트로 타집니다.** CONDITION 은 이전 노드의 출력으로 갈라지고, 그 판정 규칙은 코드에 있습니다 — "알아서 잘" 이 아닙니다 (P4-2).
- **프로세스를 재시작해도 이어 실행됩니다.** Workflow Run 의 상태가 영속되어 있고, 중단된 지점부터 다시 갑니다 (P4-2).
- **PARALLEL·LOOP·WAIT 가 동작합니다.** 병렬 분기가 합류하고, 루프는 **상한이 필수**이며 상한을 넘기면 `failed` 가 되고, 대기는 주입된 시계로 결정적으로 테스트됩니다 (P4-3).
- **승인 전 재개 시도는 거부됩니다.** 승인 없이 재개를 요청하면 거부되고, 승인 뒤에는 재개되며, **누가 언제 승인했는지가 기록으로 남아 조회됩니다** (P4-4).
- **LLM·MCP·TOOL 노드가 각자의 통로를 지납니다.** Agent 를 거치지 않는 단일 호출 노드도 모델은 `ModelGateway`(AR-5), 도구는 MCP Gateway(AR-6)를 지나고, `api-arch` 가 그것을 막습니다 (P4-5).
- **`workflow → runtime` 단방향이 코드로 실재하고, 역방향을 주입하면 `api-arch` 가 exit 0 이 아닌 값을 냅니다.** Phase 3 이 AR-3 에 한 것과 같습니다 — 지금은 계약 자체가 없으므로, 계약을 만드는 것까지 이 Phase 의 결과입니다.
- **"도구를 기다리는 중" 과 "사람을 기다리는 중" 이 구별됩니다.** 둘을 같은 값으로 두지 않고, 운영자가 멈춘 이유를 상태만으로 알 수 있습니다.
- 위 전부가 **네트워크 없이** 통과합니다 — fake 모델로 결정적으로.
- 새 API 경로는 전부 인증 뒤에 있습니다. 인증 없는 요청은 401 입니다.

## Affected Users

| 대상 | 무엇을 느끼는가 |
| --- | --- |
| 내부 개발자 | 처음으로 Agent 하나보다 큰 일을 정의합니다. 분기와 병렬을 가진 Workflow 를 올리고 실행 상태를 봅니다 |
| 운영자 | 멈춘 Workflow 를 보고 **왜** 멈췄는지 구별합니다 — 도구 대기인지 승인 대기인지. 승인 대기 목록이 운영 업무가 됩니다 |
| 승인자(사람) | **처음으로 자동화 중간에 개입합니다.** 승인 전에는 다음 노드가 돌지 않고, 승인한 사실이 자기 이름으로 남습니다 |
| 보안·컴플라이언스 검토자 | 승인 기록이 조회 가능해집니다. 다만 **승인자 권한 모델은 이번 범위가 아닙니다**(Trust Layer, Phase 8) — 그 공백이 무엇을 뜻하는지는 아래 열린 질문 5 가 다룹니다 |
| 에이전트(하네스) | Workflow Run 이 생기면서 "여러 단계를 거친 일이 끝났는가" 를 판정할 수 있는 첫 대상이 생깁니다. 평가 task 를 더하는 것은 이번 범위가 아닙니다 |
| 최종 사용자 | 없습니다. `apps/web` 은 이번 Phase 에도 Workflow 화면을 얻지 않습니다(Phase 5) |

## Affected Systems

[../docs/architecture.md](../docs/architecture.md) 2절의 계층 이름으로 적습니다.

| 계층 / 패키지 | 어떤 영향 |
| --- | --- |
| Workflow `packages/workflow` | **비어 있던 껍데기가 처음 채워집니다.** 그래프·노드·간선의 도메인 타입과 검증, Workflow Version(불변), 실행 유스케이스, Run 생성·대기의 outbound 포트 |
| Agent Runtime `packages/runtime` | AGENT 노드가 쓰는 Run 생성·관찰 경로. **역참조가 생기지 않는 것**이 이 Phase 의 판정 대상입니다. 승인 대기를 어떻게 표현하든 `RunStatus` 와 그 전이표에 닿습니다 |
| Control Plane `apps/api` | Workflow 정의·버전 경로, Workflow Run 요청·조회, **승인 API**. 승인은 보안에 닿으므로 사람 검토를 거칩니다(DP-6) |
| `apps/worker` | Workflow Run 의 실행 자리. 노드 하나가 Agent Run 을 기다리는 동안의 점유 모델이 함께 결정됩니다(열린 질문 3) |
| 데이터 모델 | Workflow 정의·Version·Run 상태·노드 실행 기록·**승인 기록**의 저장 위치. `control` / `data` 중 어디인지가 함께 결정됩니다(열린 질문 4·5) |
| MCP `packages/mcp` | TOOL·MCP 노드가 Gateway 를 지납니다. 새 호출자가 생기는 것이고 Gateway 자체는 바뀌지 않습니다 |
| `packages/sdk` | 새 경로의 생성 타입과 호출 함수 |
| 아키텍처 규칙 | **AR-3 의 문구와 `.importlinter` 계약에 `aether_workflow` 가 들어갑니다.** `.importlinter` 는 보호 파일이라 사람이 커밋합니다 |
| `docs/domain.md` | `Workflow`·`Node`·`Approval` 정의가 더해집니다(열린 질문 6) |

의존 방향에서 새로 실제 효력을 갖는 것은 **workflow → runtime 단방향**입니다. Phase 2 의 AR-6 과 Phase 3 의 AR-3 이 그랬듯, 코드가 생기면서 비로소 발화합니다. 다만 그 둘과 다른 점이 있습니다 — **AR-6·AR-3 은 계약이 미리 있었고 공허하게 통과하고 있었던 반면, 이 방향은 계약 자체가 없습니다.** 그래서 이번에는 "공허한 계약을 깨우는" 것이 아니라 **계약을 만드는** 일이 포함됩니다.

## Constraints

- **오프라인이 기본입니다.** Workflow 실행·분기·대기·승인이 인터넷 없이 동작해야 합니다(DP-4). WEBHOOK·SCHEDULE 노드를 범위에서 뺀 이유가 이것입니다(인바운드 네트워크와 스케줄러).
- **승인은 보안에 닿습니다.** 승인 API·승인 기록·재개 경로는 사람 검토로 에스컬레이션합니다(DP-6, [../AGENTS.md](../AGENTS.md) Trust). 에이전트가 승인 판정 로직을 혼자 결정하지 않습니다.
- **Workflow Version 은 불변입니다.** `Agent Version` 과 같은 규칙입니다 — 실행 중인 Workflow Run 의 정의가 바뀌지 않아야 사후에 "무엇이 돌았는가" 를 복원할 수 있습니다.
- **루프에는 상한이 필수입니다.** 상한 없는 루프를 정의할 수 있게 두지 않습니다. 무한 루프는 오프라인 단일 노드 배포에서 복구가 사람 손입니다.
- **`workflow → runtime` 단방향.** 역참조를 만들지 않고, 그것을 `.importlinter` 계약으로 막습니다.
- **노드 출력은 데이터입니다.** 이전 노드의 출력이 다음 노드의 **지시**로 해석되는 경로를 만들지 않습니다 — Phase 2 의 `Observation`(spec 0002 D-6)과 Phase 3 의 검색 결과(spec 0004 D-8)와 같은 취급입니다. CONDITION 의 판정도 모델에게 묻지 않고 코드가 합니다.
- **본문을 span·로그·감사에 남기지 않습니다.** Phase 3 의 D-11 과 같은 선입니다. 노드 출력이 커질 수 있으므로 크기 한계가 필요합니다(열린 질문 7).
- **하위 호환**: Phase 1~3 의 HTTP 계약과 `Agent Version` 불변 규칙, 기존 Run 경로의 결과는 깨지지 않습니다. `RunStatus` 에 손을 대는 경우 기존 전이가 모두 그대로 성립해야 합니다.
- 비밀값을 코드·로그·커밋·span 에 남기지 않습니다.
- **verify 예산**: 합계 10분(spec 0001 D-12). 2026-10-12 실측으로 `--full` 이 507.6초이고 **여유가 92초(15%)** 입니다. Workflow 통합 테스트와 smoke 시나리오가 그 여유를 먹습니다 — 넘으면 선택 실패로 집계되고, 임계 조정은 사람이 합니다(EI-2).
- 기간은 Week 13~16 이고 반복·중단 예산은 [../harness/rules/loop-budget.rule.md](../harness/rules/loop-budget.rule.md) 가 소유합니다.

## Open Questions

| # | 질문 | 누가 답하는가 | 언제까지 |
| --- | --- | --- | --- |
| 1 | **Workflow Run 의 상태 모델을 Agent Run 과 공유할 것인가 별도로 둘 것인가.** 공유하면 전이표·투영·SSE 를 재사용하지만 두 종류의 "Run" 이 한 표에 섞여 조회와 권한이 복잡해집니다. 별도로 두면 깨끗하지만 이벤트·취소·trace 를 한 벌 더 만들어야 합니다 | 사람 | spec 0005 |
| 2 | **승인 대기를 `waiting` 으로 둘 것인가 새 상태를 만들 것인가.** `waiting` 은 이미 도구 호출 대기에 쓰이고 있습니다(`execute_run.py` 672행). 같은 값에 사유 필드를 더하는 방식과 새 상태 값을 더하는 방식이 있고, 후자는 마이그레이션 0001 의 `data.run_execution_status` enum 과 전이표를 건드립니다 | 사람 | spec 0005 |
| 3 | **AGENT 노드가 Agent Run 의 완료를 어떻게 기다리는가.** 지금 있는 수단은 `GET /runs/{id}` 폴링과 SSE 뿐입니다. 폴링은 단순하지만 지연과 부하가 있고, 이벤트 소비는 빠르지만 Workflow 실행기가 Run 이벤트 스트림의 소비자가 되어 결합이 늘어납니다. **기다리는 동안 worker 슬롯을 점유할 것인가**(단순하지만 Workflow 하나가 다른 Run 을 굶김)도 같은 질문입니다 | 사람 | spec 0005 |
| 4 | **Workflow 정의·Version·Run 상태를 `control` 과 `data` 중 어디에 두는가.** Phase 1~3 의 선례는 정의가 `control`, 실행 부산물이 `data` 입니다(마이그레이션 0001 의 역할·GRANT). 노드 실행 기록이 어느 쪽인지는 양이 결정할 수 있습니다 | 사람 | spec 0005 |
| 5 | **승인자 권한 모델이 없는 동안 v1 은 무엇으로 대체하는가.** 권한 모델은 Trust Layer(Phase 8)입니다. 그때까지 "인증된 주체 누구나 승인 가능" 으로 두면 승인이 형식만 남고, 반대로 승인자 목록을 Workflow 정의에 박으면 Phase 8 에서 이전해야 합니다. **그 공백을 기록으로 메울 것인지**(누가 승인했는지만 남기고 누가 승인할 수 있는지는 묻지 않음)가 결정입니다 | 사람 | spec 0005 |
| 6 | **`docs/domain.md` 에 `Workflow`·`Node`·`Approval` 을 이번에 정의할 것인가.** Phase 3 은 문서의 정의에 코드를 붙였고, Phase 4 는 정의가 없습니다. 코드를 먼저 쓰면 용어가 구현에서 역산되고, 문서를 먼저 쓰면 아직 안 만든 것을 정의하게 됩니다. 어느 시점에 누가 쓰는지를 정해야 합니다 | 사람 | spec 0005 |
| 7 | **노드 사이로 흐르는 출력의 모양과 한계.** CONDITION 이 "이전 노드 출력" 으로 분기한다면 그 출력의 타입(문자열 / 구조화된 값)과 크기 한계가 필요합니다. 한계가 없으면 Workflow Run 하나가 모델 출력 전체를 영속하게 되고, D-11(본문을 span·기록에 넣지 않습니다)과도 부딪힙니다 | 사람 | spec 0005 |
| 8 | **`aether_workflow` 의 방향 계약을 AR-3 에 넣을 것인가 새 AR 로 둘 것인가.** AR-3 은 지금 "mcp 와 context 는 runtime 을 import 하지 않는다" 입니다. workflow 는 방향이 반대(workflow → runtime)라 같은 계약에 넣으면 이름과 내용이 어긋납니다. `.importlinter` 와 `docs/architecture.md` 를 함께 고치는 일이고 **`.importlinter` 는 보호 파일**입니다 | 사람 | spec 0005 |

## Non-goals

**나중에 할 것.**

- **WEBHOOK·SCHEDULE 노드** — 인바운드 네트워크와 스케줄러가 필요해 오프라인 MVP 시나리오 밖입니다([mvp-backlog.md](mvp-backlog.md) 가 Public Beta 전으로 미뤘습니다).
- **Workflow 편집 UI 와 시각화** — Phase 5(Visual Agent Builder). 이번 Phase 는 정의를 API 로만 받습니다.
- **승인 알림**(메일·메신저·푸시) — 승인 대기 사실을 조회할 수는 있지만 알리지는 않습니다.
- **승인자 권한 모델** — Trust Layer(Phase 8). 열린 질문 5 가 그 공백을 어떻게 다룰지 묻습니다.
- **분산 실행·수평 확장** — 노드를 여러 worker 에 흩뿌리는 것은 범위 밖입니다. 병렬은 한 worker 안의 병렬입니다.
- **노드별 재시도 정책의 세분화** — Run 수준의 재시도(P1-7)를 그대로 씁니다.
- **Workflow 의 평가 task** — 평가 세트에 "여러 단계를 거친 일" 을 더하는 것은 Phase 7(제품 Evaluation)과 하네스 평가 쪽 결정입니다.
- **Workflow 정의의 마이그레이션·버전 호환** — Version 은 불변이고 이전은 하지 않습니다.

**아예 하지 않을 것.**

- **상한 없는 루프를 정의할 수 있게 두는 것.**
- **CONDITION 의 분기를 모델에게 묻는 것** — 분기는 코드가 판정합니다. 모델이 제어 흐름을 정하면 같은 입력이 다른 경로를 타고, 그것은 테스트할 수 없습니다.
- **이전 노드의 출력을 다음 노드의 system 지시로 올리는 경로.**
- **승인을 에이전트가 대신하는 경로** — "승인 자동화" 는 승인의 부정입니다. 사람이 승인하지 않으면 멈춘 채로 둡니다.
- **`workflow → runtime` 의 역참조.**

## 근거

- 로드맵 9장(Phase 4 — Workflow Engine, Week 13~16)과 [mvp-backlog.md](mvp-backlog.md) 의 P4-1 ~ P4-5. 등급 판정은 [../docs/roadmap.md](../docs/roadmap.md) 1절.
- intent [0004](0004-phase-3-context-compiler.md) 완료(2026-10-10). Phase 3 의 Proposed Outcome 전부가 병합되어 이 Phase 의 전제(도구를 부르는 Agent, 예산 안에서 조립되는 Context)가 성립합니다. 실행형 사람 몫도 2026-10-12 에 끝났습니다([../docs/step_results/phase-3.md](../docs/step_results/phase-3.md)).
- 관측된 사실(2026-10-12 확인): `packages/workflow` 구현 0행·tests 없음, `.importlinter` 에 workflow 방향 계약 0건, `docs/domain.md` 에 `Workflow` 정의 없음, `RunStatus.WAITING` 이 도구 대기에 선점됨, 마이그레이션에 workflow 표 없음, Run 완료를 기다리는 수단이 폴링·SSE 뿐, 사람 개입이 P1-7 에서 Phase 4 로 미뤄진 뒤 방치됨.
- [../docs/architecture.md](../docs/architecture.md) 의 DP-4(오프라인)·DP-6(보안은 초기부터)과 AR-5·AR-6. 승인 경로가 DP-6 에 걸리는 첫 제품 기능입니다.

### 로드맵의 하네스 칸 하나는 이미 지났습니다

로드맵 Phase 요약표는 Phase 4 의 하네스 항목을 "AD-3: `improvement-log/` 실운영 시작" 으로 적습니다. 그런데 `improvement-log/` 는 이미 **61건**이 쌓여 있고 Phase 0 부터 실운영 중입니다([../improvement-log/README.md](../improvement-log/README.md)). 즉 이 칸은 Phase 4 를 기다리지 않고 먼저 지나갔습니다.

이 사실을 적어 두는 이유는 로드맵을 고치자는 것이 아닙니다 — **이 Phase 에 하네스 쪽 새 할 일이 로드맵 기준으로는 없다**는 뜻이고, 그러면 이 Phase 의 하네스 작업은 "Workflow 때문에 필요해진 것"(방향 계약, 통합 테스트, 예산 재판정)뿐입니다. 로드맵의 등급은 [../docs/roadmap.md](../docs/roadmap.md) 1절이 정하므로 표 자체는 건드리지 않습니다.
