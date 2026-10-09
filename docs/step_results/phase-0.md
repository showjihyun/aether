# Phase 0 — Architecture & Foundation (완료 2026-09-11)

단위 열 개(P0-1 ~ P0-9, P0-3b 포함). intent [0001](../../intents/0001-phase-0-foundation.md) · spec [0001](../../specs/0001-phase-0-foundation.md) · plan [0001](../../plans/0001-phase-0-foundation.md). 마지막 PR #10.

그림: [diagrams/phase-0.html](diagrams/phase-0.html)

## 무엇이 생겼는가

| 단위 | 생긴 것 |
| --- | --- |
| P0-1 | 모노레포 트리 — `apps/{web,api,worker}`, `packages/{runtime,workflow,context,memory,mcp,policy,evaluation,sdk}`, `infra/{docker,kubernetes}`. 각 Python 패키지는 세 층의 빈 껍데기(`domain`, `application/ports/{inbound,outbound}`, `application/usecases`, `adapters/{inbound,outbound}`)만. uv(Python) + pnpm workspace(Node) |
| P0-2 | FastAPI 앱과 `GET /healthz` 하나. 환경변수만으로 기동. OpenTelemetry SDK 초기화(exporter 없이도 뜸) |
| P0-3 | `packages/sdk` 의 `healthz()`, 그것을 부르는 Next.js 페이지 하나. 타입은 생성, 호출은 수기(spec D-2) |
| P0-3b | Tailwind v4 + shadcn/ui(new-york·neutral·CSS 변수), 앱 셸(사이드바 5항목·헤더·`lg` 미만 sheet), `next-themes`, Geist. 도메인 컴포넌트 `RunStatusBadge` |
| P0-4 | Redis 를 기다리는 worker 프로세스. 작업 정의 없음. SIGTERM 에 5초 내 종료 |
| P0-5 | `infra/docker/compose.yaml`(PostgreSQL·Redis·migrate·api·web·worker), `compose.offline.yaml`(internal 네트워크 + `probe` 서비스), `.dockerignore`, 루트 `README.md` |
| P0-6 | `.importlinter`(AR-2·3·4·5·8·9·11·12)와 `.dependency-cruiser.cjs`(AR-1). 각 규칙마다 **일부러 위반한 예시가 실패하는** 테스트 |
| P0-7 | `harness.config` 의 제품 단계 활성화, 임계값 90 → 80, CI(`.github/workflows/harness.yml`)와 비밀값 스캔 job, Dependabot |
| P0-8 | 스키마 `control`/`data` 와 역할 `aether_control`/`aether_data` 분리. `control.{agents,agent_versions,api_keys,runs}` · `data.run_executions`. `agent_versions` 불변 트리거. `docs/data-model.md` 신설 |
| P0-9 | API 키 인증(spec D-3). 보호 경로는 401, `/healthz` 는 인증 없이 200 |

## 왜 그렇게 했는가

- **빈 껍데기를 먼저 만들었습니다.** 패키지 경계를 나중에 그으면 이미 섞인 코드를 되돌려야 합니다. 트리가 먼저 있으면 `.importlinter` 가 첫날부터 방향을 잡습니다(DP-5 Modular Monolith).
- **아키텍처 규칙을 문서가 아니라 기계에 두었습니다**(P0-6). AR-* 를 자연어로만 두면 위반이 리뷰에서만 걸리고, 리뷰는 매번 사람을 씁니다. 위반 예시가 실패하는 테스트까지 함께 둔 이유는 "규칙이 등록되었다" 와 "규칙이 발화한다" 가 다른 사실이기 때문입니다.
- **AR-6·AR-7 은 등록만 하고 검사를 걸지 않았습니다** — 검사할 코드가 없었습니다. 없는 것을 검사하는 단계를 미리 적지 않습니다.
- **인증은 API 키 하나로 시작했습니다**(게이트 Q4). 세션·OIDC 는 조직·사용자 모델을 요구하고 그것은 Phase 8 입니다.

## 하네스 근거

| 줄 | 내용 |
| --- | --- |
| **요구** | spec 0001 R-1(명령 하나로 기동) · R-2(verify 가 self-check 와 제품 단계를 함께 집계) · R-3(AR-1~5·8·9·11·12 기계 판정) · R-4(인터넷 없이 `compose up`) · R-5(CI) · R-6(비밀값 부재) · R-7(Control → Data 는 선언만) · R-8(저장 모델) · R-9(401/200) · R-10(게이트 약화 금지) · R-11(시간 예산) |
| **결정** | D-1(아키텍처 규칙을 한 번에) · D-2(타입 생성·호출 수기) · D-3(API 키) · D-12(verify 시간 예산 600,000 ms — 그때 단계는 10개) · D-14(P0-3b 신설) |
| **단계** | 이 Phase 가 **제품 단계 자체를 켰습니다**(P0-7). 그 전까지 verify 는 self-check 뿐이었습니다 |
| **증거** | 각 단위의 PR(~#10)과 커밋. `arch-test` 의 위반 주입 테스트가 이 Phase 의 가장 강한 증거입니다 |
| **후보** | P0-7 에서 과거 관측을 일괄 전환(가드 `install` 오탐, cp949 ×3, Node LTS, shadcn v4 프리셋, depcruise 상대 경로, `uv sync` 의미, eslint `projectService`) |

## 정한 것과 다른 점

- P0-3 뒤에 **P0-3b 를 신설**했습니다(spec 개정 6, D-14). 화면 기반이 없으면 Phase 1 의 Run 화면이 임의 색·임의 간격으로 자랍니다.
- 하네스 도입 단계가 이 Phase 에서 **AD-1 → AD-2** 로 올라갔습니다(P0-7, 2026-09-11).

## 남긴 것

- `packages/{workflow,context,memory,mcp,policy,evaluation}` 는 빈 껍데기로 남았습니다 — 각자의 Phase 가 채웁니다.
- `infra/kubernetes` 는 디렉터리와 README 한 줄.
- AR-6·AR-7 의 기계 검사는 Phase 2 로 미뤘습니다(대상 코드 부재).
