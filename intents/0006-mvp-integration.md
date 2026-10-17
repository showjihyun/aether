# Intent 0006 — MVP 통합

| 키 | 값 |
| --- | --- |
| 번호 | 0006 |
| 작성일 | 2026-10-17 |
| 대상 Phase | [../docs/roadmap.md](../docs/roadmap.md) 의 **MVP 통합**(Month 4) — 원본 로드맵 10장 |
| 상태 | **초안** — 사람 승인 전입니다 |
| 승인 | (대기) |
| 후속 spec | [../specs/0006-mvp-integration.md](../specs/0006-mvp-integration.md) (**초안 2026-10-17** — 사람이 답한 셋을 D-1·D-3·D-6 으로, 나머지 셋을 D-4·D-5·D-7 로 고정했습니다) |

작업 단위는 [mvp-backlog.md](mvp-backlog.md) 의 MVP-1 ~ MVP-5 가 소유합니다. 이 문서는 그 다섯 단위가 **왜** 이번에 함께 가야 하는지, 끝났을 때 무엇이 관측되어야 하는지, 넘지 않을 선이 무엇인지를 고정합니다. 단위의 범위·완료 판정을 여기 복제하지 않습니다.

## Problem

Phase 4 가 끝나(2026-10-17) 제품은 Agent 를 만들고 실행하며, 도구는 Gateway 와 기본 deny Policy 를 지나고, Context 는 예산 안에서 조립되며, Workflow 가 노드를 전진시키고 사람의 승인을 기다립니다. **그런데 그것을 쓰는 방법이 HTTP 를 직접 치는 것뿐입니다.** 관측된 사실입니다.

- **`aether` CLI 가 없습니다.** 진입점은 `aether-api`(키 발급·openapi·events-schema)와 `aether-worker` 둘이고 **둘 다 운영자용**입니다. 제품을 처음 쓰는 사람이 "Agent 를 만들어 한 번 돌린다" 를 하려면 `curl` 로 인증 헤더를 붙여 네 번 호출해야 합니다.
- **화면이 하나입니다.** `apps/web/app` 에는 `page.tsx`(healthz 카드) 하나뿐인데, 사이드바(`components/nav-items.ts`)는 `/agents`·`/runs`·`/knowledge`·`/workflows` 를 가리킵니다 — **그 네 링크는 지금 404 입니다.** 껍데기가 먼저 서 있고 내용이 없습니다.
- **SDK 가 제품의 절반만 압니다.** `packages/sdk/src/client.ts` 는 healthz·agents·runs(+SSE)만 노출합니다. Knowledge 와 Workflow 는 `openapi.json` 에 있지만 클라이언트 함수가 없어, 화면이나 CLI 가 쓰려면 먼저 그 자리를 채워야 합니다.
- **로컬 LLM 이 기본 경로가 아닙니다.** compose 에 `llm` 프로파일(ollama, 다이제스트 핀)이 있고 `AETHER_MODEL_BASE_URL` 기본값도 그것을 가리키지만, 어댑터 기본값은 `fake` 이고 프로파일은 꺼져 있습니다. **모델 파일을 미리 받아 두는 절차도 문서 한 줄**이지 검증된 경로가 아닙니다 — 즉 "네트워크를 끊고 돌린다" 는 아직 **주장**입니다.
- **오프라인 시나리오가 테스트로 없습니다.** `harness.config` 에 `e2e` 단계가 없고, `smoke` 는 compose 로 Agent Run·도구·Knowledge 를 보지만 **Workflow 는 보지 않습니다**(spec 0005 D-16 이 일부러 뺐습니다). 로드맵 10장의 시나리오 전체를 한 번에 거는 테스트가 없습니다.
- **"10분" 이 측정된 적이 없습니다.** backlog 의 MVP 완료 판정은 "처음 보는 사람이 clone 부터 첫 Run 성공까지 10분" 인데, 그 측정 기록이 저장소에 없습니다. 지금은 Quickstart 문서도 없습니다.

이 다섯이 남은 동안은 **제품이 "된다" 고 말할 수 있는 근거가 `verify.sh` 뿐**입니다. 통합 테스트가 초록인 것과 사람이 열어서 쓸 수 있는 것은 다른 사실이고, 그 차이를 메우는 것이 이번 intent 입니다.

## Outcomes

끝났을 때 **관측되어야 하는 것**만 적습니다. 어떻게 만들지는 spec·plan 의 일입니다.

1. **한 명령으로 Agent 를 만들고 돌릴 수 있습니다** — CLI 로 `up` → Agent 생성 → Run 스트림 출력까지. api 코드를 import 하지 않고 SDK 만 씁니다.
2. **세 화면이 실제 데이터로 뜹니다** — Agent 와 대화(스트림), Run 목록, Run 상세(이벤트 타임라인 + trace id). 사이드바가 가리키는 링크가 **더 이상 404 가 아닙니다.**
3. **네트워크를 끊은 compose 에서 Run 이 로컬 모델로 `succeeded` 가 됩니다.** 부팅 경로에 모델 다운로드가 **없습니다**(미리 받아 둔 것을 씁니다).
4. **로드맵 10장의 시나리오가 테스트 하나로 성립합니다** — 네트워크 차단 → compose up → Knowledge 적재 → Agent 생성(MCP 바인딩) → **Workflow 실행** → 성공. 통과 로그가 `.harness/logs/` 에 남습니다.
5. **"clone 부터 첫 Run 성공까지" 가 측정되어 커밋됩니다.** 10분을 넘겼다면 **막힌 지점이 다음 단위로 등록**됩니다 — 숫자를 맞추려고 조건을 바꾸지 않습니다(EI-3 의 정신).

## Non-goals

- **Agent Builder·Workflow 편집 화면**(Phase 5). 사이드바의 `/workflows` 가 가리킬 화면이 MVP 범위인지는 아래 열린 질문입니다.
- **노드 실행 조회 API 와 그 투영**(spec 0005 개정 4 가 Phase 5 로 보냈습니다). 화면이 Workflow 의 **노드 단위**를 보여주려면 그것이 먼저 필요합니다.
- 인증·권한 모델의 확장(Phase 8), 멀티테넌시, Admin·Analytics 화면.
- 모델 선택 UI·GPU 스케줄링·Model Registry(Phase 6).
- 성능·다중 사용자 — MVP-5 가 재는 것은 **처음 쓰는 사람의 시간**이고 처리량이 아닙니다.

## Constraints

- **`apps/web` 은 `packages/sdk` 외의 `packages/*` 를 import 하지 않습니다**(AR-1). CLI 도 같습니다 — 그래서 SDK 의 빈자리를 먼저 채워야 합니다.
- **오프라인이 제품 요구입니다**(DP-4). 부팅 경로에 네트워크 호출이 생기면 그것이 결함입니다.
- **모델 호출은 `ModelGateway`(AR-5), 도구는 MCP Gateway(AR-6)를 지납니다.** CLI·화면이 그 통로를 우회하지 않습니다.
- **`harness.config` 에 단계를 더하는 것은 보호 파일 변경**이고 사람이 커밋합니다. 지금 전량 `verify.sh` 는 458,000~606,000 ms 사이이고 예산은 600,000 ms 입니다 — **단계를 하나 더하면 예산 결정이 같이 와야 합니다**(`improvement-log/2026-10-06-002`).
- 비밀값을 코드·로그·커밋에 남기지 않습니다. CLI 가 키를 다루므로 이 제약이 그 단위의 설계에 직접 걸립니다.

## Open Questions

**OQ1·OQ2·OQ5 는 2026-10-17 에 사람이 답했습니다** — Python CLI, 화면 넷을 이번에, `e2e` 를 `harness.config` 단계로. spec 0006 초안이 그 셋을 D-1·D-3·D-6 으로 고정하고 나머지 셋(OQ3·OQ4·OQ6)도 D-4·D-5·D-7 로 좁혔습니다. 아래 표는 **질문의 원문**으로 남겨 둡니다.

승인 전에 사람이 답해야 하는 것들입니다. **spec 은 이 답들을 결정(D-*)으로 고정합니다.**

| # | 질문 | 왜 지금 | 막는 단위 |
| --- | --- | --- | --- |
| OQ1 | **CLI 의 런타임.** backlog 는 "`packages/sdk` 만 씀" 이라 적었고 그 SDK 는 TypeScript 입니다 — CLI 를 Node 로 내면 사용자에게 Node 런타임을 요구하고, Python 으로 내면 SDK 를 한 벌 더 만들거나 AR-1 의 "CLI 판" 을 다시 정해야 합니다. 어느 쪽입니까 | MVP-1 의 전부가 이 답에 걸립니다 | MVP-1 |
| OQ2 | **MVP-2 의 화면 범위.** 사이드바는 넷을 가리키는데 backlog 의 MVP-2 는 셋(대화·Run 목록·Run 상세)입니다. `/knowledge`·`/workflows` 는 (a) 이번에 만든다 (b) 사이드바에서 뺀다 (c) "준비 중" 으로 둔다 중 무엇입니까 | 404 를 남긴 채 MVP 를 선언할 수 없습니다 | MVP-2 |
| OQ3 | **Workflow 를 화면에서 어디까지 보여줍니까.** 지금 조회 가능한 것은 Workflow Run 의 **상태·현재 노드·대기 대상**뿐이고 **노드 실행 목록은 API 가 없습니다**(`data` 평면, Phase 5). Run 상세가 Workflow 를 포함해야 하면 그 투영을 이번에 만들어야 합니다 | 범위가 Phase 5 로 넘어갈지 여기서 갈립니다 | MVP-2, MVP-4 |
| OQ4 | **모델 파일을 미리 받아 두는 경로.** 볼륨에 사람이 넣습니까(문서), 별도 스크립트가 받습니까(네트워크 있는 환경에서 1회), 아니면 이미지에 넣습니까(크기 증가). 오프라인 판정은 **부팅 경로에 다운로드가 없을 것**만 요구합니다 | MVP-3 의 완료 판정이 이 절차에 달려 있습니다 | MVP-3 |
| OQ5 | **e2e 를 어디서 돌립니까.** `harness.config` 에 단계를 더하면(보호 파일) 로컬 전량이 더 느려지고 예산이 이미 경계입니다. (a) 단계로 추가 (b) CI 전용 워크플로 (c) `HARNESS_DEFERRED_STEPS` 처럼 로컬 기본에서 미룸 중 무엇입니까 | MVP-4 의 완료 판정("CI 에서 통과")과 예산 결정이 한 묶음입니다 | MVP-4 |
| OQ6 | **"처음 보는 사람" 을 어떻게 구합니까.** MVP-5 는 저장소를 처음 보는 사람의 시간을 재는 것이고, 에이전트는 그 사람이 될 수 없습니다(이미 전부 알고 있습니다). 사람 한 명의 시간이 필요합니다 | 그 섭외 없이는 MVP-5 가 성립하지 않습니다 | MVP-5 |

**Q6(로컬 LLM 서버 후보)는 이미 닫혔습니다** — 2026-09-12 에 Qwen3.8 27B 양자화로 결정됐고 compose 의 `llm` 프로파일이 그 자리입니다(ollama, 다이제스트 핀). OQ4 는 "무엇" 이 아니라 "**어떻게 미리 받아 두는가**" 입니다.

## 사람 손

| 순간 | 무엇 |
| --- | --- |
| 이 intent | **승인**. 그리고 OQ1 ~ OQ6 중 최소 OQ1·OQ2·OQ5 는 spec 작성 전에 답이 필요합니다 |
| MVP-4 앞 | `harness.config`(또는 CI 워크플로) 변경 — 보호 파일이고 `harness-change` 라벨이 필요합니다. **예산 결정이 같이 옵니다** |
| MVP-5 | **처음 보는 사람 한 명의 시간**. 에이전트가 대신할 수 없는 유일한 단위입니다 |

## 넘지 않을 선

- **측정값을 맞추려고 조건을 바꾸지 않습니다.** 10분을 넘기면 그 사실과 막힌 지점을 적습니다(EI-3).
- **화면·CLI 를 위해 통로를 새로 만들지 않습니다.** 필요한 것이 없으면 SDK 와 기존 API 에 더하고, 그것이 평면·권한을 건드리면 사람에게 올립니다.
- **404 를 "준비 중" 으로 가리는 것과 화면을 만든 것을 같은 완료로 적지 않습니다.**

## 관련 문서

- [mvp-backlog.md](mvp-backlog.md) — MVP-1 ~ MVP-5 의 범위·완료 판정과 Q6·Q7
- [../docs/roadmap.md](../docs/roadmap.md) — Phase 표와 하네스 대응
- [../docs/architecture.md](../docs/architecture.md) — AR-1(web·CLI 는 SDK 만), AR-5·AR-6
- [../improvement-log/2026-10-06-002.yaml](../improvement-log/2026-10-06-002.yaml) — verify 예산. OQ5 가 이것과 한 묶음입니다
- [../docs/step_results/README.md](../docs/step_results/README.md) — Phase 1~4 가 무엇을 만들었는가
