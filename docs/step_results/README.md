# Step 결과 (step_results)

이 디렉터리는 **무엇이 실제로 구현되었는가**에 답합니다. `intents/` 는 무엇을 왜 하려는지, `specs/` 는 무엇을 만들기로 정했는지, `plans/` 는 어떤 순서로 할지를 소유합니다. 그 셋은 **작업 전**의 문서이고 작업이 끝난 뒤에도 바뀌지 않습니다. 이 디렉터리는 **작업 뒤**의 문서입니다 — 정한 것과 만든 것이 어디서 갈라졌는지, 판정이 무엇으로 성립했는지가 여기 남습니다.

진행 상태(대기·진행·완료)의 정본은 여전히 [../../intents/mvp-backlog.md](../../intents/mvp-backlog.md) 입니다. 이 디렉터리는 상태를 소유하지 않고 **내용**을 소유합니다.

## 색인

| 페이지 | 범위 | 상태 |
| --- | --- | --- |
| [phase-0.md](phase-0.md) | Phase 0 Architecture & Foundation — P0-1 ~ P0-9 | 완료 2026-09-11 |
| [phase-1.md](phase-1.md) | Phase 1 Agent Runtime — P1-1 ~ P1-9 | 완료 2026-09-16 |
| [phase-2.md](phase-2.md) | Phase 2 Enterprise MCP Gateway — P2-1 ~ P2-6, H-1, H-2 | 완료 2026-10-03 |
| [phase-3.md](phase-3.md) | Phase 3 Context Compiler / RAG — 단위별 페이지의 입구 | 진행 중 |

Phase 3 부터는 **단위당 한 장**입니다 — [p3-1.md](p3-1.md), [p3-2a.md](p3-2a.md), [p3-2b.md](p3-2b.md), [p3-3.md](p3-3.md), [p3-4.md](p3-4.md).

그림(standalone HTML, Phase 당 1장)은 `diagrams/` 에 있습니다 — [phase-0](diagrams/phase-0.html) · [phase-1](diagrams/phase-1.html) · [phase-2](diagrams/phase-2.html) · [phase-3](diagrams/phase-3.html). 브라우저로 직접 엽니다(외부 요청 없음).

소스 JSON 을 `diagrams/src/` 에 함께 둡니다 — HTML 은 생성물이고 **고쳐야 할 것은 JSON** 입니다. 다시 만드는 명령(archify skill 이 설치돼 있어야 합니다):

```
node ~/.claude/skills/archify/bin/archify.mjs deliver architecture   docs/step_results/diagrams/src/phase-3.architecture.json   docs/step_results/diagrams/phase-3.html --quality showcase --json
```

네 장 모두 `showcase` 로 받았습니다(9개 artifact check, 오류 0 · 경고 0). 한 가지 한계 — 그 도구의 글꼴 스택에 **한글 글꼴이 없어** 한글 렌더링이 보는 쪽 OS 의 대체 글꼴에 달려 있습니다. 그림은 보조이고 내용의 정본은 markdown 입니다.

## 왜 Phase 0~2 는 Phase 당 한 장인가

과거 26개 단위를 되짚어 단위별로 쓰는 것은 **지금 이 문서의 목적에 기여하지 않습니다**. 목적은 "앞으로 각 단위가 끝날 때 그 내용이 남는 것" 이고, 과거는 요약으로 충분합니다. 과거의 세부는 이미 그 단위의 커밋 메시지와 PR 본문에 있고, 이 문서는 그것을 복제하지 않고 **가리킵니다**. 같은 사실을 두 곳에 두면 갈라집니다.

## 한 장이 담아야 하는 것

단위 페이지는 다섯 절을 갖습니다. 순서를 지킵니다 — 읽는 사람이 "무엇이 생겼는지" 를 먼저 알아야 나머지가 의미를 가집니다.

| 절 | 담는 것 | 담지 않는 것 |
| --- | --- | --- |
| `## 무엇이 생겼는가` | 생긴 것·바뀐 것의 목록. 파일 경로와 포트·표·경로 이름 | 코드 본문. diff |
| `## 왜 그렇게 했는가` | 갈림길이 있었던 결정과 고른 이유. spec 의 D-* 를 가리킵니다 | spec 의 복제 |
| `## 하네스 근거` | 아래 표의 다섯 줄. 이 절이 이 디렉터리의 존재 이유입니다 | — |
| `## 정한 것과 다른 점` | spec·plan 과 갈라진 부분과 그 사유. 없으면 "없음" | 변명 |
| `## 남긴 것` | 미측정, 사람 몫, 후속 단위로 미룬 것 | 막연한 TODO |

Phase 요약 페이지는 같은 다섯 절을 Phase 단위로 갖습니다.

## 하네스 근거 — 이 다섯 줄을 비우지 않습니다

"구현했다" 는 주장이고, 주장은 근거로 성립합니다. 이 저장소에서 근거는 하네스의 구조 안에 이미 있습니다 — 그 구조의 어느 자리가 이 단위를 판정했는지를 적습니다. 비어 있으면 그 단위는 **판정되지 않은 것**입니다.

| 줄 | 무엇을 적는가 | 정본 |
| --- | --- | --- |
| **요구** | 이 단위가 만족시킨 `R-*` 와 그것을 보는 검사 | 해당 spec 의 요구 표 |
| **결정** | 이 단위가 따른 `D-*` | 해당 spec 의 결정 표 |
| **단계** | 판정한 verify 단계 이름(`api-unit`·`api-integration`·`smoke` 등) | `harness.config` |
| **증거** | verify 의 합계 ms·단계 수·`budget_exceeded`, 그리고 red 증거가 있는 곳(PR 번호) | `.harness/verify.json`, PR |
| **후보** | 이 단위에서 나온 improvement candidate 번호 | [../../improvement-log/](../../improvement-log/) |

단계 이름을 여기 나열하지 않습니다 — 개수와 내용은 `harness.config` 가 소유합니다([../../AGENTS.md](../../AGENTS.md) Verification). 이 디렉터리는 그 이름을 **참조**할 뿐입니다.

## 언제 쓰는가

단위의 PR 에 그 단위의 페이지를 **함께** 넣습니다. 나중에 몰아서 쓰지 않습니다 — 몰아 쓰면 기억이 아니라 추측이 들어가고, 추측은 커밋 메시지와 어긋납니다.

이 약속은 자연어 지시로 두지 않고 검사로 둡니다([../../AGENTS.md](../../AGENTS.md) Learning: "전역 지시보다 test, lint, arch-rule, hook, script 를 우선합니다"). `tests/scripts/test_step_result_pages.py` 가 `main` 의 커밋 trailer `Unit:` 를 읽어 Phase 3 이후의 단위마다 페이지가 있는지, 그 페이지에 위 다섯 절이 있는지 봅니다. 그 테스트는 하네스의 기존 `quality` 계층 단계에서 함께 돕니다 — 새 verify 단계를 더하지 않았습니다(이유는 [phase-3.md](phase-3.md) 의 `남긴 것`).

## 관련 문서

- [../README.md](../README.md) — 문서 지도
- [../roadmap.md](../roadmap.md) — 지금이 어느 Phase 인가
- [../../intents/mvp-backlog.md](../../intents/mvp-backlog.md) — 단위의 상태(정본)
- [../../PROVENANCE.md](../../PROVENANCE.md) — 하네스가 어디서 왔는가
