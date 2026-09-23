# 이 저장소의 개선 후보

이 디렉터리는 aether 를 만들면서 **실제로 관측된** 실패를 담습니다. 스키마·템플릿·상태 전이 규칙은 번들이 소유하며 여기서 복제하지 않습니다.

| 무엇 | 어디 |
| --- | --- |
| 키 명세와 검증 규칙 | [../harness/improvement-log/schema.md](../harness/improvement-log/schema.md) |
| 템플릿 | [../harness/improvement-log/_template.yaml](../harness/improvement-log/_template.yaml) |
| 운용 규칙 | [../harness/improvement-log/README.md](../harness/improvement-log/README.md) |
| 승격 판정 | [../harness/rules/promotion-gate.rule.md](../harness/rules/promotion-gate.rule.md) |
| 배치 판단 | [../harness/rules/lesson-placement.rule.md](../harness/rules/lesson-placement.rule.md) |

## 현재 상태

**AD-2(Week 1)에 진입했습니다.** 2026-09-11, P0-7 에서 candidate 15건을 발급했습니다(`2026-09-11-001` ~ `015`. 014·015 는 후보 파일 검토와 H-2b 의 CI 실패에서 관측). P0-9 에서 3건(`016` 거짓 red · `017` PEP 563 + `Depends` 422 · `018` 검토 대기 red 와 stop 게이트). P1-1 에서 1건(`2026-09-13-001` plan 단계가 '추가 + 테스트' 로 묶여 sdk 구현이 테스트보다 먼저 쓰임). P1-4 에서 1건(`2026-09-13-002` 명시 지시에도 구현 먼저 — 자연어로는 막히지 않음, red-check hook 제안, recurrence high). P1-6 에서 2건(`2026-09-14-001` TestClient 는 열린 스트리밍 응답을 실시간으로 넘기지 않음 — 단절 테스트는 실제 서버로, `2026-09-14-002` `redis.asyncio` 기본 `socket_timeout` 과 `XREAD BLOCK` 충돌). P1-7 에서 1건(`2026-09-15-001` 위임 지시의 그룹 간 red 가정 오류 — 앞 그룹이 구현한 동작의 뒤 그룹 테스트는 mutation 증거로) + `2026-09-13-002` 재발 1회 기록. P1-9 에서 2건(`2026-09-16-001` D-15 단계 상한 10 → 11 의 근거와 실측 — 사람 결정 기록, `2026-09-16-002` bake 는 compose 상대 컨텍스트를 실행 위치 기준으로 해석). AD-2 기준선 실행(2026-09-17, 대표 task 7건)에서 4건(`2026-09-17-001` 대표 task 실행이 blind 가 아님 — 실행 에이전트가 task 문서를 읽음, `2026-09-17-002` REP-1·REP-4·REP-8 입력이 Phase 1 이후 계약과 맞지 않아 not-run, `2026-09-17-003` REP-2 기준이 실행자 자신의 red 관측을 요구하지 않음, `2026-09-17-004` performance 계층에 verify 단계가 없어 150 ms 기준이 계층 평가에 빠짐) + `2026-09-13-002` 재발 1회(다른 에이전트 종류). REP-1·4·8 개정 입력 첫 실행(같은 날)에서 1건(`2026-09-17-005` web-typecheck 가 생성물을 HEAD 와 비교해 미커밋 계약 변경은 verify 를 통과할 수 없음 — 2회 관측) + `2026-09-17-002` 적용·회귀 확인(not-run 0건), `2026-09-17-001` 누출 경로 추가(성능 기준 문서의 task ID), `2026-09-13-002` 재발 1회. blind 훅 적용 뒤 REP-5 재실행(2026-09-19)에서 1건(`2026-09-19-001` blind 조건에서는 REP-5 입력이 작업 지시로 읽히지 않아 not-run) + `2026-09-17-001` 적용·회귀 확인. REP-4 재설계(2026-09-20)에서 1건(`2026-09-20-001` 합격 기준이 실행 중인 시스템을 증명하도록 요구하지 않아 단일 프로세스 대체 관측이 통과하려 함). 그 기준으로 돌린 첫 실행에서 1건 더(`2026-09-20-002` 조인 기준이 blind 실행자가 알 수 없는 산출물 규약을 요구함). 입력 보완 뒤 실행에서 1건 더(`2026-09-20-003` 기준 (1)(2)가 서로 충돌하는 조건을 한 캡처에서 요구함) + `2026-09-17-001` 에 reflog 누출 경로 추가. 완화 기준 첫 실행에서 1건 더(`2026-09-20-004` 남은 미충족이 관측이 아니라 서류 요구 — 기준을 세 줄로 줄이자는 제안. 2026-09-21 에 적용하고 네 실행을 재채점 — r5 만 pass, 가짜 이벤트 소스 실행은 여전히 fail). 개정 기준 첫 실행(r6)에서 3건(`2026-09-22-001` 실행자가 improvement-log 후보에서 합격 기준을 읽어 blind 가 partial — 가드가 판정 문서 두 곳만 막음, `2026-09-22-002` CI bench 가 측정 한 번으로 판정해 문서만 바꾼 PR 에서 떨어짐, `2026-09-22-003` 실행자가 기본 개발 compose 프로젝트를 `down -v` 로 내려 기존 개발 볼륨을 지움). 그 후속 작업에서 1건 더(`2026-09-23-001` 보호 파일의 수동 커밋이 사람에게만 마찰로 남고, 로컬 가드는 스크립트 한 겹으로 우회된다 — 층별 역할 정리 제안). 지침 문서 감사(2026-09-23, prompt-audit 절차)에서 2건(`2026-09-23-002` AGENTS.md 의 모델 핀·미강제 규약·중단 문장 충돌·예산 숫자 중복, `2026-09-23-003` implementer frontmatter 가 지금 지원되는 필드를 쓰지 않음 — 턴 수 실측 포함). 가드 확장 뒤 blind 실행(r7)에서 1건 더(`2026-09-23-004` 합격 기준이 입력에 없는 산출물 규약을 요구 — 기준을 읽은 r6 은 pass, 읽지 못한 r7 은 같은 질의 관측에도 fail. 2026-09-20-002 와 같은 뿌리의 2회째) + `2026-09-13-002` 재발 1회(구현 먼저). 입력 개정 뒤 blind 실행(r8)이 세 줄 기준을 모두 충족해 **4차 기준의 첫 blind pass** 가 나왔고, `2026-09-20-004` 와 `2026-09-23-004` 를 `validating` 으로 올렸습니다. `2026-09-22-001`(가드 확장)은 REP-7 blind 재실행이 남아 candidate 입니다. 2026-09-19 에 다섯 건(`2026-09-17-001`·`002`·`004`·`005`, `2026-09-19-002`)을 `validating` 으로 올렸습니다 — 제안한 하네스 변경을 실제로 적용했고 대표 task 쪽 회귀 확인을 마쳤습니다. 나머지는 `status: candidate` 이고 전부 `trust: untrusted` 이며 `promoted` 는 아직 0건입니다. `promoted` 로 올리려면 held-out 세트에서도 회귀가 없어야 하는데(PG-3), 그 세트의 첫 실행 시점은 문서가 AD-3 으로 정하고 있고 HLD-4·HLD-5 는 전제(MCP)가 아직 없습니다.

이 13건은 Phase 0 실행(P0-1 ~ P0-6, P0-8) 중 실제로 관측되어 `PROVENANCE.md` 8절 이력·커밋 본문·테스트 docstring 에 그림자 로그로만 남아 있던 사건들과, 이 항목을 발급하는 세션 자체에서 재현한 사건(`2026-09-11-004`, guard hook 오탐) 하나를 포함합니다. `validate` 는 통과했지만 사람의 승격 판정(`../harness/rules/promotion-gate.rule.md`)은 아직 거치지 않았습니다 — 그 전까지는 여기 적힌 내용을 결론이 아니라 후보로 다룹니다.

AD-1(Day 1)의 "비어 있는 것이 정상" 규칙([../harness/references/harness-adoption.md](../harness/references/harness-adoption.md) 3.3)은 검증(verify)이 자리 잡기 전 단계의 이야기였습니다. P0-7 이 그 단계를 닫았으므로, 지금부터 남기는 항목은 상상이 아니라 관측입니다.

## 항목 만들기

손으로 파일을 복사하지 않습니다. 스크립트가 id 를 발급하고 파일명을 맞춥니다.

```bash
./harness/scripts/improvement-log.sh new
./harness/scripts/improvement-log.sh list
./harness/scripts/improvement-log.sh validate
```

## 무엇을 남기는가

작업이 끝날 때 한 가지만 묻습니다.

> 이번 작업에서 에이전트가 겪은 문제 중, 다음 작업을 위해 시스템에 남겨야 할 것은 무엇인가.

남길 값이 있다면 자연어 지시가 아니라 test, lint, arch-rule, hook, script 중 하나로 바꿉니다. 강제력 등급은 [../harness/HARNESS.md](../harness/HARNESS.md) 의 EL-1 … EL-7 을 따르고, 가능한 한 높은 등급을 고릅니다.

aether 에서 특히 높은 등급으로 올려야 할 것은 [../docs/architecture.md](../docs/architecture.md) 의 AR-1 ~ AR-7 입니다. 지금은 문서(EL-2)이고, Phase 0 에서 `.importlinter` 와 `.dependency-cruiser.cjs` 로 옮기면 EL-6 이 됩니다.
