# MVP-1 — `aether` CLI

**HTTP 를 직접 치지 않고 제품을 쓸 수 있게** 됐습니다. `aether up` → `agent create` → `run` → `runs get` 으로 Agent 하나를 만들어 돌리고 이벤트를 스트림으로 봅니다. 이 단위는 **AR-14 의 첫 손님**이기도 합니다 — 그 계약은 PR #164 까지 빈 패키지를 가리키며 아무것도 막지 않았습니다.

## 무엇이 생겼는가

- **`apps/cli`** — `aether` 콘솔 스크립트와 명령 다섯(`up`·`agent create`·`agent list`·`run`·`runs get`). `dependencies` 는 **비어 있습니다**.
- **표준 라이브러리만으로 HTTP** — `urllib` 기반 transport 와 **SSE 파서**(청크로 읽어 `data:` 를 파싱, `run.finished` 에서 종료).
- **계약을 한 곳에** — `contract.py` 에 경로·메서드를 모으고 **드리프트 테스트**가 `openapi.json` 과 맞는지, 다른 모듈에 경로 리터럴이 없는지 봅니다.
- **격리 compose** — `aether up` 이 고정 프로젝트 이름(기본 `aether-dev`)으로 띄우고, 임시 `.env` 를 만들고 끝나면 지웁니다. `--down` 은 **그 프로젝트만** 내립니다.

## 왜 그렇게 했는가

- **CLI 가 Python 인데 SDK 는 TypeScript** 입니다(사람 결정, spec 0006 D-1). 그래서 AR-1 의 "SDK 만 쓴다" 를 문자 그대로 지킬 수 없고, 규칙의 **뜻**(제품 코드를 보지 않고 공개 계약만 쓴다)을 **AR-14** 로 강제합니다.
- **`httpx` 를 쓸 수 없습니다** — AR-5 가 저장소 전체에서 금지하고 허용된 자리는 `model_gateway` 하나입니다. `requests`·`aiohttp` 를 들이면 보호 파일을 고쳐야 합니다. 그래서 **표준 라이브러리**이고, 그 결과 **설치할 것이 늘지 않습니다**(DP-4 — On-Prem·Air-Gapped 가 제품 요구입니다).
- **키는 환경변수로만** 받습니다(D-8). 없으면 **요청을 보내지 않고** exit 2 입니다 — 키 없이 보낸 요청이 서버 로그에 남는 것보다 낫습니다.
- **프로젝트 이름을 검사합니다.** 이름이 비면 `down -v` 가 **기본 프로젝트의 개발 볼륨**을 지울 수 있습니다(`improvement-log/2026-09-22-003` 의 선례). 그래서 `^[a-z0-9][a-z0-9_-]*$` 가 아니면 exit 2 입니다.
- **스트림을 모으지 않습니다.** 이벤트는 도착하는 대로 한 줄씩 나갑니다 — 모아서 내보내면 "지금 무엇을 하고 있나" 를 볼 수 없고, 그것이 CLI 로 Run 을 보는 이유의 절반입니다.
- **출력 인코딩을 로케일에 맡기지 않습니다** — `stream.buffer` 에 UTF-8. cp949 에서 터진 전례가 있습니다(`2026-09-11-005`).

## 하네스 근거

| 줄 | 내용 |
| --- | --- |
| **요구** | spec 0006 **R-1**(CLI 만으로 생성 → Run → 스트림 → 조회) · **R-2**(제품 코드 import 금지) · **R-3**(HTTP 라이브러리 금지) |
| **결정** | **D-1**(Python·`urllib`·`openapi.json` 이 계약) · **D-2**(AR-1 개정과 AR-14) · **D-8**(키는 환경변수로만) |
| **단계** | `api-unit`(명령마다 경로·본문·출력·종료 코드, 키 없음, cp949 stdout) · `api-arch`(**AR-14·AR-5 가 실제 코드에서 통과 — 14 kept**, `dependencies` 가 비어 있는지) · `api-integration`(격리 compose 에서 CLI 를 **서브프로세스로** — `succeeded` 와 스트림 출력) |
| **증거** | PR [#166](https://github.com/showjihyun/aether/pull/166) 본문. 변이 **여덟**이 각자 다른 단언에서 발화했습니다 |

## 정한 것과 다른 점

- **`aether up` 에 옵션 넷을 더했습니다**(`--project`·`--compose-file`·`--no-build`·`--down`) — 통합 테스트가 `aether up` 자체를 검증하려면 포트·프로젝트를 바꿀 수 있어야 했습니다.
- **`aether up` 은 키를 발급하지 않습니다** — 발급 명령을 안내만 합니다(D-8: 키 원문이 stdout 에 나가는 자리는 발급 한 번뿐).
- **`web` 서비스는 띄우지 않습니다** — 화면이 아직 없습니다(MVP-2 가 더합니다).
- **`agent list` 에 `ID` 열을 더했습니다** — 그것이 없으면 `run` 에 넘길 값이 없습니다.
- **red 순서가 일부 뒤바뀌었습니다** — 배관 모듈(`contract`·`output`·`sse`·`transport`)은 구현이 먼저였고, 명령 계층은 테스트가 먼저였습니다(`ModuleNotFoundError: No module named 'aether_cli.main'`). 뒤바뀐 쪽은 **변이 여덟**으로 갈음했습니다.
- **Docker 함정 하나**: compose 의 포트 override 는 `!override [...]` 입니다. `!reset [...]` 는 값을 **비웁니다** — 처음에 그렇게 썼다가 `docker compose config` 로 원인을 찾았습니다.

## 남긴 것

- **Linux·macOS 에서 돌려 보지 않았습니다**(Windows + Docker Desktop 에서만). CI 가 Linux 이므로 통합 단계가 그것을 봅니다.
- `SMOKE_NO_BUILD=1`(CI 캐시 경로)은 코드에 있지만 **돌리지 않았습니다**.
- **CI 예산 영향**: 이 단위의 통합 2건이 스택 하나를 공유해 약 86초입니다. `e2e` 단계(H-2)가 들어오면 그 숫자와 함께 사람이 예산을 봅니다.
- `aether up` 의 **실제 `docker compose up` 을 단위 테스트가 돌리지는 않습니다** — runner 를 fake 로 꽂아 인자만 봅니다. 실제 실행은 통합이 봅니다.
