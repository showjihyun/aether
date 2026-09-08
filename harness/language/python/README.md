# Python 팩

Python 백엔드(웹 서버, 배치, CLI, 데이터 파이프라인) 프로젝트에 하네스를 붙일 때 읽습니다. 팩 계약과 로딩 순서는 [../README.md](../README.md) 가 소유합니다.

| 소유자 | 재검토 조건 |
| --- | --- |
| unassigned | Python 이 조직 스택에서 사라질 때, 또는 패키지 매니저·lint 도구가 바뀔 때 |

## 감지 조건

| 스택 ID | 근거 파일 | 명령 접두사 |
| --- | --- | --- |
| `python:uv` | 매니페스트 + `uv.lock` | `uv run ` (uv 가 설치되어 있을 때) |
| `python:poetry` | 매니페스트 + `poetry.lock` | `poetry run ` (poetry 가 설치되어 있을 때) |
| `python:pdm` | 매니페스트 + `pdm.lock` | `pdm run ` |
| `python:pipenv` | `Pipfile` 또는 `Pipfile.lock` | `pipenv run ` |
| `python` | 매니페스트만 | 없음 (활성화된 venv 를 가정) |

매니페스트는 `pyproject.toml`, `requirements.txt`, `setup.py`, `setup.cfg`, `Pipfile` 중 하나입니다. 도구가 설치되어 있지 않으면 접두사 없이 명령을 실행하므로, 그 경우 venv 를 먼저 활성화합니다.

## 지원 kind

| kind | 판정 | 디렉터리 |
| --- | --- | --- |
| `backend` | 항상 | [backend/](backend/) |

## 기본 verify 단계

**설정 파일이 있는 도구만** 단계가 됩니다. 설치되지 않은 도구를 무조건 부르면 verify 가 항상 실패하기 때문입니다.

| id | layer | required | 명령 | 생성 조건 |
| --- | --- | --- | --- | --- |
| `lint` | `quality` | false | `ruff check .` | `ruff.toml`, `.ruff.toml` 또는 `pyproject.toml` 의 `[tool.ruff]` |
| `format-check` | `quality` | false | `ruff format --check .` | 위와 같음 |
| `lint` | `quality` | false | `flake8` | ruff 설정이 없고 `.flake8` 이 있을 때 |
| `typecheck` | `quality` | false | `mypy .` | `mypy.ini`, `.mypy.ini` 또는 `[tool.mypy]` |
| `typecheck` | `quality` | false | `pyright` | mypy 설정이 없고 `pyrightconfig.json` 또는 `[tool.pyright]` 가 있을 때 |
| `arch-test` | `architecture` | true | `lint-imports` | `.importlinter` 또는 `[tool.importlinter]` |
| `test` | `correctness` | true | `pytest -q` | `tests/` 또는 `test/` 가 있거나, `pytest.ini`·`tox.ini`·`setup.cfg`·`[tool.pytest.ini_options]` 가 있을 때 |

통합 테스트를 `pytest -m integration` 으로 분리하거나 부하 테스트를 붙이려면 [backend/harness.config.example](backend/harness.config.example) 을 씁니다.

## 보호 패턴

| 목록 | 패턴 | 이유 |
| --- | --- | --- |
| 차단 | `ruff.toml`, `.ruff.toml`, `.flake8`, `.pylintrc`, `pylintrc` | 규칙을 `ignore` 에 넣거나 `exclude` 를 늘리면 `quality` 가 측정되지 않은 채 오릅니다 |
| 차단 | `mypy.ini`, `.mypy.ini`, `pyrightconfig.json` | `ignore_errors`, `strict = false` 로 타입 검사가 약해집니다 |
| 차단 | `pytest.ini`, `.coveragerc` | `testpaths`, `addopts = -k`, `omit` 으로 테스트 범위가 좁아집니다 |
| 차단 | `.importlinter` | 계층 의존 규칙 자체입니다. `ignore_imports` 추가는 `architecture` 위반 동결입니다 |
| 차단 | `.bandit` | 보안 정적 분석 제외 목록입니다 |
| 경고 | `pyproject.toml`, `setup.cfg`, `setup.py`, `tox.ini` | 의존성과 `[tool.ruff]`·`[tool.mypy]`·`[tool.pytest.ini_options]` 가 한 파일에 섞여 있습니다. 차단하면 의존성 추가까지 막히므로 경고로 두고, 도구 섹션 완화는 리뷰와 REP-3 과제가 잡습니다 |
| 경고 | `conftest.py`, `requirements*.txt`, `requirements/*`, `Pipfile`, `uv.lock`, `poetry.lock`, `pdm.lock` | fixture 로 실제 호출을 통째로 가짜로 바꾸거나 테스트 의존성을 지우는 자리입니다. `Pipfile.lock` 은 목록에 없습니다 |
| 보안 | `.pypirc`, `.netrc`, `pip.conf` | 패키지 인덱스 자격 증명입니다. `loop.sh` 가 사람 검토로 에스컬레이션합니다 |

## 문서 예시

코어 문서의 언어 중립 예시(계층 규칙 위반, AGENTS.md 비대화, 관측 채널)를 FastAPI/SQLAlchemy/import-linter/ruff 이름으로 옮긴 판입니다.

- [backend/examples.md](backend/examples.md)
- [backend/harness.config.example](backend/harness.config.example)
- [backend/improvement-log.example.yaml](backend/improvement-log.example.yaml)
