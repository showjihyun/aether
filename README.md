# aether

Cloud / Private Cloud / On-Premise / Air-Gapped / Edge 에서 같은 AI Runtime 을 실행하는 Open Hybrid Enterprise AI OS 입니다. 지금은 Phase 0(Architecture & Foundation) 입니다 — 자세한 배경은 [AGENTS.md](AGENTS.md).

## 개발 설치

```bash
uv sync --all-packages
pnpm install
```

## 비밀값

```bash
cp infra/docker/.env.example infra/docker/.env   # <generate> 를 채웁니다. 예: openssl rand -hex 24
```

## 기동

```bash
AETHER_VERSION=$(git describe --tags --always) docker compose -f infra/docker/compose.yaml up --build -d
```

첫 실행은 이미지 pull 이 필요합니다(온라인).

## 확인

```bash
curl localhost:8000/healthz   # {"status":"ok","service":"api","version":"<git describe 값>"}
```

브라우저로 http://localhost:3000 을 엽니다.

## API 키 발급

`/healthz` 와 OpenAPI 문서 경로를 제외한 모든 경로는 `Authorization: Bearer <key>` 를
요구합니다([specs/0001-phase-0-foundation.md](specs/0001-phase-0-foundation.md) 2.9).

```bash
docker compose -f infra/docker/compose.yaml exec api aether-api keys create --label <이름>
```

원문 키는 이때 **한 번만** stdout 에 출력됩니다 — 다시 조회할 방법이 없으니 그 자리에서
저장하십시오. 환경변수나 `.env` 로 키를 주입하는 부트스트랩은 없습니다.

## Run 실행해 보기

`worker` 가 실행을 맡고 `api` 는 선언·조회·취소만 합니다([docs/api.md](docs/api.md) 4절,
spec 0002 2.2, 2.4). 기본 모델 어댑터는 `fake` — 인터넷 없이 됩니다.

```bash
KEY=$(docker compose -f infra/docker/compose.yaml exec -T api aether-api keys create --label demo)

AGENT_ID=$(curl -s -X POST localhost:8000/agents \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"name": "demo-agent", "definition": {"schema_version": 1, "system_prompt": "You are a helper."}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

RUN_ID=$(curl -s -X POST "localhost:8000/agents/$AGENT_ID/run" \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"input": "hello"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")

curl -s "localhost:8000/runs/$RUN_ID" -H "Authorization: Bearer $KEY"   # status 가 곧 "succeeded"
```

`GET /runs/{id}` 를 몇 번 다시 호출하면(투영은 비동기입니다, D-2) `status` 가
`"succeeded"` 가 됩니다. 취소하려면 `POST /runs/{id}/cancel` — 진행 중인 도구·모델
호출은 끝나기를 기다린 뒤(협력적 취소, C-3) 다음 반복에서 `"cancelled"` 로 끝납니다.

그 Run 의 trace 는 `infra/docker/out/otel/spans.jsonl` 에서 위 응답의 `trace_id` 값을
검색하면 보입니다(spec 0002 2.9, R-5) — collector 의 배치 처리 때문에 몇 초 지연될
수 있습니다.

## 실제 모델로 돌리기

기본은 `AETHER_MODEL_ADAPTER=fake` - 판정(verify·smoke)은 언제나 이 어댑터로, 네트워크
없이 갑니다(spec 0002 R-6, C-7). 로컬 LLM 으로 돌리는 길은 **모델을 미리 받아 두고**
(네트워크 있는 환경에서 한 번), override 를 얹어 띄우는 것입니다. 기동 경로는 모델을 받지
않습니다.

```bash
scripts/fetch-model.sh                     # 제품 기본 모델 qwen3.8:27b 를 모델 볼륨에 적재(1회)
docker compose -p aether-dev -f infra/docker/compose.yaml -f infra/docker/compose.llm.yaml up -d --wait
```

**`-p` 를 빼면 모델을 못 찾습니다.** compose 는 `-p` 가 없으면 프로젝트 이름을 compose 파일의
디렉터리(`docker`)에서 가져오고, 볼륨 이름은 거기 붙습니다(`docker_ollama_models`). 반면
`fetch-model.sh` 와 `aether up` 은 `aether-dev` 를 씁니다 - 두 이름이 다르면 **다른 볼륨**이고,
받아 둔 모델이 스택에 보이지 않아 worker 가 "볼륨에 없다" 로 멈춥니다. 적재와 기동은 **같은
프로젝트 이름**이어야 합니다(`--project` 로 바꿀 수 있고, 둘을 같이 바꿔야 합니다).

`compose.llm.yaml` 이 worker 를 `openai_compatible`·`http://llm:11434/v1` 로 돌리고 `llm`
서비스에 의존하게 합니다(`.env` 에 `AETHER_MODEL_ID` 를 모델 태그와 맞춥니다). 모델 볼륨이
비어 있으면 worker 는 **시작할 때** 받는 방법(`scripts/fetch-model.sh`)을 적고 멈춥니다 -
Run 이 나중에 애매하게 실패하지 않습니다. `fetch-model.sh` 는 멱등이고(이미 있으면 받지
않고 그렇다고 출력), 받지 못하면 0 이 아닌 코드로 끝납니다. 기본 모델은 **17.7 GB**
(2026-10-12 레지스트리 매니페스트 실측)이라 VRAM 18 GB 이상이 필요합니다 - 없는 머신은 fake
어댑터만 씁니다. `llm` 서비스에는 GPU 예약이 없어 CPU 로 돕니다.

**소형 모델은 판정 전용입니다**(spec 0006 D-12). `scripts/fetch-model.sh --test-model` 이
`qwen2.5:0.5b`(약 400 MB)를 받고, `scripts/e2e.sh` 가 그것으로 "네트워크를 끊은 compose 에서
Run 이 `succeeded`" 와 "빈 볼륨이면 명확한 오류로 멈춤" 을 단언합니다(모델 품질은 보지
않습니다). 제품 기본값은 그대로 `qwen3.8:27b` 입니다. `e2e` 의 처음 실행은 이미지와 소형
모델을 받으므로 온라인이어야 합니다. 실제 모델로 돌린 수동 확인의 기록은
[docs/step_results/phase-3.md](docs/step_results/phase-3.md) 의 "D-13 수동 확인"(임베딩)과
"P3-3 수동 확인"(응답)입니다.

## 검증

```bash
./harness/scripts/verify.sh
```

결과는 `.harness/verify.json` 에 남습니다.

smoke(끝에서 끝까지: 격리된 compose 프로젝트로 api·worker 를 띄워 agent → run → `succeeded` 와 trace 파일까지)만 따로 돌리려면 `scripts/smoke.sh` 입니다. 개발 스택과 포트·볼륨이 겹치지 않고 끝나면 스스로 정리합니다. `scripts/smoke.sh --bench` 는 Run 생성 응답 지연을 `infra/docker/out/smoke-bench.json` 에 기록합니다(spec 0002 2.13).

## 오프라인 판정

이미지를 위 `up --build` 로 한 번 빌드해 둔 뒤:

```bash
docker compose -f infra/docker/compose.yaml down
docker compose -f infra/docker/compose.yaml -f infra/docker/compose.offline.yaml run --rm probe
```

`probe` 의 exit 코드가 0 이면 인터넷 없이 뜬 것입니다(호스트 curl 이 아니라 네트워크 안의 판정 — 이유는 [specs/0001-phase-0-foundation.md](specs/0001-phase-0-foundation.md) C-3).

## 문서 지도

- [AGENTS.md](AGENTS.md) — 저장소 진입점 지침
- [docs/README.md](docs/README.md) — 문서 전체 지도
- [DESIGN.md](DESIGN.md) — `apps/web` 표현 규약
- [intents/intent.md](intents/intent.md) — 지금 무엇을 왜 만드는가
