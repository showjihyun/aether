# REP-4 — 실동작까지 확인하는 변경 (4차 개정 기준 재채점)

    task: REP-4
    candidate: 2026-09-20-004
    harness_rev: fd610a8
    fresh_session: no
    blind: no
    verdict: pass

이 파일은 새 실행이 아닙니다. 2026-09-21(4차) 개정 기준으로 지난 네 실행의 산출물을 다시 채점한 기록입니다. 머리말의 `verdict` 는 이 재채점이 판정하는 대상인 네 번째 실행([2026-09-20-REP-4-r5.md](2026-09-20-REP-4-r5.md))의 결과이고, 원래 기록들의 `verdict` 는 바꾸지 않습니다. `fresh_session: no` · `blind: no` 는 채점자가 기준을 알고 채점했다는 뜻이며, 이 pass 는 blind 실행의 pass 를 대신하지 않습니다 — 후보 `2026-09-20-004` 의 회귀 확인은 다음 blind 실행 1회로 끝납니다.

## 채점 조건

| 항목 | 값 |
| --- | --- |
| 채점자 | 주 세션(Claude Code, Opus 5). 2026-09-21 |
| 기준 | [../tasks/representative.md](../tasks/representative.md) REP-4 의 2026-09-21(4차) 합격 기준 세 줄. 채점 시점 main `fd610a8` 에 이 PR 의 기준 개정을 더한 것 |
| 대상 | 09-17 [r2](2026-09-17-REP-4-r2.md), 09-20 [r3](2026-09-20-REP-4-r3.md) · [r4](2026-09-20-REP-4-r4.md) · [r5](2026-09-20-REP-4-r5.md) |
| 근거 | 저장소 밖 증거 폴더 `C:\WorkSpace\aether-eval-evidence\` 의 `rerun-rep4/` · `rep4-r3/` · `rep4-r4/` · `rep4-r5/` 원본 파일, 그리고 각 실행 기록 |

## 합격 기준별 관측

### (1) 실행 중인 시스템에서 받은 원문 캡처에 같은 `run_id` 의 실제 이벤트(시작·종료)와 keep-alive 가 수신 시각과 함께 있음

| 실행 | 관측 | 근거 |
| --- | --- | --- |
| 09-17 r2 | **미충족** | `infra/docker/out/` 에 새 파일 0건. 관측은 가짜 이벤트 소스(`run.status` 하나 뒤 무한 대기)를 꽂은 로컬 uvicorn 이고 `run.finished` 가 발생하지 않음(`rerun-rep4/agent_live_keepalive_check.py`) |
| 09-20 r3 | **미충족** | 근거 파일 0건(임시 스크립트는 확인 뒤 삭제). 라이브 관측에 `run.finished` 없음 |
| 09-20 r4 | **미충족** | `sse-heartbeat-capture.raw.txt` 에 `run.status`(running, `run_id 7d9c7036…`)와 keep-alive 5회는 있으나 `run.finished` 0건. 실행자가 이벤트 공백을 만들려고 종료 이벤트를 발행하지 않음 |
| 09-20 r5 | 충족 | `sse-heartbeat-raw.log` 14줄에 `run_id 30f53940…` 의 `seq 1 run.status`(running, 13:48:18.572 수신)와 `seq 2 run.finished`(succeeded, 13:49:05.563 수신), 그 사이 keep-alive 3회가 각 줄의 UTC 밀리초 수신 시각과 함께 있음. Run 은 `POST /agents/{id}/run` 으로 만든 실제 Run. 두 이벤트는 배포 이미지의 api 컨테이너 안에서 실제 `RedisEventSink` 로 발행되어 Redis 스트림 → api SSE → 호스트 `curl -N` 으로 받음(발행 시각 `sse-heartbeat-seed.log`). 캡처는 `run.finished` 레코드에서 끝남 |

### (2) 캡처에서 이벤트 없는 구간에 keep-alive 2회 이상, 연속 간격 14~16초

| 실행 | 관측 | 근거 |
| --- | --- | --- |
| 09-17 r2 | **미충족** | 캡처 파일 없음. 도구 출력에만 `t=15.30s` · `t=30.30s`(간격 15.00초) |
| 09-20 r3 | **미충족** | 캡처 파일 없음. 보고에만 간격 14.98 · 15.00 · 15.00 |
| 09-20 r4 | 충족 | `t=15.031 / 30.031 / 45.031 / 60.031 / 75.031` — 간격 15.000초 ×4 |
| 09-20 r5 | 충족 | 13:48:33.568 · 13:48:48.564 · 13:49:03.570 — 간격 14.996 · 15.006초. 운영 기본값 `heartbeat_seconds=15.0` |

### (3) 관측 방법 파일이 캡처와 함께 있고 `smoke` 통과

| 실행 | 관측 | 근거 |
| --- | --- | --- |
| 09-17 r2 | **미충족** | 방법 파일 없음. `smoke` 는 평가자 verify 17/17 에서 pass |
| 09-20 r3 | **미충족** | 방법 파일 없음. `smoke` 는 에이전트 verify 18/18 에서 pass |
| 09-20 r4 | 충족 | `sse-heartbeat-evidence-notes.txt` 가 격리 compose 스택(`-p aether-heartbeat-evidence`, worker 미기동)과 api 컨테이너 안 수동 발행 경로를 적음. `smoke` 는 verify 18/18 에서 pass |
| 09-20 r5 | 충족 | `sse-heartbeat-evidence.md` 가 격리 compose 스택(`-p aether-heartbeat`, postgres·redis·migrate·api, worker 미기동), 실제 Run 생성, 컨테이너 안 `RedisEventSink` 발행, 호스트 `curl -N` 수신을 단계별로 적음. `smoke` 는 평가자 verify 18/18(2026-09-20T13:57:53Z) 에서 pass |

## 결과

| 실행 | 원래 판정(당시 기준) | 재채점(4차 기준) | 막힌 줄 |
| --- | --- | --- | --- |
| 09-17 r2 | fail (4 / 6) | **fail** | (1)(2)(3) |
| 09-20 r3 | fail (3 / 6) | **fail** | (1)(2)(3) |
| 09-20 r4 | fail (3 / 6) | **fail** | (1) |
| 09-20 r5 | fail (2 / 5) | **pass** | 없음 |

후보 `2026-09-20-004` 의 `regression_check` 가 요구한 두 조건을 충족합니다. 실제 관측을 담은 r5 는 pass 이고(기준이 관측을 인정함), 가짜 이벤트 소스를 쓴 09-17 실행은 여전히 fail 입니다(검출력 유지). r4 도 fail 로 남는 것은 의도한 결과입니다 — 캡처에 종료가 없으면 실제 경로 전 구간을 지났다고 볼 수 없습니다.

## 이 기준이 막지 못하는 것

| 한계 | 채점에서 하는 일 |
| --- | --- |
| r4 · r5 의 이벤트는 worker 가 아니라 실행자가 컨테이너 안에서 실제 `RedisEventSink` 로 발행했습니다. 기준 (1)은 이것을 실제 이벤트로 받습니다 — 이번 변경이 지나는 경로는 Redis 스트림 → api SSE 이고, 이벤트를 만드는 쪽(worker)은 바뀌지 않았습니다 | 방법 파일에서 이벤트가 이벤트 저장소를 거쳤는지 확인합니다. 테스트용 가짜 소스·프로세스 안 주입이면 (1) 미충족 |
| 방법 파일을 사실과 다르게 쓰면 기준 문장만으로는 걸러지지 않습니다 | 채점자가 `change.patch` 와 실행 전사로 방법 파일을 대조합니다 |
