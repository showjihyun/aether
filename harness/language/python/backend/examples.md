# Python 백엔드 예시

이 문서는 코어 문서의 언어 중립 예시를 Python 백엔드(FastAPI, SQLAlchemy, uv, ruff, mypy, pytest, import-linter) 스택의 실제 도구 이름으로 옮긴 판입니다. 코어 문서가 "아키텍처 규칙 도구", "통합 테스트" 처럼 추상적으로 적은 자리를 이 스택에서는 무엇으로 구현하는지 알고 싶을 때 읽습니다. 규칙 ID 를 발급하지 않으며, 코어 문장을 복제하지 않고 링크로 가리킵니다. 각 절은 코어의 어느 문서·어느 예시를 구체화한 것인지 첫 줄에 밝힙니다.

## 1. 계층 규칙 위반과 승격 경로

> 코어: [../../../references/harness-elements.md](../../../references/harness-elements.md) 2.1 "승격 경로 예시", [../../../rules/lesson-placement.rule.md](../../../rules/lesson-placement.rule.md) 예시 1

프로젝트의 계층 규칙은 `api(router) → services → domain → infra(repositories)` 입니다. 에이전트가 `app/api/members.py` 의 라우터에서 `app/infra/repositories.py` 의 `MemberRepository` 를 직접 import 하는 코드를 만들었고, import-linter 가 이를 잡았습니다.

사다리의 0~2단계와 5단계는 언어와 무관하므로 코어가 소유합니다. 이 팩이 채우는 것은 도구가 실제로 갈리는 3·4단계뿐입니다.

| 단계 | 등급 | 이 스택에서의 형태 |
| --- | --- | --- |
| 3 | EL-6 | import-linter 계약을 `.importlinter` 에 추가 |
| 4 | EL-6+ | 계약 이름과 주석에 허용 경로(service 경유)를 적어 넣음 |

3단계와 4단계의 계약은 다음과 같습니다. import-linter 는 실패 메시지에 계약 이름을 출력하므로, 이름에 허용 경로를 담으면 4단계가 됩니다.

```ini
# .importlinter
[importlinter]
root_package = app

[importlinter:contract:layers]
name = Layered architecture: api -> services -> domain -> infra (허용 경로는 docs/architecture/layers.md)
type = layers
layers =
    app.api
    app.services
    app.domain
    app.infra

[importlinter:contract:domain-no-framework]
name = domain 은 FastAPI·SQLAlchemy 에 의존하지 않습니다
type = forbidden
source_modules =
    app.domain
forbidden_modules =
    fastapi
    sqlalchemy
```

승격 후 하위 등급 중복을 제거하는 규범은 코어가 소유합니다. 이 스택에서 진입점 문서에 남기는 것은 "계층 규칙은 `.importlinter` 가 정본이며 `harness/scripts/verify.sh --only arch-test` 로 확인한다" 는 한 줄과 링크뿐입니다.

이 사건의 improvement candidate 는 [improvement-log.example.yaml](improvement-log.example.yaml) 입니다.

## 2. AGENTS.md 비대화 사례

> 코어: [../../../rules/context-hygiene.rule.md](../../../rules/context-hygiene.rule.md) 예시 1, [../../../rules/lesson-placement.rule.md](../../../rules/lesson-placement.rule.md) 예시 2

```markdown
# AGENTS.md

## Rules

- api 모듈에서 infra 를 직접 import 하지 않는다.
- SQLAlchemy 모델을 응답으로 그대로 반환하지 않는다. Pydantic 스키마를 거친다.
- 모든 엔드포인트에 통합 테스트를 작성한다.
- datetime.now() 대신 datetime.now(tz=UTC) 를 쓴다.
- pytz 를 쓰지 말 것. (2026-03 타임존 버그 때문)
- MemberService.update_profile 은 반드시 session.begin() 안에서 호출한다.
- 단, 배치 워커에서는 트랜잭션 없이 호출해도 된다.
- 통합 테스트가 느리면 testcontainers 대신 sqlite 로 돌린다.
- 급할 때는 통합 테스트 생략 가능.
- ... (이하 200줄)
```

각 줄을 어느 자리로 옮길지의 판정 절차, 정본 자리, `preferred_enforcement` 값은 코어의 두 규칙 문서가 소유합니다. 여기서는 **그 자리를 이 스택에서 무엇으로 구현하는가**만 적습니다.

| before 항목 | 이 스택의 도구 |
| --- | --- |
| api → infra 직접 import 금지 | import-linter `layers` 계약 |
| SQLAlchemy 모델 응답 반환 금지 | `response_model=` 규약 + import-linter (`app.api` 에서 `app.infra.models` 금지) |
| 모든 엔드포인트에 통합 테스트 | `integration` 단계(`pytest -m integration`) + Stop hook |
| `datetime.now()` 금지 | ruff `DTZ` 규칙군 (`flake8-datetimez`) |
| `pytz` 금지 (타임존 버그) | ruff `TID251` (`banned-api`) + 타임존 회귀 테스트 1건 |
| 특정 서비스 함수의 트랜잭션 경계 | `docs/architecture/transactions.md` |

ruff 규칙의 예입니다.

```toml
# pyproject.toml
[tool.ruff.lint]
select = ["E", "F", "I", "DTZ", "TID"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"pytz".msg = "zoneinfo 를 씁니다 (docs/architecture/time.md)"
```

## 3. verify 단계와 관측 채널

> 코어: [../../../references/agent-observability.md](../../../references/agent-observability.md) 2.2 "Backend 채널", 2.3 "공통 채널"

| 채널 | 이 스택에서 확보하는 명령 | 공급하는 계층 |
| --- | --- | --- |
| OBS-B1 Integration Test | `uv run pytest -q -m integration` (`testcontainers[postgres]` 로 실제 DB 기동) | `correctness`, `behavior` |
| OBS-B2 curl | `curl -sS -o /dev/null -w '%{http_code}' http://localhost:8000/health` | `behavior` |
| OBS-B3 Database Query | 마이그레이션 반영 확인은 `uv run alembic check` (조회 자체는 `psql` 등 스택 무관 도구) | `behavior`, `architecture` |
| OBS-B4 Application Log | structlog JSON 로그를 `.harness/logs/app.log` 에 남기고 `grep -cE '"level":"(error|critical)"' .harness/logs/app.log` | `behavior` |
| OBS-B5 Metric | `prometheus-fastapi-instrumentator` 의 `/metrics` 를 curl 로 조회 | `performance` |
| OBS-B6 Trace | `opentelemetry-instrumentation-fastapi` + OTLP 수집기 조회 결과를 `.harness/logs/trace.log` 로 저장 | `performance` |
| OBS-B7 Load Test | `uv run locust --headless -u 20 -r 5 -t 30s --host http://localhost:8000` 또는 `k6 run load/smoke.js` | `performance` |

`OBS-C1`(exit code)과 `OBS-C3`(diff)은 언어와 무관하므로 여기 적지 않습니다. 코어가 소유합니다.

## 4. 보호 패턴의 근거

> 코어: [../../../rules/evaluation-integrity.rule.md](../../../rules/evaluation-integrity.rule.md) EI-1, EI-6, [../../../hooks/README.md](../../../hooks/README.md)

| 패턴 | 목록 | 이 파일을 고치면 무엇이 약해지는가 |
| --- | --- | --- |
| `ruff.toml`, `.ruff.toml`, `.flake8` | 차단 | `ignore`, `per-file-ignores`, `exclude` 로 `quality` 가 측정되지 않은 채 오릅니다 |
| `mypy.ini`, `pyrightconfig.json` | 차단 | `ignore_errors = True`, `follow_imports = skip` 으로 타입 검사가 약해집니다 |
| `pytest.ini`, `.coveragerc` | 차단 | `testpaths`, `addopts = -k 'not slow'`, `omit` 으로 테스트 범위가 좁아집니다 |
| `.importlinter` | 차단 | 1절의 계층 계약 자체입니다. `ignore_imports` 추가는 위반 동결입니다 |
| `pyproject.toml` | 경고 | `[tool.ruff]`·`[tool.mypy]`·`[tool.pytest.ini_options]` 가 의존성과 같은 파일에 있습니다. 차단하면 의존성 추가까지 막히므로 경고로 두고, 도구 섹션 완화는 리뷰와 REP-3 이 잡습니다 |
| `conftest.py` | 경고 | autouse fixture 로 DB·HTTP 호출을 통째로 가짜로 바꿀 수 있습니다 |

`@pytest.mark.skip`, `pytest.xfail`, `# noqa`, `# type: ignore` 를 소스에 추가하는 것은 파일 패턴으로 잡히지 않습니다. 이것은 EI-6 의 "테스트 skip·억제 주석" 이며 리뷰와 REP-3 과제가 잡습니다. ruff `PGH004` (`blanket-noqa`) 와 `PGH003` (`blanket-type-ignore`) 로 범위 없는 억제는 lint 단계에서 잡을 수 있습니다.

## 5. improvement candidate 예시

- [improvement-log.example.yaml](improvement-log.example.yaml) — 1절 사건을 기록한 candidate. 코어 예시 [../../../improvement-log/2026-08-09-001.example.yaml](../../../improvement-log/2026-08-09-001.example.yaml) 과 같은 사건이며 모듈·도구 이름만 구체적입니다.

## 관련 문서

- [../README.md](../README.md) — Python 팩 개요
- [../../README.md](../../README.md) — 팩 규약
- [../../../references/agent-observability.md](../../../references/agent-observability.md) — OBS-* 채널 정의
- [../../../rules/evaluation-integrity.rule.md](../../../rules/evaluation-integrity.rule.md) — 보호 패턴의 규범
