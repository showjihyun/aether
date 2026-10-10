# Phase 1 — Agent Runtime (완료 2026-09-16)

단위 열 하나(P1-1 ~ P1-9, P1-2 와 P1-5 는 둘로 쪼갬). intent [0002](../../intents/0002-phase-1-agent-runtime.md) · spec [0002](../../specs/0002-phase-1-agent-runtime.md) · plan [0002](../../plans/0002-phase-1-agent-runtime.md).

그림: [diagrams/phase-1.html](diagrams/phase-1.html)

## 무엇이 생겼는가

| 단위 | 생긴 것 |
| --- | --- |
| P1-1 | `POST /agents`, `GET /agents`, `GET /agents/{id}`. 생성 시 `Agent Version` 1 이 함께. 수정은 새 Version, 이전 Version 불변 |
| P1-2a | 루트 pytest·mypy 설정, `conftest.py`, `tests/support/{pg,waiting}.py`, `pytest-socket`, 마이그레이션 0002, `tests/arch/test_no_sleep_in_tests.py`(AST) |
| P1-2b | `Run` 상태 기계(`queued → running → (waiting) → succeeded/failed/cancelled/timed_out`), `State` 영속(`data.run_states`), `Task` 모델, 실행 권한 **lease**, `AgentDefinition`, `RunStateStore` 포트와 fake·PostgreSQL 계약 테스트 |
| P1-3 | Model gateway 한 인터페이스(`complete`·`stream`·`embed`)와 어댑터 둘 — fake, OpenAI-호환 HTTP |
| P1-4 | Planner/Executor 루프: Model → 도구 결정 → Tool → `Observation` → Model → Result. 프로세스 내부 도구 둘 |
| P1-5a | worker 가 `aether:runs:requested` 를 집어(자기 PEL 먼저, `XAUTOCLAIM`, `count=1`) `ExecuteRun` 을 부르고 ack. Redis `EventSink`·`StatusNotifier`, PostgreSQL `RunDeclarationReader`, heartbeat healthcheck |
| P1-5b | `POST /agents/{id}/run` → `control.runs` 선언 → `202`. `GET /runs/{id}`(투영만), `POST /runs/{id}/cancel`. api 안의 `aether:runs:status` 소비자가 `seq` 로 멱등 투영 |
| P1-6 | Run 이벤트 SSE. 이벤트 스키마 고정 |
| P1-7 | Run 타임아웃 → `timed_out`. 재시도 정책(횟수·백오프)을 `Agent Version` 에 저장. 오류 분류 |
| P1-8 | OpenTelemetry span 트리(Run → Task → 모델/도구 호출), compose 의 collector, 응답의 `trace_id` |
| P1-9 | `scripts/smoke.sh` 와 `smoke` 단계 활성화. Run 생성 P95 를 **사람이** 고정 |

## 왜 그렇게 했는가

- **Control Plane 은 선언만 합니다**(spec 0001 R-7 의 연장). api 가 worker 를 호출하지 않고 Redis Stream 에 선언을 넣습니다 — 그래서 worker 가 죽어도 선언은 남고, 재개가 같은 선언을 다시 집습니다.
- **한 Run 은 한 worker 만**(R-15) — lease 로 고정했습니다. 두 worker 가 같은 Run 을 돌리면 상태 전이가 뒤섞이고 그 버그는 재현되지 않습니다.
- **종결 알림은 반드시 도달합니다**(R-16). 커밋 뒤 발행 사이에 죽어도 재개가 재발행하고, 소비자는 `seq` 로 멱등합니다.
- **테스트는 결정적입니다**(R-11). 시간·난수·모델은 주입하고 `sleep` 으로 기다리지 않습니다 — 그 규칙을 자연어가 아니라 AST 테스트(`tests/arch/test_no_sleep_in_tests.py`)로 뒀습니다.
- **`Observation` 은 신뢰 경계 밖 데이터로 표시해 넣습니다**(R-14, D-6) — `[observation tool=… trust=untrusted]` 표지와 `role: tool` 메시지로만. 이 결정이 Phase 3 의 Knowledge 블록이 따를 선례가 됩니다.

## 하네스 근거

| 줄 | 내용 |
| --- | --- |
| **요구** | spec 0002 R-1 ~ R-16. 핵심은 R-2(선언 → 실행 → 종결) · R-3(SSE 순서) · R-4(주입된 시계로 결정적) · R-6(네트워크 없이 통과) · R-11(결정성) · R-12(계약이 구현보다 먼저) · R-14(신뢰 경계) · R-15(단일 실행자) · R-16(종결 알림 도달) |
| **결정** | D-1(모델 게이트웨이 인터페이스) · D-6(`Observation` 표지) · D-10(lease) · D-18(테스트 도구 설정) |
| **단계** | 이 Phase 가 `smoke` 를 켰습니다(P1-9). 제품 단계 10 → 11 |
| **증거** | 각 단위의 PR. `{{성능_기준}}` 은 사람이 고정했습니다(EI-2 — 임계값은 사람 소유) |
| **후보** | 하네스 도입 단계는 AD-2 로 진행 중이었습니다. 이 Phase 의 관측은 `improvement-log/` 의 2026-09-* 항목 |

## 정한 것과 다른 점

- 2026-09-12 plan 리뷰로 **P1-2 → P1-2a·P1-2b**, **P1-5 → P1-5a·P1-5b** 로 쪼갰습니다. 범위의 합은 불변이고, 반복 예산 8회 안에 끝내기 위한 분할입니다.

## 남긴 것

- 도구는 아직 프로세스 내부 함수입니다 — MCP 로 옮기는 것은 Phase 2(P2-3).
- `/embeddings` 가 채팅 모델 id 를 보내고 있었습니다. 이 결함은 Phase 3(P3-2a)에서 드러나 고쳐졌습니다 — 적재가 없던 동안에는 아무도 그 경로를 부르지 않았습니다.
