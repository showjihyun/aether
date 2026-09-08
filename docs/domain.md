# aether 도메인 용어

이 문서는 이름을 붙이거나 스키마를 정하기 전에 읽습니다. 같은 개념에 다른 이름을 붙이면 코드·API·문서가 서로 다른 제품을 설명하게 됩니다. 계층 구조는 [architecture.md](architecture.md) 가 소유하고, 여기서는 **용어의 뜻**만 고정합니다.

용어를 새로 만들기 전에 이 표에 이미 있는지 확인합니다. 없으면 추가하되, 추가할 때 대체하거나 삭제할 항목을 함께 정합니다.

## 1. 실행 (Agent Runtime)

| 용어 | 뜻 | 혼동하기 쉬운 것 |
| --- | --- | --- |
| `Agent` | 목표와 도구 집합과 정책이 묶인 실행 단위의 **정의**. 실행 중인 것이 아닙니다 | `Run` |
| `Agent Version` | 특정 시점의 `Agent` 정의를 고정한 불변 스냅숏. 재현 가능한 실행의 근거 | `Agent` |
| `Run` | `Agent Version` 하나를 실제로 한 번 실행한 **사건**. 취소·재시도·타임아웃의 대상. Control Plane 이 **선언**하고 Data Plane 이 **실행**하므로 기록은 Plane 마다 하나씩입니다 — 선언 `control.runs`, 실행 상태 `data.run_executions`([../specs/0001-phase-0-foundation.md](../specs/0001-phase-0-foundation.md) 2.8) | `Agent` |
| `Task` | `Run` 안에서 Planner 가 쪼갠 작업 단위 | `Run` |
| `State` | `Run` 의 현재 진행 상태. 재시작 후 이어붙일 수 있어야 합니다 | `Memory` |
| `Observation` | 도구 실행 결과가 모델에게 되돌아간 것. 신뢰 경계 밖에서 온 데이터입니다 | `Result` |
| `HITL` | Human-in-the-loop. `Run` 이 사람의 승인을 기다리며 멈추는 지점 | `Approval` |

## 2. 연결 (MCP)

| 용어 | 뜻 | 혼동하기 쉬운 것 |
| --- | --- | --- |
| `MCP Server` | 외부 시스템 하나를 도구로 노출하는 프로세스 | `Enterprise System` |
| `MCP Gateway` | 모든 도구 호출이 지나는 단일 통로. 인증·권한·검사·감사가 여기 걸립니다 | `MCP Client` |
| `MCP Firewall` | Gateway 안에서 요청·응답을 검사하고 차단하는 층(DLP 포함) | `Policy Engine` |
| `Tool` | Agent 가 호출할 수 있는 능력 하나. 스키마를 가집니다 | `Skill` |
| `Tool Discovery` | 연결된 MCP Server 로부터 사용 가능한 `Tool` 목록을 얻는 절차 | `Marketplace` |

## 3. 맥락 (Context Engine)

| 용어 | 뜻 | 혼동하기 쉬운 것 |
| --- | --- | --- |
| `Context` | 이번 모델 호출에 실제로 들어간 내용. 예산이 있는 자원입니다 | `Knowledge` |
| `Context Compiler` | 무엇을 `Context` 에 넣고 무엇을 뺄지 결정하는 구성 요소 | `RAG` |
| `Knowledge` | 문서·데이터에서 유래한, 조직이 소유한 사실 | `Memory` |
| `Memory` | 이전 실행에서 유래한, 에이전트가 남긴 경험. **검증 전에는 신뢰하지 않습니다** | `Knowledge` |
| `Skill` | 반복 절차를 고정한 지침 묶음. 코드가 아니라 절차입니다 | `Tool` |

`Memory` 와 `Knowledge` 를 한 저장소에 섞지 않습니다. 섞이면 검증되지 않은 경험이 사실로 승격됩니다. 같은 이유가 하네스 쪽에도 있습니다([../harness/rules/untrusted-experience.rule.md](../harness/rules/untrusted-experience.rule.md)).

## 4. 신뢰 (Trust Layer)

| 용어 | 뜻 | 혼동하기 쉬운 것 |
| --- | --- | --- |
| `Policy` | 무엇이 허용되는지에 대한 선언. 판정만 하고 실행하지 않습니다 | `Permission` |
| `Permission` | 특정 주체가 특정 자원에 대해 갖는 권한. `Policy` 판정의 입력 | `Policy` |
| `Approval` | 사람이 특정 `Run` 또는 도구 호출을 승인한 사건 | `HITL` |
| `Decision Provenance` | 어떤 입력·맥락·정책으로 그 결정이 나왔는지의 추적 가능한 기록 | `Audit` |
| `Audit` | 무슨 일이 일어났는지의 시간순 기록 | `Decision Provenance` |
| `Agent Passport` | Agent 의 신원·권한·이력을 담아 배포 경계를 넘길 수 있게 한 증명 | `Agent Version` |

## 5. 평가 (Evaluation)

제품의 `Evaluation` 과 하네스의 평가는 **다른 것**입니다. 이름이 같아 섞이기 쉬우므로 여기서 갈라 둡니다.

| 용어 | 뜻 | 어디에 있는가 |
| --- | --- | --- |
| `Evaluation`(제품) | 고객이 자기 Agent 의 품질을 측정하는 aether 의 기능 | Phase 7, `packages/evaluation` |
| 하네스 평가 | **우리가** aether 를 만드는 과정의 품질을 측정하는 것 | [../evaluation/README.md](../evaluation/README.md), `harness/scripts/eval.sh` |

## 6. 배포

| 용어 | 뜻 |
| --- | --- |
| `Deployment Mode` | Cloud / Private Cloud / On-Premise / Air-Gapped / Edge 중 하나 |
| `Control Plane` | 관리 평면. 무엇이 존재하는지를 선언합니다 |
| `Data Plane` | 실행 평면. 고객 데이터가 실제로 흐르는 곳 |
| `Offline Release Bundle` | 인터넷 없이 설치·갱신할 수 있게 묶은 산출물(Phase 11) |

## 관련 문서

- [architecture.md](architecture.md)
- [roadmap.md](roadmap.md)
- [../AGENTS.md](../AGENTS.md)
