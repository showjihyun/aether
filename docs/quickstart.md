# Quickstart — clone 에서 첫 Agent 실행까지

이 문서 하나만 보고 **처음 보는 사람이 10분 안에** 첫 Agent 를 성공시키는 것이 목표입니다. 그 시간이 이 제품의 KPI 하나(TTFSA)이고, 재는 방법은 [measurements/ttfsa-TEMPLATE.md](measurements/ttfsa-TEMPLATE.md) 입니다.

**여기서 쓰는 모델은 소형 모델입니다**(`qwen2.5:0.5b`, 약 379 MB — spec 0006 **D-21**). 제품 기본 모델은 17.7 GB 라 그것을 받는 시간이 측정을 덮어 버립니다. 그래서 이 문서가 재는 것은 **저장소의 마찰**이고, 제품 모델로 바꾸는 길은 [마지막 절](#제품-모델로-바꾸기)에 따로 있습니다. 끝까지 왔을 때 당신이 가진 것은 "**로컬 모델로 답하는 Agent 하나**" 이고, "제품 모델로 쓸 수 있는 상태" 는 아닙니다.

## 0. 필요한 것

| 것 | 확인 |
| --- | --- |
| Docker (Compose v2) | `docker compose version` |
| git | `git --version` |
| [uv](https://docs.astral.sh/uv/) | `uv --version` — `aether` CLI 를 돌립니다 |

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

`infra/docker/.env` 를 열어 **네 줄**을 고칩니다.

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

약 379 MB 를 `aether-dev` 프로젝트의 모델 볼륨에 넣습니다. 멱등입니다 — 이미 있으면 받지 않고 그렇다고 출력합니다.

> **`-p aether-dev` 를 모든 compose 명령에 붙이십시오.** 볼륨 이름은 프로젝트 이름에 붙습니다. `-p` 를 빼면 compose 가 compose 파일의 디렉터리 이름(`docker`)을 쓰고, 그러면 **다른 볼륨**이라 받아 둔 모델이 스택에 보이지 않습니다. worker 는 그때 조용히 넘어가지 않고 "볼륨에 없다 + 받는 방법" 을 적고 멈춥니다. 이것이 이 저장소에서 가장 자주 밟는 돌입니다.

## 4. 스택 띄우기

```bash
AETHER_VERSION=$(git describe --tags --always) docker compose -p aether-dev \
  -f infra/docker/compose.yaml -f infra/docker/compose.llm.yaml \
  up --build -d --wait
```

첫 실행은 이미지를 빌드합니다(api·worker·web). 끝나면 확인합니다.

```bash
curl localhost:8000/healthz   # {"status":"ok","service":"api","version":"…"}
```

## 5. API 키 발급

```bash
docker compose -p aether-dev -f infra/docker/compose.yaml \
  exec -T api aether-api keys create --label quickstart
```

원문은 **이때 한 번만** 출력되고 다시 조회할 방법이 없습니다. 그 자리에서 환경변수로 둡니다.

```bash
export AETHER_API_KEY=<위에서 출력된 값>
```

## 6. 첫 Agent 실행 — 여기서 시계를 멈춥니다

```bash
uv run aether agent create --name first-agent
uv run aether run <위에서 출력된 id> --input "한 문장으로 자기소개를 해줘"
```

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
