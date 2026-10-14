# Plan 0005 — Phase 4: Workflow Engine

| 키 | 값 |
| --- | --- |
| 번호 | 0005 |
| 근거 spec | [../specs/0005-phase-4-workflow-engine.md](../specs/0005-phase-4-workflow-engine.md) (승인됨 2026-10-12, R-1 ~ R-15 · D-1 ~ D-16) |
| 근거 intent | [../intents/0005-phase-4-workflow-engine.md](../intents/0005-phase-4-workflow-engine.md) (승인됨 2026-10-12) |
| 작업 단위 | [../intents/mvp-backlog.md](../intents/mvp-backlog.md) P4-1 ~ P4-5 (P4-2 → **2a·2b** 로 분할) |
| 작성일 | 2026-10-13 |
| 상태 | 승인됨 |
| 승인 | showjihyun, 2026-10-13 |

spec 이 정한 요구사항(R-1 ~ R-15)·결정(D-1 ~ D-16)은 반복하지 않습니다. 이 문서는 여섯 단위를 어떤 순서로 하고, 단위마다 어느 파일을 누가 만들며, 무엇으로 판정하는지를 정합니다. 표기 — **A** 에이전트(`implementer`), **M** 주 세션, **H** 사람(보호 파일·보안 검토).

이 plan 이 풀어야 하는 문제는 다섯입니다.

1. **판정 없는 통로를 main 에 남기지 않습니다.** Phase 2 에서 권한 판정(P2-4)을 Gateway(P2-2b) **앞**에 둔 것과 같은 규칙입니다. Phase 4 에서 그 자리에 있는 것은 **파킹**입니다 — 대기하면서 worker 슬롯을 쥐는 실행기가 한 번이라도 main 에 들어가면 그것이 spec D-4 가 금지한 설계이고, R-7 이 그것을 판정합니다. 그래서 **P4-2 를 2a(파킹과 재개)·2b(노드 출력과 CONDITION)로 쪼개고 2a 를 먼저** 합니다.
2. **마이그레이션은 한 번에 갑니다.** spec 2.9 의 다섯 표를 **전부 마이그레이션 0005 하나**로 P4-1 에서 만듭니다. `control.workflow_approvals` 는 쓰는 단위가 P4-4 이지만 표는 여기서 만듭니다 — 평면·역할·GRANT 검토가 한 번의 위험 표면이고, Phase 2 가 같은 선택을 했습니다(마이그레이션 0003 이 P2-4 의 `control.tool_permissions` 를 함께 만들었습니다).
3. **확신이 가장 낮은 결정을 자기 PR 로 분리합니다.** 노드 출력(D-8)은 spec 이 스스로 "새 제품 표면" 이라 적고 되돌리는 조건을 C-3 에 둔 결정입니다. 상태 기계(2a)와 섞으면 되돌릴 때 둘이 함께 뜯깁니다. **P4-2b 가 그 결정의 PR** 입니다.
4. **Phase 를 정의하는 시나리오를 먼저 초록으로 만듭니다.** backlog 의 Phase 완료 판정과 R-4 는 `START → AGENT → CONDITION → HUMAN → AGENT → END` 이고 거기에 PARALLEL·LOOP·WAIT 가 **없습니다.** 그래서 **P4-4(승인)를 P4-3 앞**에 둡니다. P4-4 는 🔒 이고 사람 검토(DP-6)가 필요하므로 뒤로 밀수록 그 검토가 Phase 끝에 몰립니다.
5. **verify 예산의 여유가 15% 뿐입니다**(spec 2.12·C-6). 단계를 늘리지 않고 `smoke` 도 건드리지 않으므로, 늘어나는 것은 `api-integration` 의 testcontainers 시간입니다. **단위마다 `--full` 소요를 기록**하고(4절), 넘으면 선택 실패로 집계해 사람이 봅니다. 에이전트가 임계를 올리지 않습니다(EI-2).

## 1. 순서

| Wave | 단위 | 왜 이 자리인가 | 사람 손 |
| --- | --- | --- | --- |
| 0 | (완료) `.importlinter` **AR-13** 신설 + AR-3 에 `aether_memory` | 계약을 먼저 세우면 첫 workflow 코드가 처음부터 위반할 수 없습니다(spec D-10) | **완료** — PR #144, 2026-10-12 |
| 1 | **P4-1** 그래프·검증·마이그레이션 0005(다섯 표)·정의 API | 표와 불변 Version 이 없으면 뒤가 전부 멈춥니다. 검증은 DB 없는 순수 함수 | — |
| — | (경계) | `docs/domain.md` 의 Workflow 용어 — 타입이 실재하는 **P4-1 병합 커밋에서** 채웁니다(spec D-7) | **M** |
| 2 | **P4-2a** 실행기 골격 · AGENT 노드 · **파킹과 재개**(스위퍼·멱등) | 문제 1. 대기가 슬롯을 놓는 것(R-7)·재시작 이어 실행(R-6)·멱등(R-8)이 이 단위의 전부 | — |
| 3 | **P4-2b** 노드 출력(8 KiB) · CONDITION 분기 | 문제 3. 되돌릴 수 있게 자기 PR 로 | — |
| 4 | **P4-4** 🔒 HUMAN / APPROVAL | 문제 4. 여기서 R-4(Phase 완료 시나리오)가 성립합니다 | **H-1** 보안 검토(DP-6) |
| 5 | **P4-3** PARALLEL / JOIN / LOOP / WAIT | 앞의 실행기 위에 노드 종류를 더하는 일. 판정은 전부 `api-unit` | — |
| 6 | **P4-5** LLM / MCP / TOOL 노드 | 같은 모양. 통로(AR-5·AR-6)를 지나는 것이 판정의 핵심 | — |

P4-2 를 2a·2b 로 쪼갠 것과 **P4-4 를 P4-3 앞에 둔 것**이 backlog 번호 순서와 다릅니다. 근거는 1절 문제 1·3·4 이고, backlog 의 행과 순서 메모는 **M** 이 이 plan 승인과 같은 커밋에서 고쳤습니다(2026-10-13).

**Wave 5·6 은 서로 독립입니다**(P4-3 과 P4-5 는 같은 파일을 거의 건드리지 않습니다). 그래도 **동시에 돌리지 않습니다** — `verify.sh` 는 락이 동시 실행을 막고(`2026-10-03-001`), 두 위임 세션이 번갈아 기다리면 벽시계가 오히려 늘어납니다.

## 2. 단위별 계획

모든 단위는 **red(실패하는 테스트, 실행해 기록) → green → refactor** 순서입니다. `ModuleNotFoundError` 하나로 여러 단언을 갈음하지 않습니다 — 모듈이 생긴 뒤에도 각 단언이 **자기 이유로** 한 번은 실패하는 것을 보여야 합니다(Phase 2 P2-2b 에서 세운 기준). 단위마다 브랜치 하나(`p4-1-workflow-model`), PR 하나, 커밋 trailer `Unit: P4-1`.

### P4-1 그래프·검증·마이그레이션 0005·정의 API (A, 문서는 M)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `packages/workflow/src/aether_workflow/domain/` — 노드 종류 열 11개(spec D-14), 간선, `WorkflowVersion`(불변), **검증 순수 함수**(spec 2.2 의 여섯 거부, 각각 다른 사유). `application/ports/inbound/` 의 정의 유스케이스 |
| 만드는 것(DB) | `apps/api/migrations/versions/0005_*.py` — spec 2.9 의 **다섯 표 전부**(`control.workflows`·`control.workflow_versions`·`control.workflow_runs`·`control.workflow_approvals`·`data.workflow_node_executions`)와 GRANT. Workflow Run 상태는 **새 enum**(spec 2.3) — `data.run_execution_status` 를 건드리지 않습니다 |
| 만드는 것(API) | `POST /workflows`·`GET /workflows/{id}`·`PUT /workflows/{id}`(새 Version)·`GET /workflows/{id}/versions/{n}`. `packages/sdk/openapi.json` 과 생성 타입(**추가 변경만**, 기존 경로 0개) |
| 판정 | `api-unit`: 여섯 거부가 **각각 구별되는 사유**(R-1·R-3). 같은 정의를 두 번 직렬화해 바이트 동일(R-2 의 절반). `api-integration`: 잘못된 그래프 `POST` 가 4xx(R-1), `PUT` 로 Version 2 를 만들어도 Version 1 의 노드·간선이 바이트 단위로 같음(R-2), 빈 DB 에서 0005 up/down 왕복, `aether_control` 로 `data.workflow_node_executions` 접근이 permission denied |
| 주의 | 검증 함수는 I/O 를 하지 않습니다(AR-9). `aether_workflow` 는 이 단위에서 `aether_runtime` 을 **import 하지 않습니다** — AR-13 은 반대 방향이지만, 지금 역방향을 만들 이유도 없습니다 |
| M | `docs/domain.md` 에 `Workflow`·`Workflow Version`·`Workflow Run`·`Node`·`Node Execution`·`Approval` 절 — 실행자는 용어 초안만 보고에 넣고, **M 이 병합 커밋에서** 씁니다(spec D-7) |

### P4-2a 실행기 골격 · AGENT 노드 · 파킹과 재개 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `aether_workflow` 의 실행 유스케이스 — 요청 스트림에서 Workflow Run 을 집고(Agent Run 과 **다른 스트림**), lease 를 걸고, 노드를 하나 전진시키고, 상태를 영속. outbound 포트 `AgentRunLauncher`(Agent Run 생성·관찰) 선언 |
| 만드는 것(파킹) | `waiting_run` 파킹 — 상태와 "무엇을 기다리는가" 만 남기고 **lease 를 놓습니다**. 재개 경로 둘: `run.finished` 이벤트 소비 → 재큐, 그리고 **스위퍼**(`waiting_run` 인데 자식 Run 이 이미 터미널인 건을 주워 재큐). `AETHER_WORKFLOW_SWEEP_INTERVAL_SECONDS` 기본 **30**(spec 2.11 이 plan 에 맡긴 값) |
| 만드는 것(이벤트) | `workflow.status`·`node.started`·`node.finished`·`workflow.finished` — **자기 어휘**(spec D-13). Agent Run 의 이벤트 계약에 섞지 않습니다 |
| 조립 | `apps/worker/src/aether_worker/main.py` 가 `AgentRunLauncher` 를 `aether_runtime` 으로 꽂습니다(AR-10). Phase 3 의 `ModelGatewayEmbedder` 와 같은 자리 |
| 판정 | `api-integration`: 노드 하나를 마친 뒤 worker 를 죽이고 다시 띄워 END 도달, 마친 노드의 실행 기록이 **1건**(R-6). `waiting_run` Workflow Run 을 worker 동시성 한도만큼 만든 뒤 평범한 Agent Run 하나가 정상 처리되고 대기 Run 의 lease 가 비어 있음(R-7). `run.finished` 를 **소비하지 않은** 상태에서 스위퍼만으로 재개되는 것 1건. `api-unit`: 같은 깨우는 신호를 두 번 넣어도 노드가 한 번만 전진(R-8), 종결 상태에서 나가는 전이가 거부됨, `waiting_run` 값이 조회에 나타남(R-13 의 절반) |
| 주의 | **이벤트만 믿지 않습니다**(spec 2.5). 스위퍼 없는 구현은 반려 사유입니다 — 그 실패를 하네스에서 세 번 겪었습니다(`2026-10-11-001`). 전진은 "현재 노드가 이 노드이고 상태가 이 대기값일 때만" 입니다 |

### P4-2b 노드 출력 · CONDITION (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | 노드 출력 — JSON 객체, **8 KiB 상한**(`AETHER_WORKFLOW_NODE_OUTPUT_MAX_BYTES`, 기본 8192), 자르면 **잘렸다는 사실을 함께 기록**. `AGENT` 노드의 출력은 자식 Run 의 마지막 assistant 본문을 상한까지 자른 것 + 종결 상태 |
| 만드는 것 | `CONDITION` — **선언된 필드 경로 + 선언된 연산자**(`equals`·`not_equals`·`contains`·`gt`·`lt`·`exists`). 임의 표현식을 평가하지 않고 모델에게 묻지 않습니다(spec D-9) |
| 판정 | `api-integration`: 같은 Workflow 를 두 입력으로 돌려 **다른 경로**를 타고 지난 노드 목록이 다름(R-5). `api-unit`: 상한 + 1 바이트 출력이 잘리고 잘림 표시가 남음, 없는 필드 경로를 가리킨 CONDITION 이 `exists` 에서 거짓이고 다른 연산자에서는 **거부**(실행 실패, 조용한 거짓 아님), 출력이 **span·감사·보고에 나타나지 않음**(구조 테스트) |
| 주의 | **되돌릴 수 있게 둡니다**(spec C-3). 출력을 읽는 곳은 CONDITION 과 노드 실행 조회 **둘뿐**이어야 하고, 세 번째 소비자가 생기면 보고에 적습니다 |

### P4-4 🔒 HUMAN / APPROVAL (A, 설계·검토는 M·H)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `HUMAN`/`APPROVAL` 노드 → `waiting_approval` 파킹. 승인 API — **특정 노드 실행을 지목**해야 하고 그 실행이 `waiting_approval` 이 아니면 거부(정확성 가드). `control.workflow_approvals` 에 `approved_by`·`approved_at`·대상 노드 실행·선택 메모를 **append-only** 로. 조회 경로. 이벤트 `approval.requested`·`approval.granted` |
| 판정 | `api-integration`: 승인 없이 재개 요청 → 4xx, 승인 뒤 재개되어 END 도달, 승인 기록이 조회에 나옴, **대기가 아닌 노드 실행을 지목한 승인은 거부**(R-12). 승인 API 를 두 번 불러도 노드 실행 기록이 1건(R-8). `waiting_run` 과 `waiting_approval` 이 **상태만으로 구별**되고 Agent Run 의 `waiting` 값은 바뀌지 않음(R-13, 회귀). **`START → AGENT → CONDITION → HUMAN → AGENT → END` 전체 1건**(R-4) |
| 주의 | **승인자 권한 모델을 만들지 않습니다**(spec 2.6·C-4). "자기 승인 금지" 도 넣지 않습니다. 인증된 주체 누구나 승인할 수 있고, **그 공백은 의도된 것**이며 Phase 8 의 자리입니다. 그럴듯해서 더하는 반쪽 권한 판정이 이 단위의 반려 사유입니다 |
| H-1 | 승인 경로의 **코드·마이그레이션 사용·API 를 사람이 검토**합니다(DP-6, AGENTS.md Trust). 에이전트는 인터페이스와 테스트를 제안하고 거기서 멈춥니다 — 병합 전에 사람이 봅니다 |

### P4-3 PARALLEL / JOIN / LOOP / WAIT (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | `PARALLEL`→`JOIN` 합류(결과에 각 분기의 결과), `LOOP`(`max_iterations` 필수 — 검증은 P4-1 이 이미 거부합니다), `WAIT`(**주입된 시계**) |
| 판정 | `api-unit`: 두 분기가 모두 실행되고 합류 뒤 다음 노드가 **한 번** 실행됨, 한 분기를 실패시키면 합류 결과에 그 실패가 담기고 Workflow Run 이 `failed`(R-9). 상한 n 인 루프가 n+1 회에 `failed` + **상한 초과로 구별되는 사유**(R-10). 시계를 앞으로 돌려 대기가 끝나고 **테스트 소요가 대기 시간과 무관**(R-11) |
| 주의 | 병렬은 **한 worker 안**입니다(spec D-15). 분산·큐 분할을 만들지 않습니다. `WAIT` 가 실제 시간을 1초라도 기다리면 반려입니다 |

### P4-5 LLM / MCP / TOOL 노드 (A)

| 항목 | 내용 |
| --- | --- |
| 만드는 것 | Agent 를 거치지 않고 한 번 부르는 노드 셋. 포트 선언(`ModelInvoker`·`ToolInvoker`)과 **조립은 worker 의 `main`** — 모델은 `ModelGateway`(AR-5), 도구는 MCP Gateway(AR-6)를 지나고 감사도 그대로 남습니다 |
| 판정 | `api-arch`: `aether_workflow` 가 `httpx`·벤더 SDK·MCP 클라이언트 라이브러리를 import 하지 않음(R-14). `api-integration`: 세 노드가 각각 한 번씩 들어간 Workflow 가 END 도달하고 **도구 호출이 `data.tool_call_audit` 에 남음**(R-14) |
| 주의 | Gateway 를 우회하는 경로를 만들면 Firewall(Phase 10)이 관측하지 못합니다(DP-2). 통로를 새로 만들지 않고 있는 것을 지납니다 |

## 3. 사람 손

| 순간 | 언제 | 사람이 하는 일 |
| --- | --- | --- |
| (완료) | P4-1 **앞** | `.importlinter` AR-13 — **2026-10-12 완료**(PR #144, `harness-change` 라벨) |
| **H-1** | P4-4 병합 전 | 승인 경로의 코드·API·마이그레이션 사용을 검토합니다(DP-6). 에이전트가 넘기는 것: 인터페이스, 테스트, "권한 판정을 넣지 않았다" 는 명시, 그리고 R-12 의 red 증거 |
| **H-2**(Phase 뒤) | Phase 4 완료 후 | **D-8 되돌리기 판단**(spec C-3) — CONDITION 이 메타데이터만으로 충분했는지. 에이전트는 노드 출력의 실제 소비자 목록과 크기 분포를 보고에 넣고, 판단하지 않습니다 |
| 수동 확인 | P4-4 뒤 | compose 에서 승인 대기 → 승인 API → 재개 1회. `smoke` 에는 **넣지 않습니다**(spec D-16) |

`harness.config` 와 CI 워크플로는 바뀌지 않습니다(단계 수 불변, spec 2.12). **보호 파일 변경이 더 없습니다** — Phase 4 의 유일한 보호 파일 변경은 Wave 0 에서 끝났습니다. 새로 생기면 그때 부록으로 제안합니다.

## 4. 판정 절차

`TESTCONTAINERS_RYUK_DISABLED=true ./harness/scripts/verify.sh` 하나가 판정입니다(단계 수는 `harness.config` 가 소유합니다 — 여기 적지 않습니다). 로컬 기본은 `api-integration`·`smoke`·`bench` 를 미룹니다(`HARNESS_DEFERRED_STEPS`) — **Phase 4 의 판정은 그 미룬 단계에 몰려 있으므로 단위마다 `--full` 을 최소 1회** 돌립니다. 문서·기록만 고친 커밋은 `--changed` 로 좁힐 수 있습니다(`2026-10-04-001`).

**단위마다 보고에 적습니다**: `.harness/verify.json` 의 합계 ms 와 `api-integration` 단계의 ms. spec C-6 의 여유가 15% 뿐이므로 **증가분을 단위별로 보이게** 둡니다. 예산을 넘기면 선택 실패로 집계하고 사람이 봅니다 — **에이전트가 임계를 올리지 않습니다**(EI-2).

**단위별 추가 확인**(verify 가 아직 못 보는 것 — 보고에 "손으로 실행", 실행하지 않았으면 "미측정"):

| 단위 | 추가 확인 |
| --- | --- |
| P4-1 | 마이그레이션 0005 를 **되돌린 뒤 다시** 올려 1회. `\dp` 로 다섯 표의 GRANT 를 눈으로 |
| P4-2a | 스위퍼만으로 재개되는 것 1회(이벤트 소비를 끈 상태). 대기 Run 의 lease 열이 비는 것을 SQL 로 |
| P4-2b | 출력이 8 KiB 를 넘는 실제 응답 1회(로컬 LLM 으로 되면, 안 되면 사유) |
| P4-4 | compose 에서 승인 대기 → 승인 → 재개 1회 |
| P4-3 | `WAIT` 테스트의 벽시계 소요가 대기 시간과 무관한 것을 숫자로 |
| P4-5 | `data.tool_call_audit` 에 TOOL 노드의 호출이 남은 것을 SQL 로 1회 |

**보고에 반드시**: `red 증거`(각 단언이 자기 이유로 실패한 기록), 판정 명령 exit 표, verify 합계 ms, 미측정, spec/plan 과의 불일치, `docs/` 에 옮길 표 초안.

## 5. 예산과 중단

[../AGENTS.md](../AGENTS.md) Loop 와 `harness/rules/loop-budget.rule.md` 를 그대로 씁니다. 다른 것만 적습니다.

| 항목 | 값 |
| --- | --- |
| 쪼개기 | P4-2 는 **처음부터** 2a·2b. 포트에 메서드를 더하는 변경이 들어가면 그 fake 가 몇 곳인지 먼저 세십시오(`2026-09-28-001` — P2-6 에서 39개 테스트가 깨졌습니다) |
| 위임 기준 | 단일 파일·기계적 변경은 **주 세션이 직접**. 위임은 여러 파일에 걸친 기능 단위와 red→green 이 실제로 여러 번 도는 일에만(2026-10-04 결정). 여섯 단위 전부가 위임 대상이고 `docs/domain.md` 는 **M** |
| Docker | 마이그레이션 0005 는 기존 볼륨에 **얹힙니다**(이미지 교체 없음). 그래도 `down -v` 는 격리 프로젝트 이름(`-p`)에서만 |
| verify 동시 실행 | 금지됩니다(락이 막습니다, `2026-10-03-001`). Wave 5·6 이 독립이어도 동시에 돌리지 않습니다(1절) |
| 중단 조건 | P4-2a 에서 파킹이 성립하지 않으면(R-7 이 초록이 되지 않으면) **멈추고 보고**합니다. 대기가 슬롯을 쥐는 우회 구현을 만들지 마십시오 — 그것이 spec D-4 가 거부한 설계입니다 |
| 시간 예산 | 합계 10분(판정 명령). 넘으면 선택 실패로 집계되고 사람이 판단합니다 |

## 6. Phase 완료

backlog 의 Phase 4 완료 판정 + spec 0005 의 R-1 ~ R-15 전부가 통과하고 여섯 단위가 병합되면 완료입니다. R-15 는 **Wave 0 에서 이미 통과**했습니다(PR #144).

| 요구 | 어느 단위가 판정하는가 |
| --- | --- |
| R-1, R-2, R-3 | P4-1 |
| R-6, R-7, R-8, R-13(절반) | P4-2a |
| R-5 | P4-2b |
| R-4, R-12, R-13 | P4-4 |
| R-9, R-10, R-11 | P4-3 |
| R-14 | P4-5 |
| R-15 | **완료** — Wave 0 (PR #144) |

그때 **M** 이 하는 일: intent 0005 의 상태를 `완료` 로, [../intents/intent.md](../intents/intent.md) 의 활성 intent 를 다음 건(0006, MVP 통합)으로, backlog 의 Phase 4 상태 행, [../docs/roadmap.md](../docs/roadmap.md) 의 Phase 행. 그리고 H-2(D-8 되돌리기 판단)에 필요한 숫자를 모아 사람에게 넘깁니다.

## 부록 A — P4-2a 의 실행 설계 (2026-10-14, M)

2절의 P4-2a 표를 **대체하지 않고 좁힙니다.** 착수 전에 GRANT 를 실측해서 2절이 전제한 것 하나가 성립하지 않는 것을 확인했고(아래), 그 결과 이 단위가 만드는 것이 늘어났습니다. 늘어난 만큼 **PR 을 둘로 나눕니다** — 단위는 하나(`Unit: P4-2a`)이고 backlog 의 상태는 둘이 다 병합된 뒤에 `완료` 가 됩니다.

| PR | 범위 | main 에 남는 것 |
| --- | --- | --- |
| **A** 실행기 골격 | 마이그레이션 0006(`data.workflow_run_executions`), Workflow Run 시작·조회 API 와 상태 투영, `aether_workflow` 의 전진 유스케이스(`START`→`END`)와 lease, Workflow 자기 이벤트 어휘, worker 의 요청 소비자 | **대기가 전혀 없는** 실행기. 파킹이 없으므로 슬롯을 쥐는 경로도 없습니다(1절 문제 1 을 더 강하게 지킵니다) |
| **B** AGENT 노드와 파킹 | `AgentRunLauncher`(자식 Run 선언 요청), `waiting_run` 파킹과 lease 놓기, 재개 둘(`run.finished` 소비 + **스위퍼**), 멱등, `node_executions.status` enum 좁히기 | R-6·R-7·R-8 의 판정 |

**왜 나누는가.** 둘을 한 PR 에 넣으면 리뷰 한 번에 마이그레이션·API·실행기·파킹·스위퍼가 같이 들어오고, 그중 하나를 되돌리려면 전부 뜯어야 합니다. 1절 문제 1 의 금지선("대기하면서 슬롯을 쥐는 실행기")은 A 가 **대기 자체를 만들지 않으므로** 더 강하게 지켜집니다 — A 가 지원하는 노드 종류는 `START`·`END` 둘이고, 나머지 종류를 만나면 실행은 `failed` + 구별되는 사유로 끝납니다(절반만 만든 AGENT 노드를 두지 않습니다).

**전제가 틀린 것 하나 — 평면.** 2절은 "상태를 영속" 을 `control.workflow_runs` 로 읽히게 적었습니다. 그런데 실행기는 worker 이고 worker 의 역할(`aether_data`)은 `control` 에 **SELECT 뿐**입니다(마이그레이션 0001·0005 실측). GRANT 를 넓히는 선택은 하지 않습니다 — 평면 규칙(spec D-5)을 거스르고 권한 변경은 사람 검토 대상이며, [../docs/step_results/p4-1.md](../docs/step_results/p4-1.md) 가 이미 "P4-2a 가 이 자리에서 GRANT 를 넓히는 쪽으로 가지 않도록" 적어 두었습니다. 그래서 **spec 개정 2** 로 실행 상태를 `data` 에 두고 `control` 쪽을 투영으로 고정했습니다. 자식 Agent Run 의 선언도 같은 이유로 api 가 만듭니다.

| 이름 | 값 | 자리 |
| --- | --- | --- |
| 요청 스트림 | `aether:workflow_runs:requested` | api → worker (Agent Run 과 **다른 스트림**) |
| 상태 스트림 | `aether:workflow_runs:status` | worker → api (투영) |
| 자식 Run 선언 요청 | `aether:workflow:agent_runs:requested` | worker → api (**PR B**) |
| 실행 상태·lease | `data.workflow_run_executions` (마이그레이션 0006) | worker 가 씀 |
| 스위퍼 주기 | `AETHER_WORKFLOW_SWEEP_INTERVAL_SECONDS` 기본 **30** | **PR B** |

**B 가 만드는 것**(2026-10-14, A 병합 뒤 확정). 착수 전 실측으로 둘이 더 막혔고 spec **개정 3** 으로 적었습니다 — 노드에 **Agent 참조가 없었고**(그래서 `AGENT` 노드가 무엇을 실행할지 말할 수 없습니다), 깨우는 신호로 적힌 `run.finished` 는 **group 으로 받을 수 없는** per-run 스트림에 있습니다. B 도 두 물결로 나눕니다(PR 은 하나).

| 물결 | 범위 |
| --- | --- |
| **B1** | 노드의 `agent_id`·`agent_version`(검증·아홉 번째 거부·API·SDK), 자식 Run **선언**을 만드는 api 쪽 소비자와 멱등 `create`(주어진 id 로) |
| **B2** | 실행기의 `AGENT` 노드 — 자식 Run 의 Version 해석(`control.agent_versions` SELECT), 발사, `waiting_run` 파킹과 **lease 놓기**, 재개 둘(상태 통지 소비 + **스위퍼**), 멱등, 마이그레이션 0007(노드 실행 상태를 enum 으로 좁힘), R-6·R-7·R-8 |

**실행기가 Version 을 해석합니다** — api 가 아닙니다. worker 는 `control.agent_versions` 에 SELECT 가 있으므로(0001) `(agent_id, version)` 을 `agent_version_id` 로 풀 수 있고, 없으면 **노드를 실패**시킵니다. api 가 풀게 하면 없는 Agent 를 가리킨 노드가 **영원히 파킹**됩니다(api 는 독약 메시지를 ack 하고 끝낼 뿐이고, 그것이 `2026-10-11-001` 이 적은 "대기 장치의 침묵" 입니다). 그래서 api 쪽 소비자의 일은 기계적입니다 — 받은 id 로 `control.runs` 에 INSERT(멱등) 하고 `aether:runs:requested` 에 통지.

**A 에 넣지 않는 것**: 파킹, AGENT·CONDITION·그 밖의 노드 종류, 스위퍼, 취소 API, 노드 출력. 취소는 `control.workflow_runs.cancel_requested_at` 열이 이미 있지만 그것을 쓰는 API 가 없으므로 **A 에서도 만들지 않습니다**(Workflow 취소는 spec 2.3 이 허용한 전이이고, 넣을 단위는 backlog 가 정합니다 — 지금 열 하나 때문에 API 를 발명하지 않습니다).

## 관련 문서

- [../specs/0005-phase-4-workflow-engine.md](../specs/0005-phase-4-workflow-engine.md) — 요구사항·결정
- [../intents/mvp-backlog.md](../intents/mvp-backlog.md) — 단위의 범위
- [../docs/architecture.md](../docs/architecture.md) — AR-5·AR-6·AR-9·AR-10·**AR-13**
- [../docs/domain.md](../docs/domain.md) — P4-1 병합 커밋에서 Workflow 용어가 들어갈 곳
- [../improvement-log/2026-10-11-001.yaml](../improvement-log/2026-10-11-001.yaml) — 대기 장치의 침묵. spec 2.5 의 스위퍼가 이 교훈의 제품판입니다
- [../AGENTS.md](../AGENTS.md) — Loop, Trust, 반복 예산
