# Java 백엔드 예시

이 문서는 코어 문서의 언어 중립 예시를 Java(Spring, Gradle/Maven, ArchUnit, Checkstyle) 백엔드 스택의 실제 도구 이름으로 옮긴 판입니다. 코어 문서가 "아키텍처 규칙 도구", "시간 타입 규칙" 처럼 추상적으로 적은 자리를 이 스택에서는 무엇으로 구현하는지 알고 싶을 때 읽습니다. 규칙 ID 를 발급하지 않으며, 코어 문장을 복제하지 않고 링크로 가리킵니다. 각 절은 코어의 어느 문서·어느 예시를 구체화한 것인지 첫 줄에 밝힙니다.

## 1. 계층 규칙 위반과 승격 경로

> 코어: [../../../references/harness-elements.md](../../../references/harness-elements.md) 2.1 "승격 경로 예시", [../../../rules/lesson-placement.rule.md](../../../rules/lesson-placement.rule.md) 예시 1

프로젝트의 계층 규칙은 `controller → usecase(application service) → domain → repository` 입니다. 에이전트가 `MemberController` 에서 `MemberJpaRepository` 를 직접 주입받는 코드를 만들었고, 아키텍처 테스트가 이를 잡았습니다.

사다리의 0~2단계와 5단계는 언어와 무관하므로 코어가 소유합니다. 이 팩이 채우는 것은 도구가 실제로 갈리는 3·4단계뿐입니다.

| 단계 | 등급 | 이 스택에서의 형태 |
| --- | --- | --- |
| 3 | EL-6 | ArchUnit 규칙을 `src/test/java/.../ArchitectureTest.java` 에 추가 |
| 4 | EL-6+ | 규칙의 `.because(...)` 에 허용 경로(`MemberUseCase` 경유)를 적어 넣음 |

3단계와 4단계의 ArchUnit 규칙은 다음과 같습니다.

```java
@AnalyzeClasses(packages = "com.example", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {

    @ArchTest
    static final ArchRule controllersMustNotDependOnRepositories =
        noClasses()
            .that().resideInAPackage("..controller..")
            .should().dependOnClassesThat()
            .resideInAPackage("..repository..")
            .because("controller 는 use-case 를 경유합니다. 허용 경로: controller → usecase → repository "
                   + "(docs/architecture/layers.md)");
}
```

승격 후 하위 등급 중복을 제거하는 규범은 코어가 소유합니다. 이 스택에서 진입점 문서에 남기는 것은 "계층 규칙은 `ArchitectureTest` 가 정본이며 `harness/scripts/verify.sh --only arch-test` 로 확인한다" 는 한 줄과 링크뿐입니다.

`arch-test` 단계로 분리하는 `HARNESS_STEPS` 는 [harness.config.example](harness.config.example) 에 있습니다. 이 사건의 improvement candidate 는 [improvement-log.example.yaml](improvement-log.example.yaml) 입니다.

## 2. AGENTS.md 비대화 사례

> 코어: [../../../rules/context-hygiene.rule.md](../../../rules/context-hygiene.rule.md) 예시 1, [../../../rules/lesson-placement.rule.md](../../../rules/lesson-placement.rule.md) 예시 2

실패가 생길 때마다 한 줄씩 추가한 결과 진입점 문서가 규칙 목록이 된 Spring 프로젝트의 사례입니다.

```markdown
# AGENTS.md

## Rules

- Controller에서 Repository를 직접 사용하지 않는다.
- Entity를 Controller에 반환하지 않는다.
- 모든 API에는 Integration Test를 작성한다.
- OffsetDateTime 대신 Instant를 사용한다.
- LocalDateTime도 쓰지 말 것. (2026-03 결제 모듈 버그 때문)
- UserService.updateProfile 은 반드시 @Transactional 안에서 호출한다.
- 단, 배치 작업에서는 트랜잭션 없이 호출해도 된다.
- 테스트가 느리면 @SpringBootTest 대신 @WebMvcTest / @DataJpaTest 슬라이스 테스트를 쓴다.
- 급할 때는 슬라이스 테스트도 생략 가능.
- ... (이하 200줄)
```

각 줄을 어느 자리로 옮길지의 판정 절차, 정본 자리, `preferred_enforcement` 값은 코어의 두 규칙 문서가 소유합니다. 여기서는 **그 자리를 이 스택에서 무엇으로 구현하는가**만 적습니다.

| before 항목 | 이 스택의 도구 |
| --- | --- |
| Controller → Repository 직접 호출 금지 | ArchUnit `noClasses()...dependOnClassesThat()` |
| Entity 를 Controller 에서 반환 금지 | ArchUnit `methods().that().areDeclaredInClassesThat().resideInAPackage("..controller..").should().notHaveRawReturnType(...)` |
| 모든 API 에 Integration Test | `integration` 단계(`integrationTest` source set) + Stop hook |
| 시각 타입 규칙 | Checkstyle `IllegalImport` (`illegalClasses="java.time.OffsetDateTime"`) 또는 같은 취지의 ArchUnit 규칙 |
| 결제 모듈 시각 변환 버그 | 그 모듈의 회귀 테스트 1건 |
| 특정 서비스 메서드의 트랜잭션 경계 | `docs/architecture/transactions.md` |
| 느린 테스트 대응(슬라이스 테스트) | 테스트 작성 skill 의 "느린 테스트" 절 |

Checkstyle 규칙의 예입니다.

```xml
<module name="TreeWalker">
  <module name="IllegalImport">
    <property name="illegalClasses" value="java.time.OffsetDateTime, java.time.LocalDateTime"/>
    <message key="import.illegal" value="시각은 java.time.Instant 로 다룹니다 (docs/architecture/time.md)"/>
  </module>
</module>
```

교정 후 AGENTS.md 에는 "계층 규칙과 시간 타입 규칙은 `ArchitectureTest` 와 `config/checkstyle/checkstyle.xml` 이 정본이며 `./harness/scripts/verify.sh` 가 잡는다" 만 남습니다.

## 3. verify 단계와 관측 채널

> 코어: [../../../references/agent-observability.md](../../../references/agent-observability.md) 2.2 "Backend 채널", 2.3 "공통 채널"

코어 문서는 채널의 정의와 우선순위만 정합니다. 이 스택에서 각 채널을 어떤 명령으로 확보하는지는 다음과 같습니다. 실제 `HARNESS_STEPS` 는 [harness.config.example](harness.config.example) 을 따릅니다.

| 채널 | 이 스택에서 확보하는 명령 | 공급하는 계층 |
| --- | --- | --- |
| OBS-B1 Integration Test | `./gradlew integrationTest` (Testcontainers 로 실제 DB·큐 기동) / `./mvnw failsafe:integration-test failsafe:verify` | `correctness`, `behavior` |
| OBS-B2 curl | `curl -sS -o /dev/null -w '%{http_code}' http://localhost:8080/actuator/health` | `behavior` |
| OBS-B3 Database Query | 마이그레이션 반영 확인은 `./gradlew flywayInfo` 또는 `./mvnw liquibase:status` (조회 자체는 `psql` 등 스택 무관 도구) | `behavior`, `correctness` |
| OBS-B4 Application Log | Logback JSON encoder 로 `.harness/logs/app.log` 에 남기고 `grep -cE '"level":"(ERROR|FATAL)"' .harness/logs/app.log` | `behavior` |
| OBS-B5 Metric | `curl -sS http://localhost:8080/actuator/prometheus \| grep http_server_requests_seconds_count.*status=\"5` | `performance` |
| OBS-B6 Trace | Micrometer Tracing + OTLP 수집기 조회 결과를 `.harness/logs/trace.log` 로 저장 | `performance` |
| OBS-B7 Load Test | `k6 run load/smoke.js` 또는 Gatling `./gradlew gatlingRun` | `performance` |

`OBS-C1`(exit code)과 `OBS-C3`(diff)은 언어와 무관하므로 여기 적지 않습니다. 코어가 소유합니다.

Spring Boot 앱의 `smoke` 단계는 앱을 띄우고 curl 을 친 뒤 내리는 스크립트가 필요합니다. 그 스크립트는 프로젝트가 소유하며 `HARNESS_STEPS` 에서 `./scripts/smoke.sh` 로 호출합니다.

## 4. 보호 패턴의 근거

> 코어: [../../../rules/evaluation-integrity.rule.md](../../../rules/evaluation-integrity.rule.md) EI-1, EI-6, [../../../hooks/README.md](../../../hooks/README.md)

`lang.sh` 의 보호 목록은 다음 근거로 정했습니다. 목록을 늘리거나 줄이는 것은 하네스 변경이며 승격 절차를 거칩니다.

| 패턴 | 목록 | 이 파일을 고치면 무엇이 약해지는가 |
| --- | --- | --- |
| `checkstyle.xml`, `checkstyle-suppressions.xml`, `config/checkstyle/*` | 차단 | 규칙을 `severity=ignore` 로 바꾸거나 억제 목록을 늘리면 `quality` 가 측정되지 않은 채 오릅니다 |
| `archunit.properties` | 차단 | `freeze.store.default.allowStoreCreation=true` 로 위반을 동결하면 `architecture` 가 통과로 바뀝니다 |
| `spotbugs-exclude.xml`, `pmd-ruleset.xml`, `detekt.yml` 및 `config/*` | 차단 | 정적 분석 제외 목록입니다 |
| `junit-platform.properties` | 차단 | `junit.jupiter.conditions.deactivate=*` 로 `@Disabled` 를 무시하거나 병렬 설정을 바꿔 테스트 의미를 바꿉니다 |
| `build.gradle(.kts)`, `pom.xml` | 경고 | 의존성 추가는 정상이지만 `test { exclude ... }`, `checkstyle { ignoreFailures = true }`, `<skipTests>` 가 같은 파일에 들어갑니다 |
| `gradle.properties`, `gradle/libs.versions.toml` | 경고 | 플러그인 버전 하향으로 검사가 조용히 약해질 수 있습니다 |

`@Disabled`, `@Ignore`, `assumeTrue(false)` 를 테스트에 추가하는 것은 파일 패턴으로 잡히지 않습니다. 이것은 EI-6 의 "테스트 skip" 이며 리뷰와 REP-3 과제가 잡습니다.

## 5. improvement candidate 예시

- [improvement-log.example.yaml](improvement-log.example.yaml) — 1절 사건을 기록한 candidate. 코어 예시 [../../../improvement-log/2026-08-09-001.example.yaml](../../../improvement-log/2026-08-09-001.example.yaml) 과 같은 사건이며 클래스·도구 이름만 구체적입니다.

## 관련 문서

- [../README.md](../README.md) — Java 팩 개요
- [../../README.md](../../README.md) — 팩 규약
- [../../../references/harness-elements.md](../../../references/harness-elements.md) — 강제력 사다리 EL-1~EL-7
- [../../../references/agent-observability.md](../../../references/agent-observability.md) — OBS-* 채널 정의
- [../../../rules/evaluation-integrity.rule.md](../../../rules/evaluation-integrity.rule.md) — 보호 패턴의 규범
