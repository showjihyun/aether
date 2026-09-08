# Ruby 팩 (최소)

Ruby 백엔드 프로젝트에 하네스를 붙일 때 읽습니다. 문서 예시(`examples.md`, `improvement-log.example.yaml`)는 아직 없으며, 필요할 때 [../_template/](../_template/) 을 따라 추가합니다. 팩 계약은 [../README.md](../README.md) 가 소유합니다.

| 소유자 | 재검토 조건 |
| --- | --- |
| unassigned | Ruby 가 조직 스택에서 사라질 때, 또는 최소 팩을 넘어 예시 문서가 필요해질 때 |

## 감지 조건

| 스택 ID | 근거 파일 |
| --- | --- |
| `ruby` | `Gemfile` 또는 `gems.rb` |

Bundler 가 사실상 유일한 의존성 관리 도구이므로 변형(`ruby:<변형>`)을 두지 않습니다. `gems.rb` 는 Bundler 가 지원하는 `Gemfile` 의 대체 이름입니다.

**Rails 저장소는 감지 순서에 주의합니다.** 프런트엔드 자산 때문에 루트에 `package.json` 이 함께 있으면 기본 순서(`typescript … ruby`)에서 `typescript` 가 먼저 잡힙니다. 그때는 `harness.config` 에 `HARNESS_STACK="ruby"` 를 적거나 `HARNESS_LANG_DETECT_ORDER` 를 재정의합니다. 보호 패턴은 감지 결과와 무관하게 합쳐지므로 이 경우에도 `.rubocop.yml` 은 차단됩니다([../README.md](../README.md) 3절).

## 지원 kind

| kind | 판정 | 디렉터리 |
| --- | --- | --- |
| `backend` | 항상 | [backend/](backend/) |

Rails 도 산출물이 서버에서 실행되므로 `backend` 입니다. 뷰가 브라우저에서 렌더링되는 것과 산출물이 브라우저에서 실행되는 것은 다릅니다.

## 기본 verify 단계

Ruby 에는 언제나 성립하는 빌드 단계가 없습니다. 그래서 모든 단계가 조건부입니다.

| id | layer | required | 명령 | 생성 조건 |
| --- | --- | --- | --- | --- |
| `lint` | `quality` | false | `rubocop` | `.rubocop.yml` 또는 `.rubocop.yaml` 이 있을 때 |
| `arch-test` | `architecture` | true | `packwerk check` | `packwerk.yml` 이 있을 때 |
| `test` | `correctness` | true | `rspec` | `.rspec` 또는 `spec/` 이 있을 때 |
| `test` | `correctness` | true | `rake test` | 위가 아니고 `Rakefile` 과 `test/` 가 있을 때 |

`Gemfile.lock`(또는 `gems.locked`)이 있으면 모든 명령 앞에 `bundle exec ` 가 붙습니다. 없으면 전역에 설치된 실행 파일을 가정합니다.

통합 테스트, 스모크, 의존성 취약점 검사는 [backend/harness.config.example](backend/harness.config.example) 을 씁니다.

## 보호 패턴

| 목록 | 패턴 | 이유 |
| --- | --- | --- |
| 차단 | `.rubocop.yml`, `.rubocop.yaml` | lint 규칙 파일입니다. `Exclude`·`Enabled: false` 추가는 `quality` 위반 동결입니다 |
| 차단 | `.rubocop_todo.yml` | 기존 위반을 통째로 제외하는 목록입니다. 여기에 줄을 더하는 것이 가장 쉬운 우회 경로입니다 |
| 차단 | `.rspec`, `.simplecov` | 테스트 기본 옵션(`--tag ~slow` 등)과 커버리지 임계값입니다 |
| 차단 | `packwerk.yml` | 패키지 경계 규칙입니다 |
| 경고 | `Gemfile`, `Gemfile.lock`, `gems.rb`, `gems.locked`, `*.gemspec`, `.ruby-version` | 의존성·런타임 변경은 정상이지만 lint·테스트 러너 버전이 여기서 바뀝니다 |
| 경고 | `Rakefile`, `spec/spec_helper.rb`, `test/test_helper.rb` | 기본 task 와 헬퍼에서 테스트 범위가 바뀝니다 |
| 보안 | `.gem/credentials`, `config/master.key`, `config/credentials/*.key`, `.bundle/config` | RubyGems API 키, Rails 자격 증명 키, 프라이빗 gem 소스 토큰입니다 |

## 문서 예시

- [backend/harness.config.example](backend/harness.config.example)
