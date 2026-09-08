# Java 팩

Java(Gradle/Maven) 백엔드 프로젝트에 하네스를 붙일 때 읽습니다. Kotlin/JVM 프로젝트도 Gradle 로 빌드하면 이 팩이 감지합니다. 팩 계약과 로딩 순서는 [../README.md](../README.md) 가 소유합니다.

| 소유자 | 재검토 조건 |
| --- | --- |
| unassigned | Java 가 조직 스택에서 사라질 때, 또는 빌드 도구·정적 분석 도구가 바뀔 때 |

## 감지 조건

| 스택 ID | 근거 파일 | 명령 접두사 |
| --- | --- | --- |
| `java:gradle` | `build.gradle`, `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts` 중 하나 | `./gradlew --console=plain` (래퍼가 없으면 `gradle`) |
| `java:maven` | `pom.xml` | `./mvnw -B` (래퍼가 없으면 `mvn -B`) |

Gradle 파일이 먼저 검사되므로 둘 다 있으면 `java:gradle` 입니다. 강제하려면 `HARNESS_STACK=java:maven` 을 씁니다. 옛 스택 ID `gradle`, `maven` 은 로더가 자동으로 새 ID 로 바꾸고 경고를 남깁니다.

## 지원 kind

| kind | 판정 | 디렉터리 |
| --- | --- | --- |
| `backend` | 항상 | [backend/](backend/) |

Android 는 아직 별도 kind 로 다루지 않습니다. 필요해지면 `AndroidManifest.xml` 감지와 `mobile/` 디렉터리를 이 팩에 추가합니다.

## 기본 verify 단계

`harness.config` 에 `HARNESS_STEPS` 가 없을 때 생성되는 단계입니다.

| 스택 | id | layer | required | 명령 | 생성 조건 |
| --- | --- | --- | --- | --- | --- |
| gradle | `compile` | `correctness` | true | `./gradlew --console=plain classes testClasses` | 항상 |
| gradle | `test` | `correctness` | true | `./gradlew --console=plain test` | 항상 |
| gradle | `check` | `quality` | false | `./gradlew --console=plain check -x test` | 항상 (checkstyle·spotbugs·pmd·jacoco 가 `check` 에 묶여 있을 때 의미가 있습니다) |
| gradle | `integration` | `correctness` | true | `./gradlew --console=plain integrationTest` | `src/integrationTest/` 또는 `src/intTest/` 가 있을 때 |
| maven | `compile` | `correctness` | true | `./mvnw -B -q compile` | 항상 |
| maven | `test` | `correctness` | true | `./mvnw -B test` | 항상 |
| maven | `verify` | `architecture` | false | `./mvnw -B verify` | 항상 (failsafe·checkstyle·spotbugs 가 `verify` 에 묶여 있을 때). 스킵 플래그를 붙이지 않으므로 위 `test` 의 단위 테스트가 한 번 더 돕니다 |

Maven 의 `verify` 단계에 스킵 플래그를 붙이지 않는 이유를 적어 둡니다. `-DskipTests` 는 surefire 와 failsafe 를 **둘 다** 꺼서 통합 테스트가 하나도 돌지 않은 채 `architecture` 계층이 통과로 채점됩니다. `-Dsurefire.skip` 은 surefire 의 사용자 속성이 아니라 무시됩니다. surefire 만 끄고 failsafe 는 살리는 명령행 속성이 없으므로, 단위 테스트가 두 번 도는 시간 비용을 감수하고 결과의 정직함을 택했습니다. 한 번만 돌리려면 POM 에서 surefire 실행에 skip 속성을 바인딩하십시오. 그것은 프로젝트의 몫입니다.

명령의 `./gradlew`·`./mvnw` 접두사는 래퍼가 있을 때이고, 없으면 `gradle`·`mvn` 으로 바뀝니다. 실제 생성 결과는 `harness/scripts/verify.sh --list` 로 확인하십시오.

ArchUnit 은 보통 `test` 단계 안에서 실행되므로 별도 단계가 없습니다. 아키텍처 규칙을 `architecture` 계층으로 따로 채점하려면 [backend/harness.config.example](backend/harness.config.example) 처럼 `--tests '*ArchitectureTest'` 로 분리합니다.

## 보호 패턴

| 목록 | 패턴 | 이유 |
| --- | --- | --- |
| 차단 | `checkstyle.xml`, `checkstyle-suppressions.xml`, `config/checkstyle/*` | 규칙을 끄거나 억제 목록을 늘리면 `quality` 가 측정되지 않은 채 오릅니다 |
| 차단 | `archunit.properties` | ArchUnit 의 실패 허용(`freeze`) 설정이 여기 있습니다. 위반을 동결하면 `architecture` 가 통과로 바뀝니다 |
| 차단 | `spotbugs-exclude.xml`, `spotbugs.xml`, `config/spotbugs/*`, `pmd-ruleset.xml`, `config/pmd/*`, `detekt.yml`, `config/detekt/*` | 정적 분석 제외 목록입니다 |
| 차단 | `lombok.config`, `junit-platform.properties` | 테스트 실행 방식과 생성 코드 규칙을 바꿉니다 |
| 경고 | `build.gradle(.kts)`, `settings.gradle(.kts)`, `gradle.properties`, `buildSrc/*`, `gradle/libs.versions.toml`, `pom.xml`, `.mvn/*`, `jacoco*.xml` | 의존성 변경은 정상이지만 테스트·검증 플러그인 제거가 같은 파일에서 일어납니다 |
| 보안 | `*.jks`, `*.p12`, `*.keystore`, `application-prod*.yml` 등 | `loop.sh` 가 변경을 감지하면 사람 검토로 에스컬레이션합니다 |

## 문서 예시

코어 문서의 언어 중립 예시(Controller → Repository 직접 의존, AGENTS.md 비대화, 관측 채널)를 Spring/ArchUnit/Checkstyle 이름으로 옮긴 판입니다.

- [backend/examples.md](backend/examples.md)
- [backend/harness.config.example](backend/harness.config.example)
- [backend/improvement-log.example.yaml](backend/improvement-log.example.yaml)
