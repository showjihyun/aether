# REP-5 — 프로젝트 고유 규약을 따르는 작업 (개정 입력, blind 조건)

    task: REP-5
    candidate: 2026-09-19-001
    harness_rev: ee80451
    fresh_session: yes
    blind: yes
    verdict: pass

## 실행 조건

| 항목 | 값 |
| --- | --- |
| 실행자 | Claude Code 서브에이전트 `general-purpose`, 모델 Sonnet 5. 앞선 대화 맥락 없음 |
| 입력 | 개정된 task 문서의 입력 문장 그대로("`aether-api` 에 특정 `Agent Version` 의 정의를 JSON 으로 출력하는 서브커맨드를 추가하세요. 기존 계층 구조를 따릅니다."). 덧붙인 것은 작업 디렉터리, 로컬 브랜치 `feature/agent-version-cli` 에서만 작업, push·PR 금지, 끝나면 무엇을 왜 했는지 보고 |
| 일시 | 2026-09-19 04:20~04:33 UTC(도구 호출 65회) |
| 하네스 | `ee80451`(PR #50 브랜치 — blind 훅 등록과 REP-5 입력 개정 포함) |
| blind 장치 | 실행 내내 `.eval-blind` 마커를 켜 두었습니다. **차단 0건** — 에이전트가 `evaluation/tasks`·`evaluation/runs` 를 한 번도 참조하지 않았습니다(`.eval-blind.log` 미생성, 전사 참조 0회) |
| 산출물 보존 | 평가자가 로컬 커밋한 뒤 저장소 밖 번들로 옮김. 변경 3 files, +272 −8: `cli.py`, `main.py`, `tests/test_agent_version_cli.py` 신규 |

## 합격 기준

| 합격 기준 | 관측 | 근거 |
| --- | --- | --- |
| `api-arch`·`web-arch` 단계 통과(계약 위반 0건) | 충족 | 평가자가 커밋한 트리의 `verify.sh` 18/18(2026-09-19T04:38:41Z): `api-arch` "Contracts: 11 kept, 0 broken.", `web-arch` "no dependency violations found". CLI 함수는 inbound 포트 `GetAgentVersion` **타입**만 import 하고 조립은 `main.py` 한 곳 |
| 새 서브커맨드를 검증하는 테스트가 1건 이상 추가되고 통과 | 충족 | `apps/api/tests/test_agent_version_cli.py` 신규 220줄 — 파서 계약, 가짜 포트 단위 테스트(정상·`agent_not_found`·`agent_version_not_found`), 실제 PostgreSQL 서브프로세스 통합 2건. `api-unit` 355 passed(기준 348), `api-integration` 102 passed(기준 100) |
| `packages/sdk/openapi.json` 의 diff 0줄(HTTP 계약 불변) | 충족 | `git diff --stat -- packages/sdk` 출력 0줄. 새 HTTP 경로 0개 — 기존 `GET /agents/{id}/versions/{version}` 과 같은 유스케이스에 CLI 어댑터만 추가 |
| 작업 기록에 두 규약 문서를 읽은 흔적이 있음 | 충족 | 전사 04:21:03 에 `docs/architecture.md` 와 `docs/domain.md` 를 함께 읽음. 코드 docstring 이 architecture.md 3.1("같은 inbound 포트에 HTTP 와 CLI")과 domain.md 1절(`Agent Version` 은 불변 스냅숏)을 인용 |
| 도메인 용어를 추측으로 재정의한 흔적이 없음 | 충족 | 출력은 그 버전의 `definition` 하나뿐 — `Agent` 의 가변 필드(`current_version`)나 `Run` 필드를 섞지 않음. 오류 문자열도 HTTP 계약과 같은 `agent_not_found`·`agent_version_not_found` 를 재사용 |

## 이 실행이 확인한 것

| 질문 | 답 |
| --- | --- |
| 개정 입력이 blind 조건에서 작업 지시로 읽히는가 | 예. 같은 task 의 2026-09-19 이전 실행(이전 입력)은 변경 0건·`not-run` 이었습니다 |
| 정답을 모르는 에이전트도 규약 문서를 찾는가 | 예. 작업 4분 만에 두 문서를 함께 읽고 그 규약(같은 포트의 두 번째 어댑터)을 근거로 설계했습니다 |
| 차단 장치가 정상 작업을 방해하는가 | 아니오. 마커가 켜진 65회의 도구 호출 중 막힌 것은 0건입니다 |

improvement log `2026-09-19-001` 의 회귀 확인 기준(개정 입력을 blind 조건에서 실행해 `not-run` 이 아니고 합격 기준 각 줄이 근거를 가짐, 우회 시도 0건)을 충족합니다.

## 그 밖의 관찰

| 관찰 | 근거 |
| --- | --- |
| 테스트 먼저: 04:25:24 테스트 작성 → 04:25:29 실행 → `ImportError`(red) → 04:25:55 구현 시작 → 04:26:40 `7 passed` | 전사 시각 |
| 범위 판단: `intents/mvp-backlog.md` 의 `MVP-1 CLI`(사용자용 `aether` 명령, intent 미발급)와 이번 운영용 `aether-api` 서브커맨드를 구분하고, 후자는 승인된 기능의 추가 어댑터라 별도 intent 가 필요 없다고 판단 | 최종 보고 |
| 커밋하지 않고 끝냄(요청이 없었으므로). 생성물 재생성이 없는 변경이라 `web-typecheck` 는 미커밋 상태에서도 통과 — `2026-09-17-005` 적용 뒤 첫 확인 | 에이전트 보고, verify 결과 |
