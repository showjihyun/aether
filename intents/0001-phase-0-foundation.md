# Intent 0001 — Phase 0: Architecture & Foundation

| 키 | 값 |
| --- | --- |
| 번호 | 0001 |
| 작성일 | 2026-09-08 |
| 대상 Phase | [../docs/roadmap.md](../docs/roadmap.md) 의 Phase 0 (Week 1~2) |
| 상태 | 승인됨 |
| 승인 | showjihyun, 2026-09-08 |
| 후속 spec | 아직 없음 |

## Problem

aether 저장소에는 현재 하네스 번들과 문서만 있습니다. 실행할 수 있는 것이 없습니다. 관측된 사실은 다음과 같습니다.

- `./harness/scripts/verify.sh` 가 검사할 제품 코드가 없어, 검증 단계 전부가 하네스 자기 점검입니다. 즉 지금의 통과는 "하네스가 성립한다" 만 뜻하고 "제품이 동작한다" 는 뜻하지 않습니다.
- [../docs/architecture.md](../docs/architecture.md) 의 의존 방향 규칙 AR-1 ~ AR-7 은 자연어 문서(EL-2)로만 존재합니다. 지금 코드를 쓰기 시작하면 위반이 리뷰 이후에야 드러납니다.
- Cloud / On-Prem / Air-Gapped 를 같은 코드베이스로 지원한다는 전제가 아직 어떤 실행 가능한 제약으로도 표현되어 있지 않습니다.

## Proposed Outcome

Phase 0 이 끝났을 때 다음이 관측 가능합니다.

- 새로 합류한 사람이나 에이전트가 저장소 정보만으로 명령 하나를 찾아 실행하면 Web 과 API 가 뜹니다.
- `./harness/scripts/verify.sh` 가 제품 코드를 실제로 검사합니다. `harness.config` 의 "Phase 0 이후" 블록이 활성이고, self-check 단계와 제품 단계가 함께 집계됩니다.
- AR-1 ~ AR-7 중 최소 AR-2, AR-3, AR-5 가 `.importlinter` 와 `.dependency-cruiser.cjs` 로 옮겨져, 위반 시 `arch-test` 단계가 exit 0 이 아닌 값을 냅니다. 즉 EL-2 에서 EL-6 으로 올라갑니다.
- `docker compose up` 만으로 PostgreSQL, Redis, API, Web 이 인터넷 없이 기동합니다(DP-4 Offline-capable 의 첫 근거).
- CI(`.github/workflows/harness.yml`)가 깨끗한 체크아웃에서 verify 를 통과합니다.

## Affected Users

| 대상 | 무엇을 느끼는가 |
| --- | --- |
| 내부 개발자 | 저장소를 받아 한 명령으로 개발 환경을 띄웁니다 |
| 에이전트 | 실패를 스스로 관측할 피드백 채널(verify)이 생깁니다. 지금은 없습니다 |
| 운영자 | 아직 없습니다. Phase 0 은 외부 사용자에게 노출되지 않습니다 |
| 최종 사용자 | 없습니다 |

## Affected Systems

| 계층 / 패키지 | 어떤 영향 |
| --- | --- |
| `apps/web` | 신규. Next.js. Experience 계층의 껍데기만 |
| `apps/api` | 신규. FastAPI. Control Plane 의 껍데기와 기본 인증 |
| `apps/worker` | 신규. 비동기 실행 자리만 확보 |
| `packages/*` | 신규. `runtime`, `workflow`, `context`, `memory`, `mcp`, `policy`, `evaluation`, `sdk` 의 빈 경계. 구현은 Phase 1 이후 |
| `infra/docker`, `infra/kubernetes` | 신규. Compose 우선, K8s 매니페스트는 자리만 |
| `harness.config` | **보호 파일**. "Phase 0 이후" 블록의 주석을 풉니다 |
| `.importlinter`, `.dependency-cruiser.cjs` | 신규. AR-* 를 기계 판정으로 옮기는 자리 |

의존 방향 규칙에 걸리는 지점: `packages/*` 를 빈 경계로 먼저 만들면 내용이 없는 채 서로를 참조할 수 없으므로, AR-2·AR-3 은 이 시점에 위반 없이 고정할 수 있습니다. AR-5(모델 호출 단일 통로)와 AR-6(외부 접근은 MCP 경유)은 대상 코드가 없어 규칙만 등록하고 검사는 Phase 1~2 에서 실제로 걸립니다.

## Constraints

- **Modular Monolith 부터**(DP-5). Phase 0 에서 서비스로 쪼개지 않습니다. 경계는 패키지 경계로만 표현합니다.
- **Offline-capable**(DP-4). 부팅 경로에 외부 네트워크 호출을 넣지 않습니다. 이미지 pull 을 제외하면 인터넷 없이 기동해야 합니다.
- **Control Plane / Data Plane 분리**(AR-7). `apps/api` 가 Data Plane 저장소를 직접 읽는 경로를 만들지 않습니다. Phase 0 에서 만든 지름길은 Phase 14 까지 남습니다.
- **검증 게이트를 약화하지 않습니다.** 제품 단계를 켜면서 통과시키려고 `required` 를 `false` 로 내리거나 `HARNESS_THRESHOLD` 를 낮추지 않습니다. 임계값을 90 에서 80 으로 내리는 것은 예외이며, [../harness/references/harness-adoption.md](../harness/references/harness-adoption.md) AD-2 에 근거가 있고 `improvement-log/` 에 기록을 남깁니다.
- **한 번에 하나만 바꿉니다.** 하네스 요소를 Phase 0 안에서 여러 개 동시에 붙이지 않습니다([../harness/rules/harness-change-control.rule.md](../harness/rules/harness-change-control.rule.md)).
- 검증 단계를 열 개 넘게 늘리지 않습니다. 실행 시간이 길어지면 반복 자체가 죽습니다.

## Open Questions

| # | 질문 | 누가 답하는가 | 언제까지 |
| --- | --- | --- | --- |
| 1 | Python 패키지 관리자를 uv / poetry 중 무엇으로 고정하는가. `harness.config` 의 제품 단계 명령이 여기 달려 있습니다 | 사람 (showjihyun) | **닫힘** 2026-09-08 · 답: **uv** |
| 2 | 모노레포 도구를 pnpm workspace 단독으로 갈 것인가, turborepo 를 함께 쓸 것인가 | 사람 (showjihyun) | **닫힘** 2026-09-08 · 답: **pnpm workspace 단독**, turborepo 없음 |
| 3 | Python 과 TypeScript 가 한 저장소에 있을 때 `verify.sh` 를 한 번에 돌릴 것인가, kind 별로 나눌 것인가. `HARNESS_KIND` 가 `fullstack` 으로 잡히는 경우의 동작을 먼저 확인해야 합니다 | 사람 + 하네스 감사 | Phase 0 착수 전 |
| 4 | 인증을 Phase 0 에서 어디까지 넣는가. 로드맵은 "Authentication" 만 적고 범위를 정하지 않았습니다 | 사람 | Phase 0 중반 |
| 5 | `packages/sdk` 가 생성물인가 수기 작성물인가. AR-1(웹은 SDK 경유)의 실효성이 여기 달려 있습니다 | 사람 | Phase 0 중반 |

질문 1·2 는 2026-09-08 에 닫혔습니다(uv, pnpm workspace 단독). 질문 3 은 **착수 전에 닫습니다.** `harness.config` 의 제품 단계 명령이 이 답에 직접 의존하므로, 열린 채로 시작하면 에이전트가 추측으로 명령을 적고 그 명령이 게이트가 됩니다.

## Non-goals

이번에 하지 않는 것.

| 항목 | 언제 하는가 |
| --- | --- |
| Agent Runtime 의 실제 구현(Planner, Executor, State) | Phase 1 |
| MCP Gateway 구현 | Phase 2 |
| Kubernetes 실배포 | Month 6 Public Beta |
| Air-Gapped 번들 | Phase 11 |
| 제품의 `Evaluation` 기능 | Phase 7. 하네스 평가와 다른 것입니다([../docs/domain.md](../docs/domain.md) 5절) |
| `improvement-log/` 실운영 | AD-3. Phase 4 전후 |

## 근거

- [../docs/roadmap.md](../docs/roadmap.md) Phase 0, 원본 로드맵 5장
- [../harness/references/harness-adoption.md](../harness/references/harness-adoption.md) AD-1 완료 판정 기준
- 관측된 실패: 없음. 이 intent 는 계획에서 나왔고 실패에서 나오지 않았습니다. 그래서 하네스 규칙의 근거가 되지 못합니다
