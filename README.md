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
