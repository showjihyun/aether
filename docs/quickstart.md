# Quickstart — clone 에서 첫 Agent 실행까지

이 문서 하나만 보고 **처음 보는 사람이 10분 안에** 첫 Agent 를 성공시키는 것이 목표입니다. 그 시간이 이 제품의 KPI 하나(TTFSA)이고, 재는 방법은 [measurements/ttfsa-TEMPLATE.md](measurements/ttfsa-TEMPLATE.md) 입니다.

**여기서 쓰는 모델은 소형 모델입니다**(`qwen2.5:0.5b`, 약 379 MB — spec 0006 **D-21**). 제품 기본 모델은 17.7 GB 라 그것을 받는 시간이 측정을 덮어 버립니다. 그래서 이 문서가 재는 것은 **저장소의 마찰**이고, 제품 모델로 바꾸는 길은 [마지막 절](#제품-모델로-바꾸기)에 따로 있습니다. 끝까지 왔을 때 당신이 가진 것은 "**로컬 모델로 답하는 Agent 하나**" 이고, "제품 모델로 쓸 수 있는 상태" 는 아닙니다.

## 0. 필요한 것

| 것 | 확인 |
| --- | --- |
| Docker (Compose v2) | `docker compose version` |
| git | `git --version` |
| [uv](https://docs.astral.sh/uv/) | `uv --version` — `aether` CLI 를 돌립니다 |
| `openssl` | `openssl version` — 2절에서 비밀값을 만듭니다(다른 난수 생성기를 쓰셔도 됩니다) |
| `curl` | `curl --version` — 4절에서 api 를 확인합니다 |

**이 문서의 명령은 bash 기준입니다**(macOS·Linux, Windows 에서는 Git Bash). PowerShell 은 환경변수를 명령 앞에 붙이는 문법(`VAR=값 명령`)과 `export` 가 없어 **4절과 5절이 그대로는 실패합니다** — 그 두 절에 PowerShell 대체 명령을 함께 적어 두었습니다.

인터넷이 **한 번** 필요합니다(이미지와 모델). 그 뒤로는 끊어도 됩니다 — 그것이 이 제품의 요구입니다.

## 1. clone 과 설치

```bash
git clone https://github.com/showjihyun/aether.git
cd aether
uv sync --all-packages
```

## 2. 비밀값 채우기

```bash
cp infra/docker/.env.example infra/docker/.env
```

`infra/docker/.env` 를 열어 **키 여섯 개**를 고칩니다(아래 표는 네 행이고, 첫 행에 비밀값 셋이 묶여 있습니다).

| 키 | 값 |
| --- | --- |
| `POSTGRES_PASSWORD` · `AETHER_CONTROL_PASSWORD` · `AETHER_DATA_PASSWORD` | `<generate>` 를 실제 값으로. 예: `openssl rand -hex 24` (셋 다 다른 값) |
| `AETHER_MODEL_ADAPTER` | `fake` → `openai_compatible` |
| `AETHER_MODEL_ID` | `qwen3.8:27b` → `qwen2.5:0.5b` |
| `AETHER_MODEL_API_KEY` | `<optional>` → 빈 값(로컬 모델은 키가 없습니다) |

채운 `.env` 는 **커밋하지 않습니다**(`.gitignore` 가 막습니다).

## 3. 모델 받기 (1회, 온라인)

```bash
scripts/fetch-model.sh --test-model
```

약 400 MB(`qwen2.5:0.5b`)를 `aether-dev` 프로젝트의 모델 볼륨에 넣습니다. 멱등입니다 — 이미 있으면 받지 않고 그렇다고 출력합니다. 마지막 줄의 `project=…` 가 **어느 프로젝트의 볼륨에 넣었는지**를 말합니다.

> **`-p aether-dev` 를 모든 compose 명령에 붙이십시오.** 볼륨 이름은 프로젝트 이름에 붙습니다. `-p` 를 빼면 compose 가 compose 파일의 디렉터리 이름(`docker`)을 쓰고, 그러면 **다른 볼륨**이라 받아 둔 모델이 스택에 보이지 않습니다. worker 는 그때 조용히 넘어가지 않고 "볼륨에 없다 + 받는 방법" 을 적고 멈춥니다. 이것이 이 저장소에서 가장 자주 밟는 돌입니다.
>
> **다른 프로젝트 이름을 쓰려면 이 스크립트에도 같은 이름을 넘기십시오** — `scripts/fetch-model.sh --test-model --project <이름>`(또는 `AETHER_FETCH_PROJECT=<이름>`). `COMPOSE_PROJECT_NAME` 은 이 스크립트가 보지 않습니다. 넘기지 않으면 모델이 `aether-dev` 볼륨으로 가고, 당신의 스택은 비어 있는 볼륨을 보게 됩니다.

## 4. 스택 띄우기

```bash
AETHER_VERSION=$(git describe --tags --always) docker compose -p aether-dev \
  -f infra/docker/compose.yaml -f infra/docker/compose.llm.yaml \
  up --build -d --wait
```

PowerShell 이면 같은 명령이 이렇게 됩니다.

```powershell
$env:AETHER_VERSION = (git describe --tags --always)
docker compose -p aether-dev -f infra/docker/compose.yaml -f infra/docker/compose.llm.yaml up --build -d --wait
```

첫 실행은 이미지를 빌드합니다(api·worker·web). **빌드 캐시가 없는 머신에서는 이 단계가 이 문서에서 가장 긴 구간입니다.**

끝나면 **세 가지**를 봅니다. 셋을 다 보는 이유는 아래에 있습니다.

```bash
echo $?                                                      # 1. 위 up 명령의 종료 코드. 0 이 아니면 뜨지 못한 서비스가 있습니다
docker compose -p aether-dev -f infra/docker/compose.yaml -f infra/docker/compose.llm.yaml ps   # 2. 서비스 상태
curl localhost:8000/healthz                                  # 3. {"status":"ok","service":"api","version":"…"}
```

> **`/healthz` 만 믿으면 안 됩니다.** 그 응답은 **api 프로세스가 살아 있다**는 뜻이고, 설계상 DB 도 worker 도 보지 않습니다. 그래서 **worker 가 죽은 스택에서도 `ok` 가 나옵니다** — 그 상태로 6절에 가면 Run 이 `queued` 에서 영원히 멈춥니다. 1번과 2번이 그것을 먼저 알려 줍니다.
>
> 2번 출력에서 `migrate` 가 `Exited (0)` 인 것은 **정상**입니다 — 마이그레이션을 한 번 돌리고 끝나는 일회성 서비스입니다. `worker` 가 `Exited` 면 비정상이고, 이유는 `docker compose -p aether-dev -f infra/docker/compose.yaml -f infra/docker/compose.llm.yaml logs worker` 가 말해 줍니다(모델이 볼륨에 없으면 그 문장과 받는 방법을 적고 멈춥니다).

## 5. API 키 발급

```bash
docker compose -p aether-dev -f infra/docker/compose.yaml \
  exec -T api aether-api keys create --label quickstart
```

출력은 **두 줄**이고 **첫 줄 전체가 키 원문**입니다(라벨이 붙지 않습니다). 둘째 줄은 `id=… label=quickstart` 로 그 키의 식별자입니다.

원문은 **이때 한 번만** 출력되고 다시 조회할 방법이 없습니다. 그 자리에서 환경변수로 둡니다.

```bash
export AETHER_API_KEY=<첫 줄 전체>
```

```powershell
$env:AETHER_API_KEY = "<첫 줄 전체>"
```

## 6. 첫 Agent 실행 — 여기서 시계를 멈춥니다

```bash
uv run aether agent create --name first-agent
uv run aether run <위에서 출력된 id> --input "한 문장으로 자기소개를 해줘"
```

`agent create` 의 출력은 **UUID 한 줄**이고, 그 줄 전체가 `aether run` 에 넣을 id 입니다.

`aether run` 은 이벤트를 **도착하는 대로** 한 줄씩 출력하다가 `run.finished` 에서 끝냅니다. 모델이 답한 글자는 `model.delta` 로 흐릅니다. 마지막 상태를 다시 보려면:

```bash
uv run aether runs get <run-id>
```

`status` 가 `succeeded` 면 **첫 Agent 가 성공한 것**입니다. 이 시점까지가 TTFSA 입니다.

실패했다면 그것도 기록할 값입니다 — 멈추지 말고 [양식](measurements/ttfsa-TEMPLATE.md)의 "막힌 지점" 에 적으십시오. 자주 보는 둘:

| 증상 | 원인 |
| --- | --- |
| worker 가 "모델이 볼륨에 없습니다 + `scripts/fetch-model.sh`" 로 멈춤 | 3번과 4번의 `-p` 가 다릅니다. 또는 `.env` 의 `AETHER_MODEL_ID` 가 받은 태그와 다릅니다 |
| CLI 가 `exit 2` | `AETHER_API_KEY` 가 없습니다(키는 **환경변수로만** 받습니다 — 파일에 쓰지 않습니다) |
| `aether run` 이 `run: <id>` 한 줄만 찍고 **아무 이벤트 없이 멈춰 있다** | 이벤트를 만들 **worker 가 없습니다.** 지금 CLI 에는 타임아웃이 없어 그대로 기다립니다 — `Ctrl+C` 로 끊고 4절의 1·2번(종료 코드·`ps`)과 `logs worker` 를 보십시오. 다른 창에서 `uv run aether runs get <run-id>` 가 `queued` 면 같은 원인입니다 |

## 7. 화면 보기 (선택)

브라우저는 api 를 직접 부르지 않고 **web 서버가 중계**합니다(spec 0006 D-15). 그래서 화면에는 **별도의 키**가 필요하고, 키는 스택이 뜬 뒤에 발급되므로 **한 번 더** 띄워야 합니다.

```bash
docker compose -p aether-dev -f infra/docker/compose.yaml \
  exec -T api aether-api keys create --label web
# 출력된 값을 infra/docker/.env 의 AETHER_WEB_API_KEY 에 넣고:
docker compose -p aether-dev -f infra/docker/compose.yaml up -d --wait web
```

http://localhost:3000 — 사이드바는 Agents·Runs·Knowledge·Workflows·Settings 다섯입니다. 방금 만든 Agent 와 Run 이 거기 보입니다. Agent 이름을 누르면 대화 화면이고, 그 화면은 **각 입력이 독립 Run 이라는 사실**을 맨 위에 적습니다(이력을 받는 API 가 없습니다).

키를 비워 두면 화면이 "api 키가 없습니다" 로 그 사실을 말합니다 — 조용히 빈 화면이 되지 않습니다. 그 키는 web 컨테이너 안에만 있고 브라우저로 가지 않습니다.

## 제품 모델로 바꾸기

위에서 쓴 것은 **판정·Quickstart 전용 소형 모델**입니다. 제품 기본값은 `qwen3.8:27b`(17.7 GB, VRAM 18 GB 이상)입니다.

```bash
scripts/fetch-model.sh            # 제품 기본 모델. 네트워크 있는 환경에서 1회
# infra/docker/.env 의 AETHER_MODEL_ID 를 qwen3.8:27b 로 되돌리고 4번을 다시 실행
```

`llm` 서비스에는 GPU 예약이 없어 CPU 로 돕니다 — VRAM 이 없는 머신은 `AETHER_MODEL_ADAPTER=fake` 로 두고 쓰십시오(판정은 언제나 그 어댑터로, 네트워크 없이 갑니다).

## 다 끝내고 지우기

```bash
docker compose -p aether-dev -f infra/docker/compose.yaml down -v
```

`-v` 가 볼륨(모델 포함)까지 지웁니다. 모델을 남기려면 `-v` 를 빼십시오.

## 다음에 읽을 것

- [cli.md](cli.md) — `aether` 명령 전부
- [api.md](api.md) — HTTP 계약
- [../README.md](../README.md) — 개발·검증·오프라인 판정
- [measurements/ttfsa-TEMPLATE.md](measurements/ttfsa-TEMPLATE.md) — 이 문서로 걸린 시간을 재는 양식
