# PROVENANCE

이 문서는 aether 저장소에 있는 것 중 **우리가 만들지 않은 것**이 어디서 왔는지, 그리고 가져오면서 무엇을 의도적으로 남기지 않았는지를 기록합니다. 출처를 적지 않으면 몇 달 뒤에 "이 규칙은 왜 있는가" 에 답할 수 없고, 답할 수 없는 규칙은 제거 판정도 할 수 없습니다([harness/rules/harness-gc.rule.md](harness/rules/harness-gc.rule.md)).

## 1. 하네스 번들

| 항목 | 값 |
| --- | --- |
| 출처 | https://github.com/showjihyun/harness-zzing |
| 가져온 커밋 | `b89299d7e042a6025181a34dc96117a277802ac9` (2026-09-06) |
| 가져온 날짜 | 2026-09-08 |
| 라이선스 | 원본 저장소의 `LICENSE` (MIT). 번들을 재배포할 때 함께 갑니다 |
| 대상 경로 | [harness/](harness/) 전체 |
| 변경 여부 | **무수정**. 번들 파일을 한 줄도 고치지 않았습니다 |

번들을 고치지 않은 것은 의도입니다. 고치기 시작하면 상류의 개선을 다시 가져올 수 없고, 그 순간 이 저장소가 하네스를 유지보수하게 됩니다. 프로젝트 고유 사정은 번들 밖(`harness.config`, `AGENTS.md`, `evaluation/`)에서 표현합니다.

번들에 고쳐야 할 것이 생기면 여기서 고치지 않고 `improvement-log/` 에 후보로 남긴 뒤 상류에 제안합니다.

## 2. 가져온 것과 그 자리

| 원본 경로 | 이 저장소의 자리 | 성격 |
| --- | --- | --- |
| `harness/` | [harness/](harness/) | 이식 가능한 번들. 무수정 사본 |
| `.claude/settings.json` | `.claude/settings.json` | 훅 등록. 무수정 |
| `.github/workflows/harness.yml` | `.github/workflows/harness.yml` | CI 게이트. 무수정 |
| `.github/CODEOWNERS` | `.github/CODEOWNERS` | 사람 검토 경로. 무수정 |
| `.gitignore` | `.gitignore` | 런타임 산출물 제외 목록 + aether 스택(node/python) 항목 추가 |

## 3. 가져오지 않은 것

| 원본 경로 | 왜 가져오지 않았는가 |
| --- | --- |
| `improvement-log/` (원본 10건) | 하네스 번들 자신에서 관측된 실패입니다. aether 의 실패가 아니므로 가져오면 근거 없는 lesson 이 됩니다(HP-5) |
| `evaluation/runs/` | 같은 이유. 다른 저장소의 판정 기록입니다 |
| `compare_resource/baseline/` | 계보가 다른 외부 프런트엔드 기준 번들입니다. aether 에서 쓸 근거가 아직 없습니다. 필요해지면 그때 근거와 함께 가져옵니다 |
| `README.md`, `README.ko.md` | 하네스 번들 자체를 설명하는 문서입니다. aether 의 README 는 제품을 설명해야 하므로 별도로 씁니다 |
| `harness.config` (원본) | 원본은 "하네스 번들이 성립하는가" 를 검사합니다. 구조는 그대로 따르되 대상은 aether 로 다시 적었습니다 |

## 4. aether 가 스스로 만든 것

| 경로 | 내용 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | 진입점 지침. `harness/templates/AGENTS.md` 의 자리표시자를 aether 로 채운 것 |
| [CLAUDE.md](CLAUDE.md) | 진입 지도. `harness/templates/CLAUDE.md` 기반 |
| `harness.config` | aether 의 verify 단계 정의 |
| `.gitattributes` | 줄바꿈을 LF 로 고정. bash 스크립트와 `harness.config` 가 Windows clone 에서 CRLF 로 깨지는 것을 막습니다. 번들에는 없던 파일입니다 |
| [docs/](docs/README.md) | 계층·용어·Phase. 에이전트의 탐색 대상 |
| [evaluation/](evaluation/README.md) | 번들 템플릿의 `{{자리표시자}}` 를 aether 도메인으로 실체화한 사본 |
| [improvement-log/](improvement-log/README.md) | 아직 비어 있습니다. 첫 항목은 실제로 실패가 관측될 때 생깁니다 |
| [intents/](intents/intent.md) | intent → spec → plan 파이프라인의 첫 단계. 출처는 6절 |
| [specs/](specs/README.md) | 승인된 intent 의 요구사항과 설계. 첫 spec(0001)이 나오면서 생겼습니다 |
| [plans/](plans/README.md) | 승인된 spec 의 파일·순서·판정 절차. 첫 plan(0001)이 나오면서 생겼습니다 |
| [.claude/agents/](.claude/agents/implementer.md) | 구현 서브에이전트. 코드 작성과 테스트 실행을 Sonnet 5 로 위임합니다. 생성자와 판정자를 가르는 장치이기도 합니다(HE-9). 번들의 `harness/subagents/` 형식을 따랐습니다 |

## 5. 로드맵 원본

| 항목 | 값 |
| --- | --- |
| 파일 | [Open_Hybrid_Enterprise_AI_OS_Final_Roadmap.md](Open_Hybrid_Enterprise_AI_OS_Final_Roadmap.md) |
| 출처 | 저장소 밖에서 생성된 초기 분석 문서(다른 LLM 산출물) |
| 신뢰 등급 | 사람이 채택한 **계획**. 하네스 규칙의 근거는 아닙니다 |
| 판정 근거 | [docs/roadmap.md](docs/roadmap.md) 1절, [harness/rules/untrusted-experience.rule.md](harness/rules/untrusted-experience.rule.md) |

이 구분을 두는 이유는 단순합니다. 계획 문서에 적힌 "항상 이렇게 하라" 는 문장이 검증 없이 하네스 규칙이 되면, 그 순간 하네스는 우리가 관측한 실패가 아니라 외부 문서를 반영하게 됩니다.

## 6. intent → spec → plan 파이프라인

| 항목 | 값 |
| --- | --- |
| 출처 | Anthropic, AI-Native SDLC Playbook — Requirements and Design (https://academy.claude.com/courses/ai-native-sdlc-playbook/requirements-and-design) |
| 보조 참고 | https://javaexpert.tistory.com/1823 (한국어 정리. 디렉터리 구조와 템플릿 항목의 근거) |
| 가져온 날짜 | 2026-09-08 |
| 대상 경로 | [intents/](intents/README.md) |

가져온 것과 바꾼 것은 다음과 같습니다.

| 원본 | aether 에서 |
| --- | --- |
| 파일 하나를 `intent.md` 로 부름 | 본문은 `intents/<NNNN>-<슬러그>.md`. 여러 건을 동시에 다루므로 번호를 붙입니다. 플레이북이 부르는 이름은 [intents/intent.md](intents/intent.md) 로 남겨 **활성 intent 를 가리키는 자리**로 씁니다. 본문을 복제하지 않습니다 |
| `intents/` `specs/` `plans/` 세 디렉터리 | `intents/` 만 지금 만듭니다. 나머지는 그 단계의 첫 산출물이 나올 때 만듭니다(AD-P2) |
| 템플릿 항목: Problem, Proposed Outcome, Affected Users, Affected Systems, Constraints, Open Questions | 그대로 채택하고 **Non-goals** 와 **근거** 두 항목을 더했습니다. 범위 확대(REP-6)와 근거 없는 계획을 막기 위한 자리입니다 |
| — | `Affected Systems` 를 [docs/architecture.md](docs/architecture.md) 의 계층 이름으로 강제했습니다. 자유 서술이면 문서와 코드가 다른 이름을 쓰게 됩니다 |
| — | intent 의 문장이 하네스 규칙으로 승격되지 않는다는 경계를 명시했습니다([intents/README.md](intents/README.md) "하네스와의 관계") |

## 7. 차용한 아키텍처 개념

[docs/architecture.md](docs/architecture.md) 3.1 의 AR-8 ~ AR-11 은 두 외부 개념을 이 저장소에 맞게 줄인 것입니다.

| 항목 | 값 |
| --- | --- |
| 출처 1 | Clean Architecture (Robert C. Martin) — 의존성 규칙: 의존은 안쪽으로만, 프레임워크는 바깥의 세부사항 |
| 출처 2 | Hexagonal Architecture / Ports and Adapters (Alistair Cockburn) — 포트는 안쪽이 선언, 어댑터는 바깥이 구현, driving/driven 의 구분 |
| 가져온 날짜 | 2026-09-09 |
| 대상 | Python 패키지 전부(`apps/*`, `packages/*`)의 내부 구조와 import-linter 계약 |

| 원본 | aether 에서 |
| --- | --- |
| 클린 아키텍처의 네 동심원(Entities · Use Cases · Interface Adapters · Frameworks) | **세 층**으로 접었습니다 — `domain` · `application` · `adapters`. Interface Adapters 와 Frameworks 를 가르는 실익이 이 규모에서는 없고, 층이 늘면 빈 껍데기가 늘어납니다 |
| 헥사고날의 driving / driven | `adapters/inbound` / `adapters/outbound` 로 이름을 바꿔 채택. 방향이 이름에 드러나야 AR-11 이 읽힙니다 |
| 헥사고날의 포트 두 종류 | 채택. inbound 포트(유스케이스 인터페이스)와 outbound 포트(바깥에 요구하는 것)를 `application/ports/inbound`, `application/ports/outbound` 에 `Protocol` 로. 유스케이스는 inbound 포트의 구현으로 `application/usecases` 에 |
| 헥사고날의 "안은 포트로만 닿는다" | 채택. AR-12 — 어댑터는 `application.ports` 만 import 하고 유스케이스 구현을 직접 부르지 않습니다. 유스케이스는 조립이 포트 타입으로 건넵니다 |
| 포트 계약 테스트 | 채택. 같은 테스트를 fake 어댑터와 실제 어댑터에 둘 다 돌립니다. "어댑터를 바꿔 꽂을 수 있다" 는 주장이 이것으로 증명됩니다 |
| 헥사고날의 "포트마다 모듈" | 강제하지 않습니다. 포트는 방향별 디렉터리 아래 모으고, 파일을 어떻게 나눌지는 포트 수가 정합니다 |
| 클린 아키텍처의 "유스케이스 = 클래스 하나" | 규칙으로 두지 않았습니다. 함수든 클래스든 `application` 에 있고 AR-9 를 지키면 됩니다 |
| 조립(composition root) | 채택. `apps/*/main.py` 한 곳(AR-10). 규칙으로 승격은 어댑터가 생기는 Phase 1 |
| — | 신뢰 경계를 어댑터에 놓는 해석을 더했습니다. `Observation` 같은 외부 데이터의 표시는 outbound 어댑터의 일이고 `domain` 은 표시된 값만 봅니다 |

이 개념들을 자연어로만 두지 않고 import-linter 계약으로 옮기는 이유는 이 저장소의 원칙([AGENTS.md](AGENTS.md) Learning) 그대로입니다 — 자연어 지시보다 arch-rule 이 먼저입니다.

### 7.1 UI 기반 — shadcn/ui

[DESIGN.md](DESIGN.md) 가 `apps/web` 의 표현 규약을 소유합니다. 그 바탕은 우리가 만들지 않은 것입니다.

| 항목 | 값 |
| --- | --- |
| 출처 | shadcn/ui (https://ui.shadcn.com) — Radix UI 프리미티브 + Tailwind CSS 위의 컴포넌트 **소스 복사** 모델 |
| 함께 오는 것 | Tailwind CSS v4, Radix UI, lucide-react, next-themes, Geist(`next/font`) |
| 라이선스 | shadcn/ui MIT, Radix MIT, Tailwind MIT, lucide ISC. 전부 저장소의 MIT 와 호환 |
| 가져온 날짜 | 2026-09-10 (결정). 설치는 P0-3b |
| 대상 | `apps/web/components/ui/`(생성물, 커밋), `app/globals.css` 의 토큰 |

| 원본 | aether 에서 |
| --- | --- |
| shadcn CLI 버전 | **`3.8.5` 고정.** v4 CLI 는 init 을 프리셋 8종으로 바꿔 `new-york + neutral` 을 지정할 수 없습니다. 프리셋을 고르는 것은 새 시각적 결정이라 3.x 마지막 안정판을 씁니다(P0-3b). 3.8.5 의 생성물은 단일 패키지 `radix-ui` 를 import 합니다 |
| shadcn 의 기본값(style `new-york`, base `neutral`, radius, CSS 변수) | **그대로 채택.** 바꾸지 않는 것이 결정입니다 — 디자인 결정을 최소화하는 것이 DESIGN.md 의 목적이고, 기본값이 곧 디자인 시스템입니다 |
| "필요한 것만 `add`" | 채택. 초기 세트는 DESIGN.md 4절(MVP-2 가 필요로 하는 것). 더 필요하면 그 단위에서 `add` 하고 표에 한 줄 |
| 생성물을 수정하는 자유 | 채택하되 이유를 파일 머리에 남기고, 고친 파일은 다시 덮지 않음(D-6) |
| 브랜드 테마 | **결정하지 않음.** `neutral` 의 `primary` 가 그 자리. 결정할 때 DESIGN.md 2절을 고침 |
| — | 도메인 → 표현 표(Run 상태 ↔ badge)와 외부 텍스트 렌더 규약(신뢰 경계)을 더했습니다. shadcn 은 이것을 모릅니다 |

왜 이것을 채택했는가: 화면을 만드는 사람이나 에이전트가 색·간격·모양을 고르는 순간을 없애기 위해서입니다. 결정이 한 곳(DESIGN.md)에 있고 기본값이 답이면, 화면 단위의 작업은 조합만 하게 됩니다. 컴포넌트 소스가 저장소에 들어오므로 오프라인(DP-4)과 장기 유지에도 외부 서비스 의존이 없습니다.

## 8. 도입 이력

| 날짜 | 무엇을 |
| --- | --- |
| 2026-09-08 | 번들 도입(AD-1). verify 단계는 self-check 6개. 제품 코드 없음 |
| 2026-09-08 | `intents/` 추가. Intent 0001(Phase 0) 작성, 승인 대기 |
| 2026-09-08 | `intents/intent.md` 추가. 플레이북의 이름으로 활성 intent 를 가리키는 자리를 만들고, 진입점 문서(AGENTS.md·CLAUDE.md·docs/README.md)의 경로를 그쪽으로 옮겼습니다 |
| 2026-09-08 | Intent 0001 승인(showjihyun). Q1 = uv, Q2 = pnpm workspace 단독으로 닫힘. 다음 산출물은 spec |
| 2026-09-08 | `specs/` 신설. Spec 0001(Phase 0) 초안, 검토 대기. Q3 는 근거와 함께 결정 요청으로 올림 |
| 2026-09-09 | Spec 0001 승인(showjihyun). D-1 ~ D-12 채택, Q3·Q4·Q5 닫힘. 다음 산출물은 plan |
| 2026-09-09 | `plans/` 신설. Plan 0001(Phase 0) 초안, 검토 대기. 사람 손 세 번(H-1 보호 파일, H-2 게이트, H-3 인증)으로 묶고 보호 파일 내용을 부록으로 제안 |
| 2026-09-09 | architecture.md 3.1 에 AR-8 ~ AR-11 신설(클린·헥사고날, 7절). Spec 0001 개정 1, plan·backlog 동반 갱신 |
| 2026-09-09 | 포트·어댑터를 1급 개념으로. 포트를 inbound/outbound 로, 유스케이스를 분리, AR-12 신설. Spec 0001 개정 2 |
| 2026-09-09 | Plan 0001 리뷰 반영(F-1 ~ F-6, P-1 ~ P-7). Spec 0001 개정 3. `.claude/agents/implementer.md`(Sonnet 5) 추가, AGENTS.md Loop 에 위임 규칙 |
| 2026-09-09 | Plan 0001 승인(showjihyun). intent → spec → plan 사슬이 Phase 0 에서 처음 닫힘. 다음은 H-1(보호 파일 다섯 개, 사람) → P0-1(implementer) |
| 2026-09-09 | H-1 완료(사람, `3040b1c`). **P0-1 완료** — 첫 제품 코드. implementer(Sonnet) 1회 반복, 주 세션 리뷰. `.importlinter` 후속 1건(`google.genai` → `google`, 사람). 11개 계약 KEPT |
| 2026-09-09 | P0-6 구현(implementer, 반복 2회 + 리뷰 재작업 1회). 리뷰가 Node 버전 spoof shim 을 거부(EI-6 모양) — 환경 불일치는 소리 내어 실패하도록. 이 기계의 Node v23 이 `.nvmrc`(22)와 달라 `test_depcruise` 1건 실패 상태로 `진행`. Node 를 맞춘 뒤 완료 판정 |
| 2026-09-09 | 개발 기계 Node v23 → **24.19.0**(Active LTS, winget). `.nvmrc` 24, `engines >=24`. `tests/arch` 5/5 — **P0-6 완료.** AR-1(depcruise)·AR-2~12(import-linter) 전부 fixture 로 발화 증명 |
| 2026-09-10 | `main` 을 `origin` 에 첫 push. CI(harness 워크플로) 첫 성공. GitHub 초기 커밋의 `LICENSE`(MIT)를 `main` 에 병합하고 기본 브랜치를 `main` 으로, `master` 삭제 |
| 2026-09-10 | **P0-2 완료** — `apps/api` 최소 기동(implementer, 반복 1회). `/healthz` 계약, `AETHER_` 설정, OTel no-op 초기화, `aether-api openapi`. 조립은 `main.py`, CLI 진입점 `main:cli`. 실제 기동 200 확인. lint-imports 11 kept — AR-8~12 가 실제 import 를 처음 검사한 단위 |
| 2026-09-10 | UI 기반 결정 — shadcn/ui 기본값을 디자인 시스템으로(7.1). `DESIGN.md` 신설, spec 0001 개정 6(2.5, D-14), backlog·plan 에 P0-3b 추가 |
| 2026-09-10 | TDD 점검 — 문장(`implementer.md` 한 줄)으로만 있었고 P0-4 는 구현 먼저였음. 자연어 지시가 무시된 예측된 실패. 관측으로 환원: implementer 작업 순서를 red → green → refactor 절차로, 보고에 `red 증거` 칸(없으면 반려). plan 남은 단위에 red 단계 명시(P0-8 재배열). P0-7(AD-2) 뒤 improvement candidate 후보 |
| 2026-09-10 | TDD 리뷰 2차 — 실행층(plan·implementer)에는 걸렸으나 단위 정의층·반려층에 없었음. backlog 쪼갠 기준에 "테스트가 먼저", AGENTS.md Loop 에 반려 규칙, plan P0-9 에 유스케이스 테스트 존재 구조 테스트(1b), P0-7 에 improvement candidate(P0-4 관측) → REP-9 경로 |
| 2026-09-10 | **P0-8 완료** — 데이터 모델 v1(implementer, 반복 1회). **red → green 절차가 처음 적용된 단위**: 테스트 4건 먼저 → `alembic` 실패 기록 → 마이그레이션이 통과시킴. `control`/`data` 스키마·역할 분리가 권한 테스트로, `agent_versions` 불변이 트리거 테스트로 고정. `docs/data-model.md` 신설. spec 개정 7 |
| 2026-09-10 | **P0-3b 완료** — Tailwind v4 + shadcn/ui 17개 + 앱 셸 + `RunStatusBadge` + healthz 재표현(implementer, 반복 1회). shadcn CLI 3.8.5 고정(v4 프리셋 = 새 결정 회피). D-1·D-5 grep 0건, depcruise 134 modules 위반 0, API 다운 시 `/` 가 alert 로 200. PostCSS 설정은 package.json 필드(보호 파일 조합 제약) |
| 2026-09-10 | **P0-3 완료** — sdk 타입 생성 + web healthz(implementer, 반복 1회). AR-1 이 실제 코드에서 처음 판정(74 modules, 위반 0). H-1 후속 2(사람): depcruise `tsConfig` 절대 경로, Next 가 다시 쓴 web tsconfig 수용. 세 언어 경계(Python → OpenAPI → TS)가 드리프트 테스트로 닫힘 |
| 2026-09-10 | **P0-4 완료** — `apps/worker` 최소 기동(implementer, 반복 1회). Redis Streams consumer group 대기, 순수 백오프 규칙, stop 이벤트 종료. 구현 세션이 주 세션의 지시("pending 0")를 spec 2.3 근거로 거부하고 PEL 의미대로 테스트 — 리뷰 승인. **wave 2 종료** |
