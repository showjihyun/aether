# Quickstart 밟아 보기 — 에이전트 dry-run, 2026-10-20

**이것은 TTFSA 측정이 아니고 R-12 의 근거도 아닙니다.** 저장소를 모르는 에이전트 하나를 `docs/quickstart.md` **한 장만** 주고 띄워, 그 문서가 **어디서 끊기는가**를 찾은 기록입니다. 에이전트는 측정자가 될 수 없습니다(spec 0006 **D-7**) — 재야 하는 것은 "사람이 헤맨 시간" 이고 에이전트에게는 그 값이 없습니다. 파일 이름을 `ttfsa-<날짜>.md` 와 다르게 둔 이유가 그것입니다.

| 항목 | 값 |
| --- | --- |
| 실행자 | 독립 에이전트 1개(별도 worktree, 저장소 지식 없음, `docs/quickstart.md` 외 문서 읽기 금지) |
| 날짜 | 2026-10-20 |
| 커밋 | `37dce69` |
| 결과 | **첫 Run 은 `succeeded` 가 되지 못했습니다** — 4절에서 worker 가 종료(exit 1), 6절 Run 은 `queued` 에서 멈춤 |
| 0~6절 소요(실측) | **332초**(정리 포함 369초). 그중 기다린 시간 약 107초(모델 31초 + `up --build` 76초) |
| 모델 다운로드 | **실제로 일어났습니다** — 시작 전 `docker volume ls` 에 aether 볼륨 0개. 397 MB, 36 MB/s, 31초 |
| 추적 파일 변경 | 없음(`git status --short` 비어 있음). 만든 것은 gitignore 대상 `infra/docker/.env` 하나 |

## 왜 실패했는가 — 원인은 문서가 아니라 이 실행의 조건입니다

이 머신에는 당신의 작업 스택이 있을 수 있어 **compose 프로젝트 이름을 `aether-dev` → `aether-dryrun` 으로 바꾸라고 제가 지시했습니다**(유일한 일탈). 에이전트는 Quickstart 의 모든 compose 명령에 그 이름을 넣었지만 3절의 `scripts/fetch-model.sh` 에는 넣을 방법을 찾지 못해 `COMPOSE_PROJECT_NAME` 을 앞에 붙였고, 스크립트가 그것을 무시해 **모델이 `aether-dev` 볼륨에 들어갔습니다.** 그래서 `aether-dryrun` 스택의 worker 가 "모델이 볼륨에 없습니다" 로 멈췄습니다.

**즉 Quickstart 를 문서 그대로(`-p aether-dev`) 따랐다면 이 실패는 일어나지 않습니다.** 이 기록을 "Quickstart 가 깨졌다" 로 읽으면 틀립니다.

## 에이전트가 틀린 것 (주 세션 검증, 2026-10-20)

보고서를 그대로 옮기지 않았습니다. 두 건은 확인 결과 **사실이 아닙니다.**

| 에이전트의 주장 | 확인 |
| --- | --- |
| "`fetch-model.sh` 는 프로젝트 이름을 받지 않는다 → `aether-dev` 외의 이름으로는 Quickstart 를 완주할 수 없다" | **틀렸습니다.** 그 스크립트는 `--project <이름>` 과 `AETHER_FETCH_PROJECT` 를 받고, 자기 머리말 사용법에 그렇게 적혀 있습니다(`scripts/fetch-model.sh` 11·29·35행). 에이전트가 쓴 `COMPOSE_PROJECT_NAME` 이 그 손잡이가 아니었을 뿐입니다 |
| "정리 절(`down -v`)이 `compose.yaml` 하나만 써서 llm 자원을 못 지운다" | **틀렸습니다.** `ollama_models` 는 오버레이가 아니라 `compose.yaml` 203~206행에 정의돼 있어 `down -v` 가 지웁니다 |

남는 사실은 **문서가 `--project` 를 한 번도 말하지 않는다**는 것입니다 — 3절은 "`-p` 를 **모든** compose 명령에 붙이십시오" 를 가장 큰 경고로 달면서, 그 다음 줄의 스크립트에 같은 값을 넘기는 방법을 주지 않습니다.

## 살아남은 마찰 (제가 각각 확인했습니다)

| # | 무엇 | 왜 문제인가 |
| --- | --- | --- |
| F-1 | 3절이 `--project`·`AETHER_FETCH_PROJECT` 를 말하지 않습니다 | 같은 절의 경고가 "프로젝트 이름은 당신이 고른다" 를 전제하는데 고를 방법이 그 절에 없습니다 |
| F-2 | **4절의 유일한 확인이 `curl /healthz` 이고, worker 가 죽어도 그것은 `ok` 입니다** | `/healthz` 는 설계상 DB·worker 를 보지 않습니다(P0-2). 실제로 깨진 것을 알려 준 건 `up --wait` 의 **exit 1** 과 `docker compose logs worker` 인데 둘 다 문서에 없습니다. healthz 만 믿은 사람은 6절에서 매달린 CLI 를 보고서야 압니다 |
| F-3 | worker 가 없을 때 `aether run` 이 **무한 대기**합니다(관측 1회) | `run: <id>` 한 줄 뒤 아무 이벤트도 오지 않고 타임아웃이 없습니다. 6절 증상 표에 "CLI 가 멈춘다" 항목이 없어, 에이전트는 프로세스를 직접 죽였습니다 |
| F-4 | 0절 준비물에 **`openssl` 이 없습니다** | 2절이 `openssl rand -hex 24` 를 예로 줍니다 |
| F-5 | 2절이 "**네 줄**을 고칩니다" 라고 하지만 실제로 고치는 키는 **여섯 개**입니다 | 표 첫 행이 비밀값 셋을 한 행에 묶어 세는 수가 달라집니다 |
| F-6 | **셸 전제가 없습니다** | 4절의 `AETHER_VERSION=$(git describe …) docker compose …` 는 PowerShell 에서 파서 오류입니다. 이 문서만 읽는 Windows 사용자는 4절에서 즉시 막힙니다 |
| F-7 | `migrate` 가 설계상 끝나는 일회성 서비스라는 말이 없습니다 | 4절 출력의 `migrate-1 Exited` 가 실패처럼 보입니다 |
| F-8 | 5절·6절의 **출력 형태**를 보여주지 않습니다 | 키 원문과 `id=…` 가 각각 어느 줄인지, `agent create` 의 UUID 한 줄이 "위에서 출력된 id" 인지 추측해야 했습니다 |
| F-9 | 3절 표기는 "약 379 MB", 실제 pull 은 **397 MB** | 작지만 같은 문서의 숫자입니다 |

> **2026-10-20 후속**: 문서만 고치면 되는 여덟 건(F-1·F-2·F-4 ~ F-9)은 같은 날 고쳤습니다. **F-3 의 제품 절반**(worker 없을 때 `aether run` 의 무한 대기)은 그대로 남습니다 — 증상 표에 대처만 적었습니다. **그래서 H-4 를 재는 사람은 "수정 뒤" 의 문서를 보게 됩니다**, 그 사실을 측정 기록에 적어야 합니다.

**얻지 못한 것**: 사람이 헤맨 시간. F-5·F-8 처럼 "두 번 읽었다" 는 보고가 그 자리의 그림자이지만, 분으로 환산할 수 없습니다. 그것이 **H-4 가 여전히 필요한 이유**입니다.

## 조건에 대한 경고

이 머신은 **Docker 레이어 캐시가 이미 따뜻했습니다** — `up --build` 가 76초에 끝났습니다. 캐시 없는 머신이라면 4절이 훨씬 깁니다. **이 332초를 cold 시간으로 읽으면 안 됩니다.**

## 이 실행이 남긴 것

`aether-dryrun` 자원은 `down -v` 로 전부 지웠습니다. 다만 3절이 **`aether-dev`** 프로젝트에 만든 것이 남아 있습니다(제 규칙이 그 이름을 건드리지 못하게 했습니다):

- 컨테이너 `aether-dev-llm-1`(Exited 0), 네트워크 `aether-dev_default`, 볼륨 `aether-dev_ollama_models`(소형 모델 397 MB 포함)

**지울지는 사람이 정합니다.** 남겨 두면 다음 사람 측정 때 3절이 "이미 있음" 으로 즉시 끝나 **측정이 짧게 나옵니다**(그 사실을 그 기록에 적어야 합니다). 지우려면 `docker compose -p aether-dev -f infra/docker/compose.yaml -f infra/docker/compose.llm.yaml down -v` 입니다.

부수로 알게 된 것: **이 머신에는 그 전까지 aether 볼륨이 하나도 없었습니다** — 즉 **H-3**(제품 모델 17.7 GB 1회 적재)은 아직 수행되지 않았습니다.

## 관련 문서

- [../quickstart.md](../quickstart.md) — 밟은 문서
- [ttfsa-TEMPLATE.md](ttfsa-TEMPLATE.md) — 사람 측정에 쓰는 양식. 이 기록이 그것을 대신하지 않습니다
- [ttfsa-2026-10-20.md](ttfsa-2026-10-20.md) — 같은 날 사람이 R-12 를 참으로 판정한 기록. **이 dry-run 은 그 판정의 근거가 아닙니다** — 둘은 다른 사건입니다
- [../../specs/0006-mvp-integration.md](../../specs/0006-mvp-integration.md) — R-12, D-7, D-21
- [../../intents/mvp-backlog.md](../../intents/mvp-backlog.md) — F-1 ~ F-9 가 단위로 등록된 자리
