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

기본은 `AETHER_MODEL_ADAPTER=fake` — 판정(verify·smoke)은 언제나 이 어댑터로, 네트워크
없이 갑니다(spec 0002 R-6, C-7). 로컬 LLM 서버로 직접 돌려 보려면:

```bash
docker compose -f infra/docker/compose.yaml --profile llm up -d llm
docker compose -f infra/docker/compose.yaml exec llm ollama pull qwen3.8:27b
```

그다음 `infra/docker/.env` 에서 `AETHER_MODEL_ADAPTER=openai_compatible` 로 바꾸고
worker 를 재기동합니다. 기본 테스트 모델(Qwen3.8 27B 양자화, 태그 `qwen3.8:27b`)은
VRAM 약 18 GB 이상이 필요합니다(추정) — 없는 머신은 fake 어댑터만 씁니다.

판정(verify·smoke)은 fake 어댑터로만 갑니다 — 실제 모델은 사람의 수동 확인입니다.
`AETHER_MODEL_ID` 의 Ollama 태그가 실재하는지는 사람이 P1-3 PR 리뷰에서 확인합니다.

## 검증

```bash
./harness/scripts/verify.sh
```

결과는 `.harness/verify.json` 에 남습니다.

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
