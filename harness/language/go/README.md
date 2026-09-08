# Go 팩 (최소)

Go 백엔드 프로젝트에 하네스를 붙일 때 읽습니다. 이 팩은 코어 `detect-stack.sh` 가 원래 제공하던 Go 감지·기본 단계를 옮긴 **최소 팩**입니다. 문서 예시(`examples.md`, `improvement-log.example.yaml`)는 아직 없으며, 필요할 때 [../_template/](../_template/) 을 따라 추가합니다. 팩 계약은 [../README.md](../README.md) 가 소유합니다.

| 소유자 | 재검토 조건 |
| --- | --- |
| unassigned | Go 가 조직 스택에서 사라질 때, 또는 최소 팩을 넘어 예시 문서가 필요해질 때 |

## 감지 조건

| 스택 ID | 근거 파일 |
| --- | --- |
| `go` | `go.mod` |

## 지원 kind

| kind | 판정 | 디렉터리 |
| --- | --- | --- |
| `backend` | 항상 | [backend/](backend/) |

## 기본 verify 단계

| id | layer | required | 명령 | 생성 조건 |
| --- | --- | --- | --- | --- |
| `build` | `correctness` | true | `go build ./...` | 항상 |
| `vet` | `quality` | true | `go vet ./...` | 항상 |
| `lint` | `quality` | false | `golangci-lint run ./...` | `.golangci.{yml,yaml,toml,json}` 이 있을 때 |
| `test` | `correctness` | true | `go test ./...` | 항상 |

통합 테스트(`go test -tags=integration ./...`)와 부하 테스트는 [backend/harness.config.example](backend/harness.config.example) 을 씁니다. 계층 규칙은 golangci-lint 의 `depguard` 또는 `go-arch-lint` 로 걸고 `arch-test` 단계로 분리합니다.

## 보호 패턴

| 목록 | 패턴 | 이유 |
| --- | --- | --- |
| 차단 | `.golangci.{yml,yaml,toml,json}`, `staticcheck.conf`, `.go-arch-lint.yml` | lint·아키텍처 규칙 파일입니다. `issues.exclude-rules` 추가는 `quality` 위반 동결입니다 |
| 경고 | `go.mod`, `go.sum`, `go.work`, `Makefile`, `tools.go` | 의존성 변경은 정상이지만 빌드 태그와 테스트 명령이 여기서 바뀝니다 |
| 보안 | `.netrc` | 프라이빗 모듈 자격 증명입니다 |

## 문서 예시

- [backend/harness.config.example](backend/harness.config.example)
