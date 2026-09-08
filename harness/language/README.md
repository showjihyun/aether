# 언어 팩 (language/)

이 디렉터리는 하네스 번들에서 **특정 언어·런타임·빌드 도구에 종속된 부분**을 코어에서 떼어내 모아 둔 자리입니다. 하네스를 새 프로젝트에 붙일 때 그 프로젝트의 언어 팩이 있는지 확인할 때, `verify.sh` 가 감지한 스택이 기대와 다를 때, 지원하지 않는 언어를 추가할 때, 그리고 코어 문서의 언어 중립 예시를 실제 스택의 도구 이름으로 읽고 싶을 때 이 문서를 먼저 읽습니다.

**팩 문서는 하나만 읽습니다.** `harness/scripts/verify.sh --list` 로 스택과 kind 를 먼저 확정하고, 해당 `<언어>/` 와 그 아래 `<kind>/` 만 읽습니다. 다른 팩의 `examples.md` 는 이 프로젝트와 무관하므로 열지 않습니다. 코어 문서가 여러 팩을 나란히 링크하는 자리(승격 사다리의 도구 대응표, 관측 채널표)에서도 마찬가지입니다.

| 소유자 | 재검토 조건 |
| --- | --- |
| unassigned | 팩이 추가·제거될 때, 또는 팩 계약(2절)을 바꿀 때 |

코어(`scripts/`, `hooks/`, `rules/`, `references/`, `skills/`, `subagents/`, `evaluation/`, `improvement-log/`, `templates/`)는 언어에 고정되지 않습니다. 언어에 따라 달라지는 것은 다음 여섯 가지이며, 전부 이 디렉터리가 소유합니다. 정확한 필수 항목 목록은 2절 계약표가 정본입니다.

| 언어 종속 요소 | 코어에서 하던 일 | 지금 소유하는 곳 |
| --- | --- | --- |
| 스택 감지 | `package.json`, `pom.xml` 같은 파일로 스택을 알아냅니다 | `<언어>/lang.sh` 의 `harness_lang_<언어>_detect` |
| FE/BE 판정 | (없었음) | `<언어>/lang.sh` 의 `harness_lang_<언어>_kind` |
| 기본 verify 단계 | `harness.config` 에 `HARNESS_STEPS` 가 없을 때 실행할 단계 | `<언어>/lang.sh` 의 `harness_lang_<언어>_default_steps` |
| 평가 보호 패턴 | lint·타입·아키텍처 설정 파일을 에이전트가 고치지 못하게 막는 목록 | `<언어>/lang.sh` 의 `HARNESS_LANG_<언어>_PROTECTED_PATTERNS` 등 |
| 보안 민감 경로 | 자격 증명 파일 변경 시 사람 검토로 에스컬레이션하는 목록 | `<언어>/lang.sh` 의 `HARNESS_LANG_<언어>_SECURITY_PATTERNS` |
| 문서 예시 | 계층 규칙 위반, AGENTS.md 비대화, 관측 채널 명령 같은 구체 예시 | `<언어>/<kind>/examples.md`, `harness.config.example`, `improvement-log.example.yaml` |

이 중 **보호 패턴과 보안 경로는 감지 결과에 의존하지 않습니다.** `guard-evaluation-tampering.sh` 와 `loop.sh` 는 로드된 모든 팩의 목록을 합집합으로 씁니다. 감지가 실패하거나 monorepo 루트가 한 언어만 가리켜도 다른 언어의 평가 설정이 무방비가 되면 안 되기 때문입니다. 감지 결과(스택·kind)는 `verify.sh` 의 기본 단계 선택에만 씁니다.

## 1. 디렉터리 구조

```text
language/
  README.md                         ← 이 문서. 팩 규약과 로딩 순서
  _template/                        ← 새 언어 팩을 만들 때 복사하는 뼈대 (로더가 무시합니다)
  <언어>/
    README.md                       ← 감지 조건, 지원 kind, 제공 단계, 보호 패턴 요약
    lang.sh                         ← source 되는 bash 팩. 감지·단계·패턴 정의
    frontend/                       ← 브라우저에서 실행되는 애플리케이션용 (있는 언어만)
      harness.config.example        ← 필수
      examples.md                   ← 선택 (최소 팩은 생략)
      improvement-log.example.yaml  ← 선택 (최소 팩은 생략)
    backend/                        ← 서버·CLI·배치 등 브라우저 밖에서 실행되는 애플리케이션용
      harness.config.example        ← 필수
      examples.md                   ← 선택
      improvement-log.example.yaml  ← 선택
```

`examples.md` 와 `improvement-log.example.yaml` 은 **관측된 필요가 생겼을 때만** 만듭니다. 근거 없이 먼저 만들면 검증되지 않은 지침이 되어 읽는 비용만 늘립니다. `go`, `rust`, `ruby` 는 이 둘이 없는 최소 팩이며, 그 사실을 각 팩 README 가 밝힙니다.

디렉터리 이름은 **언어 이름**입니다. 빌드 도구나 런타임 이름(`gradle`, `node`)을 쓰지 않습니다. 같은 언어 안에서 빌드 도구·패키지 매니저가 갈리는 것은 스택 ID 의 변형(`java:gradle`, `typescript:pnpm`)으로 표현합니다.

### 1.1 FE / BE 구분 (kind)

같은 언어라도 프론트엔드와 백엔드는 검증 단계, 관측 채널, 보호해야 할 설정 파일이 다릅니다. 그래서 언어 팩 아래를 `frontend/` 와 `backend/` 로 나눕니다.

| kind | 정의 | 대표 관측 채널 | 이 kind 만의 검증 단계 예 |
| --- | --- | --- | --- |
| `frontend` | 산출물이 브라우저(또는 웹뷰)에서 실행됩니다 | OBS-F1~F5 (browser, DOM, screenshot, console, network) | E2E, 번들 크기, 접근성 검사 |
| `backend` | 산출물이 서버·CLI·배치·워커로 실행됩니다 | OBS-B1~B7 (integration test, curl, DB query, log, metric, trace, load) | 통합 테스트, 계약 테스트, 스키마 검증, 부하 테스트 |

kind 는 `harness_lang_<언어>_kind` 가 정하고 `HARNESS_KIND` 로 재정의할 수 있습니다. 지금 프로젝트 파일을 실제로 읽어 판정하는 것은 `typescript` 뿐이고, 나머지 다섯 팩은 언제나 `backend` 를 냅니다. 두 kind 를 모두 담은 저장소는 `fullstack` 으로 판정되며 두 kind 의 단계를 합집합으로 씁니다. 판정할 근거가 없으면 `unknown` 이고 이때도 합집합을 씁니다.

kind 는 **기본 verify 단계 선택에만** 영향을 줍니다. 보호 패턴은 kind 와 무관하게 전부 적용됩니다. kind 확정으로 제외된 단계가 있으면 `verify.sh` 가 그 목록을 출력합니다.

현재 두 kind 를 모두 가진 언어는 `typescript` 뿐입니다. `java`, `python`, `go`, `rust`, `ruby` 는 `backend/` 만 갖습니다. 나중에 Kotlin/Android 나 Rust/WASM 처럼 다른 kind 가 생기면 그 언어 팩 아래에 디렉터리를 추가합니다. 관측 채널 ID(`OBS-*`)의 정의는 [../references/agent-observability.md](../references/agent-observability.md) 가 소유하고, 팩은 그 채널을 이 언어에서 어떤 명령으로 확보하는지만 적습니다.

## 2. 팩 계약 (lang.sh)

`scripts/lib/detect-stack.sh` 가 `language/*/lang.sh` 를 모두 `source` 합니다. 각 팩은 다음을 정의해야 하며, 이름 규칙을 지키지 않으면 로더가 팩을 찾지 못합니다. `<언어>` 는 디렉터리 이름과 같고, 대문자 변수명에서는 `<언어>` 를 대문자로 씁니다.

| 정의 | 필수 | 계약 |
| --- | --- | --- |
| `HARNESS_LANG_PACKS+=(<언어>)` | 예 | 팩을 등록합니다. 파일 맨 위에서 1회. |
| `harness_lang_<언어>_detect <root>` | 예 | 프로젝트 루트를 받아 스택 ID(`<언어>` 또는 `<언어>:<변형>`)를 표준출력으로 냅니다. 감지되지 않으면 아무것도 출력하지 않고 `return 1` 합니다. |
| `harness_lang_<언어>_kind <root> <stack>` | 예 | `frontend` \| `backend` \| `fullstack` \| `unknown` 중 하나를 출력합니다. |
| `harness_lang_<언어>_default_steps <stack> <root> <kind>` | 예 | `id\|layer\|required\|command` 형식의 줄을 출력합니다. 형식은 `scripts/harness.config.example` 의 `HARNESS_STEPS` 와 같습니다. 실행 가능한 근거가 있는 단계만 냅니다. |
| `HARNESS_LANG_<언어>_PROTECTED_PATTERNS=(...)` | 예 | 변경을 차단할 경로 glob. 비어 있어도 배열은 선언합니다. |
| `HARNESS_LANG_<언어>_WARN_PATTERNS=(...)` | 예 | 변경 시 경고만 낼 경로 glob. |
| `HARNESS_LANG_<언어>_SECURITY_PATTERNS` | 아니오 | `loop.sh` 의 보안 민감 변경 판정에 덧붙일 ERE 조각. |
| `HARNESS_LANG_<언어>_<KIND>_PROTECTED_PATTERNS` / `_WARN_PATTERNS` | 아니오 | kind 별 추가 패턴. `<KIND>` 는 `FRONTEND` 또는 `BACKEND`. `fullstack`·`unknown` 이면 둘 다 합칩니다. |

**계약은 로더가 기계적으로 검사합니다.** `harness_lang_validate_packs` 가 필수 함수 3개(`declare -F`)와 패턴 배열 2개(인덱스 배열인지)를 확인하고, 팩 이름이 `[a-z][a-z0-9-]*` 형식인지 봅니다. 하나라도 어긋나면 그 팩을 등록에서 **제외하고 사유를 stderr 에 남깁니다**. 특히 패턴 변수를 배열이 아닌 문자열로 선언하는 실수는 그 팩의 보호 패턴을 통째로 없애므로 반드시 걸러집니다. 계약 위반을 조용히 넘기면 보호가 사라진 사실이 어디에도 드러나지 않습니다.

```bash
harness/scripts/verify.sh --list                      # 계약 위반이 있으면 앞에 출력됩니다
harness/hooks/guard-evaluation-tampering.sh --list    # 합쳐진 보호 목록과 함께 확인합니다
```

규칙은 다음과 같습니다.

- 팩은 직접 실행하지 않습니다. `set -e` 환경에서 `source` 되므로 정의 외의 부수 효과(파일 생성, 명령 실행)를 두지 않습니다. 팩 하나의 문법 오류는 로더가 격리하므로 다른 팩과 코어로 번지지 않습니다.
- 패턴 변수는 반드시 **인덱스 배열**로 선언합니다. 비어 있어도 `=()` 로 선언합니다.
- 팩은 `scripts/lib/common.sh` 의 `have_cmd`, `log_warn` 만 의존합니다. 다른 팩의 함수를 호출하지 않습니다.
- 감지 함수는 파일 존재만으로 판정합니다. 빌드 도구를 실행해 감지하지 않습니다. 감지가 느리면 hook 이 시간 초과로 실패합니다.
- 기본 단계는 "있으면 실행되는" 것만 냅니다. 프로젝트에 해당 스크립트·설정이 없는데 단계를 내면 verify 가 언제나 실패합니다.
- 보호 패턴은 **평가 결과의 의미를 바꾸는 파일**만 담습니다. 의존성 목록처럼 바뀌는 것이 정상인 파일은 경고 목록에 둡니다. 판정 기준은 [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) 를 따릅니다.

## 3. 로딩과 감지 순서

1. `detect-stack.sh` 가 `language/*/lang.sh` 를 사전순으로 `source` 하고 계약을 검사합니다. `_` 로 시작하는 디렉터리는 건너뜁니다. 로드나 계약 검사에 실패한 팩은 제외되고 사유가 stderr 에 남습니다.
2. `guard-evaluation-tampering.sh` 는 **감지하지 않고** 코어 보호 패턴에 로드된 모든 팩의 패턴(공통 + 모든 kind)을 합칩니다. `loop.sh` 도 모든 팩의 보안 패턴을 합칩니다.
3. `verify.sh` 는 단계 선택을 위해 감지합니다. `HARNESS_STACK` 이 있으면 감지를 생략하고 그 값을 씁니다. 옛 형식(`node:pnpm`, `gradle`, `maven`)은 새 형식으로 바꿔 쓰고 경고를 남깁니다.
4. 없으면 `HARNESS_LANG_DETECT_ORDER`(기본 `typescript java python go rust ruby`) 순서로 감지 함수를 호출하고, **처음 감지된 스택**을 씁니다. 나머지 감지 결과는 `verify.sh` 가 "다른 후보" 로 표시합니다.
5. `HARNESS_KIND` 가 있으면 그 값을, 없으면 팩의 kind 함수 결과를 씁니다. kind 는 단계 선택에만 쓰이며 보호 목록을 바꾸지 않습니다.

한 저장소에 두 언어가 있으면(예: `pom.xml` 과 `frontend/package.json`) **단계 선택**은 루트에서 감지되는 언어 하나만 따릅니다. 하위 디렉터리마다 `harness.config` 를 두고 `HARNESS_PROJECT_ROOT` 로 루트를 나누거나, 루트 `harness.config` 의 `HARNESS_STEPS` 에 두 언어의 단계를 직접 적습니다. **보호 목록은 이 제약을 받지 않습니다.** monorepo 에서도 `frontend/tsconfig.json` 과 `backend/checkstyle.xml` 이 함께 차단됩니다.

## 4. 지원 팩

| 언어 | 스택 ID | kind | 감지 근거 |
| --- | --- | --- | --- |
| [typescript](typescript/README.md) | `typescript`, `typescript:pnpm`, `typescript:yarn`, `typescript:npm`, `typescript:bun` | `frontend`, `backend` | `package.json` 과 lockfile |
| [java](java/README.md) | `java:gradle`, `java:maven` | `backend` | `build.gradle(.kts)`, `settings.gradle(.kts)`, `pom.xml` |
| [python](python/README.md) | `python`, `python:uv`, `python:poetry`, `python:pdm`, `python:pipenv` | `backend` | `pyproject.toml`, `requirements.txt`, `setup.py`, `setup.cfg`, `Pipfile` |
| [go](go/README.md) | `go` | `backend` | `go.mod` |
| [rust](rust/README.md) | `rust` | `backend` | `Cargo.toml` |
| [ruby](ruby/README.md) | `ruby` | `backend` | `Gemfile`, `gems.rb` |

`typescript` 팩은 JavaScript 전용 프로젝트도 담당합니다. 타입 검사 단계는 `package.json` 에 해당 스크립트가 있을 때만 생성되므로 JavaScript 프로젝트에서는 자연히 빠집니다.

## 5. 새 언어 팩 추가

1. `_template/` 을 `language/<언어>/` 로 복사하고 `README.md` 와 `lang.sh` 의 `<언어>` 자리를 채웁니다.
2. 감지 함수, kind 함수, 기본 단계 함수, 패턴 배열을 정의합니다. 계약은 2절입니다.
3. 해당 언어 프로젝트에서 `harness/scripts/verify.sh --list` 를 실행해 감지 결과와 단계 목록을 확인합니다.
4. `harness/hooks/guard-evaluation-tampering.sh --list` 로 보호 패턴이 합쳐졌는지 확인합니다.
5. 4절 표와 `HARNESS_LANG_DETECT_ORDER` 에 팩을 추가하고, 팩 README 에 소유자와 재검토 조건을 적습니다.
6. `<kind>/examples.md` 와 `improvement-log.example.yaml` 은 **여기서 만들지 않습니다.** 실제로 그 언어에서 배치 판단이 어긋난 사건이 관측된 뒤에 만듭니다. 만들 때도 코어와 겹치는 내용을 복제하지 않고 도구가 갈리는 부분만 적습니다. 새 규칙 ID 를 발급하지 않습니다.

**팩 문서는 코어의 델타만 담습니다.** 승격 사다리의 언어 무관 단계, 배치 판정 절차, `preferred_enforcement` 값, 언어와 무관한 관측 채널(`OBS-C*`)은 코어가 정본이므로 팩에 다시 적지 않습니다. 같은 내용을 두 자리에 두면 한쪽만 갱신되어 서로 다른 것을 지시하게 됩니다.

팩 추가도 하네스 변경입니다. 한 번에 팩 하나만 추가하고 [../rules/harness-change-control.rule.md](../rules/harness-change-control.rule.md) 의 회귀 검증을 거칩니다.

## 6. 팩이 하지 않는 것

- 규칙 ID(`LP-*`, `EI-*` 등)나 요소 ID(`HE-*`)를 발급하지 않습니다. 팩은 코어 규칙을 언어로 구체화할 뿐입니다.
- 평가 계층 6종, 가중치, 임계값을 바꾸지 않습니다. 팩의 `harness.config.example` 은 `HARNESS_STEPS` 만 제안합니다.
- 코어 문서를 언어별로 복제하지 않습니다. 코어 문장은 한 곳에만 있고 팩은 링크와 예시만 둡니다([../rules/lesson-placement.rule.md](../rules/lesson-placement.rule.md) LP-7).

## 관련 문서

- [../scripts/lib/detect-stack.sh](../scripts/lib/detect-stack.sh) — 팩 로더와 감지 진입점
- [../scripts/harness.config.example](../scripts/harness.config.example) — 언어 중립 설정 예시. 팩 예시는 여기서 링크합니다
- [../hooks/guard-evaluation-tampering.sh](../hooks/guard-evaluation-tampering.sh) — 팩 보호 패턴을 합치는 hook
- [../references/agent-observability.md](../references/agent-observability.md) — FE/BE 관측 채널 정의
- [../references/harness-adoption.md](../references/harness-adoption.md) — Day 1 에 팩을 확인하는 순서
