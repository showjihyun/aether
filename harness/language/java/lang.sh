#!/usr/bin/env bash
# language/java/lang.sh — Java 언어 팩. 직접 실행하지 않고 scripts/lib/detect-stack.sh 가 source 합니다.
# 계약: language/README.md 2절.
#
# 스택 ID : java:gradle | java:maven
# kind    : backend
# 담당     : Gradle/Maven 감지, 컴파일·테스트·check/verify 기본 단계,
#            Checkstyle·ArchUnit·SpotBugs·PMD·JaCoCo 설정 보호 패턴

if [[ -n "${HARNESS_LANG_JAVA_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
HARNESS_LANG_JAVA_LOADED=1

HARNESS_LANG_PACKS+=(java)

# --- 감지 ---------------------------------------------------------------------
harness_lang_java_detect() {
  local root="${1:-$PWD}"
  if [[ -f "$root/build.gradle" || -f "$root/build.gradle.kts" \
     || -f "$root/settings.gradle" || -f "$root/settings.gradle.kts" ]]; then
    printf 'java:gradle\n'; return 0
  fi
  if [[ -f "$root/pom.xml" ]]; then
    printf 'java:maven\n'; return 0
  fi
  return 1
}

# Java 팩은 서버·배치·CLI 를 대상으로 합니다. Android(모바일)는 아직 별도 kind 로 다루지 않습니다.
harness_lang_java_kind() {
  printf 'backend\n'
}

# --- 명령 접두사 ----------------------------------------------------------------
# gradlew / mvnw 래퍼가 있으면 래퍼를 씁니다. 래퍼가 정본 버전을 고정하기 때문입니다.
# 존재(-f)로 판정하고 실행 권한(-x)으로 판정하지 않습니다. 실행 비트를 잃은 체크아웃에서
# -x 는 거짓이 되어 전역 gradle/mvn 으로 조용히 폴백하고, 래퍼가 고정한 것과 다른 버전으로
# 빌드됩니다. 그러면 verify 결과가 CI 결과와 대응하지 않습니다. 래퍼가 있는데 실행되지 않으면
# 그 자리에서 실패하는 편이 낫습니다. 원인과 조치가 드러납니다.
harness_lang_java_gradle_cmd() {
  local root="$1"
  if [[ -f "$root/gradlew" ]]; then printf './gradlew --console=plain'; else printf 'gradle --console=plain'; fi
}

harness_lang_java_maven_cmd() {
  local root="$1"
  if [[ -f "$root/mvnw" ]]; then printf './mvnw -B'; else printf 'mvn -B'; fi
}

# --- 기본 verify 단계 -------------------------------------------------------------
# 빌드 도구를 실행해 task 목록을 조회하지 않습니다(느리고 hook 시간 초과의 원인이 됩니다).
# 설정 파일 존재만으로 단계를 추가합니다.
harness_lang_java_default_steps() {
  local stack="${1:-java:gradle}" root="${2:-$PWD}" kind="${3:-backend}"
  case "$stack" in
    java:gradle)
      local g
      g="$(harness_lang_java_gradle_cmd "$root")"
      _emit_step compile correctness true "${g} classes testClasses"
      _emit_step test correctness true "${g} test"
      # check 는 checkstyle/spotbugs/pmd/jacoco 검증을 묶어 실행합니다. 테스트는 위에서 이미 돌렸으므로 제외합니다.
      _emit_step check quality false "${g} check -x test"
      # 통합 테스트 source set 이 있으면 별도 단계로 둡니다(OBS-B1).
      if [[ -d "$root/src/integrationTest" || -d "$root/src/intTest" ]]; then
        _emit_step integration correctness true "${g} integrationTest"
      fi
      ;;
    java:maven)
      local m
      m="$(harness_lang_java_maven_cmd "$root")"
      _emit_step compile correctness true "${m} -q compile"
      _emit_step test correctness true "${m} test"
      # verify 는 failsafe(통합 테스트)·checkstyle·spotbugs 를 묶어 실행합니다.
      #
      # 스킵 플래그를 붙이지 않습니다. 위 test 단계에서 이미 돈 단위 테스트가
      # 여기서 한 번 더 돕니다. 그 중복을 감수하는 이유는, surefire 만 끄고
      # failsafe 는 살리는 **사용자 속성이 없기** 때문입니다.
      #   -DskipTests        surefire 와 failsafe 를 모두 끕니다 → 통합 테스트가
      #                      하나도 돌지 않은 채 architecture 계층이 통과로 채점됩니다.
      #   -Dsurefire.skip    surefire 의 사용자 속성이 아닙니다. 무시되고 그대로 다 돕니다.
      #                      (이전 커밋이 이 값을 넣었는데 동작하지 않았습니다.)
      # 둘 중 하나를 고르면 "조용히 안 돌거나" "주석과 다르게 도는" 상태가 됩니다.
      # 중복 실행은 시간 비용일 뿐이고 결과는 정직합니다. 그래서 중복을 택합니다.
      # 단위 테스트를 정말 한 번만 돌리려면 POM 에서 surefire 실행에 skip 속성을
      # 바인딩하십시오(예: <skipTests>${skipUTs}</skipTests>). 그것은 프로젝트의 몫입니다.
      _emit_step verify architecture false "${m} verify"
      ;;
    *)
      : # 알 수 없는 변형 — 단계 없음
      ;;
  esac
}

# --- 보호 패턴 -----------------------------------------------------------------
# 차단: 바뀌면 quality/architecture 계층의 의미가 달라지는 파일.
HARNESS_LANG_JAVA_PROTECTED_PATTERNS=(
  "checkstyle.xml"
  "checkstyle-suppressions.xml"
  "config/checkstyle/*"
  "archunit.properties"
  "spotbugs-exclude.xml"
  "spotbugs.xml"
  "config/spotbugs/*"
  "pmd-ruleset.xml"
  "config/pmd/*"
  "detekt.yml"
  "config/detekt/*"
  "lombok.config"
  "junit-platform.properties"
)

# 경고: 바뀌는 것이 정상이지만 테스트·검증 플러그인 제거가 여기서 일어납니다.
HARNESS_LANG_JAVA_WARN_PATTERNS=(
  "build.gradle"
  "build.gradle.kts"
  "settings.gradle"
  "settings.gradle.kts"
  "gradle.properties"
  "buildSrc/*"
  "gradle/libs.versions.toml"
  "pom.xml"
  ".mvn/*"
  "jacoco*.xml"
)

# 보안 민감 경로: 키스토어와 프로필별 설정(비밀값이 들어가기 쉬운 자리).
HARNESS_LANG_JAVA_SECURITY_PATTERNS='\.jks$|\.p12$|\.keystore$|application-(prod|production|secret)[^/]*\.(yml|yaml|properties)$'
