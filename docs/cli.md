# `aether` CLI

MVP-1 이 만든 명령줄 진입점입니다. **읽기용 요약이고 정본은 두 곳**입니다 — 명령의 동작은 `apps/cli` 의 테스트, 계약은 `packages/sdk/openapi.json` 입니다.

`aether-api`·`aether-worker` 와 다릅니다. 그 둘은 **운영자용**(키 발급·스키마 출력·worker 프로세스)이고, `aether` 는 **제품을 쓰는 사람**의 명령입니다.

## 명령

| 명령 | 하는 일 |
| --- | --- |
| `aether up [--project P] [--compose-file F]… [--no-build]` | 격리 compose 프로젝트(기본 `aether-dev`)로 스택을 띄웁니다. 임시 `.env` 를 만들고 **끝나면 지웁니다**. 키가 필요 없습니다 |
| `aether up --down [--project P]` | **그 프로젝트의** 스택과 볼륨만 내립니다 |
| `aether agent create --name N [--prompt P]` | Agent 를 만들고 id 한 줄을 출력합니다. `--prompt` 를 생략하면 기본 system prompt 를 보냅니다(`AgentDefinition.system_prompt` 가 필수입니다) |
| `aether agent list` | `ID NAME CURRENT_VERSION UPDATED_AT` 표. `next_cursor` 를 끝까지 따라갑니다 |
| `aether run <agent-id> --input T` | Run 을 만들고 **이벤트를 도착하는 대로 한 줄씩** 출력하다가 `run.finished` 에서 끝냅니다 |
| `aether runs get <run-id>` | 상태·시각·실패 사유·`trace_id` |

## 환경변수

| 변수 | 기본 | 뜻 |
| --- | --- | --- |
| `AETHER_API_KEY` | (필수) | **키는 환경변수로만** 받습니다 — 파일에 쓰지 않고 로그·오류 메시지에도 싣지 않습니다(spec 0006 D-8). 없으면 **exit 2** 이고 요청을 보내지 않습니다 |
| `AETHER_API_URL` | `http://localhost:8000` | API 주소 |

키 원문이 stdout 에 나가는 자리는 **발급 한 번**뿐입니다(`aether-api keys create`). 그래서 `aether up` 은 키를 발급하지 않고 **발급 명령을 안내**합니다.

## 종료 코드

| 코드 | 뜻 |
| --- | --- |
| 0 | 성공 |
| 1 | 실행 실패 — 서버 오류, Run 이 `succeeded` 가 아님, 스트림 연결 끊김, `run.finished` 없이 끝남 |
| 2 | 사용 오류 — 인자가 틀림, `AETHER_API_KEY` 없음, 프로젝트 이름이 `^[a-z0-9][a-z0-9_-]*$` 가 아님 |

**프로젝트 이름을 검사하는 이유**: 이름이 비면 `docker compose down -v` 가 **기본 프로젝트의 개발 볼륨**을 지울 수 있습니다. 그 사고의 선례가 `improvement-log/2026-09-22-003` 입니다.

## 이 CLI 가 지키는 경계

- **제품 코드를 import 하지 않습니다**(AR-14). `aether_api`·`aether_runtime`·… 를 한 줄도 쓰지 않고, 공유하고 싶은 타입이 있어도 다시 적습니다. 강제는 `.importlinter` 의 AR-14 이고 `tests/arch` 의 주입 케이스가 그것을 봅니다.
- **HTTP 클라이언트 라이브러리를 쓰지 않습니다** — 표준 라이브러리 `urllib` 뿐입니다(spec 0006 D-1). `httpx` 는 AR-5 가 저장소 전체에서 금지하고, `apps/cli/pyproject.toml` 의 `dependencies` 는 **비어 있는 채로** 유지되며 그것을 보는 테스트가 있습니다. On-Prem·Air-Gapped 에서 설치할 것을 늘리지 않는 선택입니다(DP-4).
- **경로를 코드에 흩뿌리지 않습니다** — `contract.py` 한 곳에 모으고, **드리프트 테스트**가 그 전부가 `openapi.json` 에 실재하는지 봅니다(다른 모듈에 경로 리터럴이 있으면 실패합니다).
- **출력 인코딩을 로케일에 맡기지 않습니다** — `stream.buffer` 에 UTF-8 로 씁니다. cp949 에서 `UnicodeEncodeError` 로 터진 전례가 있습니다(`improvement-log/2026-09-11-005`).

## 관련 문서

- [api.md](api.md) — HTTP 계약(이 CLI 가 쓰는 경로의 정본은 `packages/sdk/openapi.json`)
- [architecture.md](architecture.md) — AR-1(web·CLI 의 경계)과 AR-14
- [../specs/0006-mvp-integration.md](../specs/0006-mvp-integration.md) — D-1·D-2·D-8
- [step_results/mvp-1.md](step_results/mvp-1.md) — 이 단위가 무엇을 만들었는가
