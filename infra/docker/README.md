Docker Compose 로 전부 기동합니다(spec 0001 2.7, plan P0-5). 기동 명령은 루트 [../../README.md](../../README.md) 가 소유합니다 — 여기는 파일 목록만입니다.

| 파일 | 내용 |
| --- | --- |
| `compose.yaml` | postgres, redis, migrate(일회성), api, worker, web |
| `compose.offline.yaml` | `compose.yaml` 오버라이드. `internal: true` 네트워크 + 판정용 `probe` 서비스(R-4) |
| `api.Dockerfile` / `worker.Dockerfile` / `web.Dockerfile` | 빌드 컨텍스트는 저장소 루트(`../..`) — uv·pnpm workspace 전체가 필요합니다 |
| `.env.example` | compose 가 읽는 전체 키. 비밀값 자리는 `<generate>` |
| `.env` | 실제 비밀값. **커밋 대상이 아닙니다**(`.gitignore`). `cp .env.example .env` 로 만듭니다 |
| `postgres/init/01-roles.sh` | `aether_control` / `aether_data` 역할만 생성(P0-8). 스키마·테이블·GRANT 는 `apps/api/migrations`(마이그레이션) 소유 |
