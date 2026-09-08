# <언어> 팩 (템플릿)

이 디렉터리는 새 언어 팩을 만들 때 복사하는 뼈대입니다. `language/_template/` 자체는 로더가 건너뛰므로 여기 있는 파일은 실행되지 않습니다. 복사한 뒤 `<언어>` 와 `<LANG>` 자리를 모두 채우고, 이 문단을 지웁니다. 팩 계약은 [../README.md](../README.md) 2절이 정본입니다.

| 소유자 | 재검토 조건 |
| --- | --- |
| unassigned | 이 템플릿으로 팩이 실제로 생성될 때, 또는 팩 계약이 바뀔 때 |

## 감지 조건

| 스택 ID | 근거 파일 |
| --- | --- |
| `<언어>` | `<빌드 파일>` |
| `<언어>:<변형>` | `<빌드 파일>` + `<lockfile 또는 도구 설정>` |

## 지원 kind

| kind | 판정 근거 | 디렉터리 |
| --- | --- | --- |
| `backend` | (예: 항상 backend) | `backend/` |

## 기본 verify 단계

| id | layer | required | 명령 | 생성 조건 |
| --- | --- | --- | --- | --- |
| `build` | `correctness` | true | `<빌드 명령>` | 항상 |
| `lint` | `quality` | false | `<lint 명령>` | 설정 파일이 있을 때 |
| `test` | `correctness` | true | `<테스트 명령>` | 항상 |

## 보호 패턴

| 목록 | 패턴 | 이유 |
| --- | --- | --- |
| 차단 | `<lint 설정 파일>` | 규칙을 끄면 `quality` 점수가 측정되지 않은 채 오릅니다 |
| 경고 | `<의존성 매니페스트>` | 바뀌는 것이 정상이지만 테스트 의존성 제거는 평가에 영향을 줍니다 |

## 문서 예시

- [backend/harness.config.example](backend/harness.config.example) — 필수
- [backend/examples.md](backend/examples.md) — 선택
- [backend/improvement-log.example.yaml](backend/improvement-log.example.yaml) — 선택

이 뼈대는 세 파일을 모두 담습니다. **최소 팩으로 만들려면 `examples.md` 와 `improvement-log.example.yaml` 을 지우고** 팩 README 에 그 사실을 적습니다. `go` 와 `rust` 가 그 형태입니다. 지우지 않고 두면 자리표시자가 남은 문서를 배포하게 됩니다.
