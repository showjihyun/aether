#!/usr/bin/env bash
# language/typescript/lang.sh — TypeScript/JavaScript 언어 팩. 직접 실행하지 않고 scripts/lib/detect-stack.sh 가 source 합니다.
# 계약: language/README.md 2절.
#
# 스택 ID : typescript | typescript:pnpm | typescript:yarn | typescript:npm | typescript:bun
# kind    : frontend | backend | fullstack | unknown  (package.json 의 의존성 이름으로 판정)
# 담당     : package.json 감지, scripts 기반 기본 단계, kind 별 추가 단계,
#            ESLint·tsconfig·Biome·dependency-cruiser·Playwright·Jest 설정 보호 패턴
#
# JavaScript 전용 프로젝트도 이 팩이 담당합니다. 타입 검사 단계는 scripts 에 있을 때만 생성됩니다.

if [[ -n "${HARNESS_LANG_TYPESCRIPT_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
HARNESS_LANG_TYPESCRIPT_LOADED=1

HARNESS_LANG_PACKS+=(typescript)

# --- 감지 ---------------------------------------------------------------------
harness_lang_typescript_detect() {
  local root="${1:-$PWD}"
  [[ -f "$root/package.json" ]] || return 1
  if [[ -f "$root/pnpm-lock.yaml" ]]; then
    printf 'typescript:pnpm\n'
  elif [[ -f "$root/yarn.lock" ]]; then
    printf 'typescript:yarn\n'
  elif [[ -f "$root/bun.lockb" || -f "$root/bun.lock" ]]; then
    printf 'typescript:bun\n'
  elif [[ -f "$root/package-lock.json" || -f "$root/npm-shrinkwrap.json" ]]; then
    printf 'typescript:npm\n'
  else
    printf 'typescript\n'
  fi
  return 0
}

# kind 판정 근거가 되는 의존성 이름. 정규식 alternation 입니다.
# 브라우저(또는 웹뷰)에서 실행되는 결과물을 만드는 프레임워크·번들러.
HARNESS_LANG_TYPESCRIPT_FRONTEND_DEPS='react|react-dom|react-native|react-native-web|vue|vue-router|nuxt|next|svelte|@sveltejs/kit|@angular/core|@angular/common|@angular/platform-browser|solid-js|preact|astro|gatsby|vite|@remix-run/react|expo|@builder\.io/qwik'
# 서버·워커로 실행되는 프레임워크·ORM.
HARNESS_LANG_TYPESCRIPT_BACKEND_DEPS='express|@nestjs/core|@nestjs/common|@nestjs/platform-express|fastify|koa|hono|elysia|@hapi/hapi|restify|@adonisjs/core|@trpc/server|@apollo/server|apollo-server|apollo-server-express|graphql-yoga|prisma|@prisma/client|typeorm|drizzle-orm|mongoose|knex|sequelize|mikro-orm|@mikro-orm/core'

# --- package.json 읽기 -----------------------------------------------------------
# _harness_lang_typescript_json_block <파일> <최상위 키> — 그 키의 객체 값만 출력합니다.
# 한 줄로 압축된 package.json 에서도 동작해야 하므로 줄 범위(sed)가 아니라 중괄호 깊이를 셉니다.
# 줄 범위로 자르면 1줄 파일에서 범위가 닫히지 않아 파일 전체가 "scripts 블록"이 되고,
# 의존성 이름이 존재하지 않는 스크립트로 잡혀 필수 단계가 만들어집니다.
_harness_lang_typescript_json_block() {
  awk -v key="$2" '
    { s = s $0 "\n" }
    END {
      pat = "\"" key "\"[ \t\r\n]*:[ \t\r\n]*\\{"
      if (match(s, pat) == 0) exit 1
      start = RSTART + RLENGTH - 1
      depth = 0; instr = 0; esc = 0
      for (i = start; i <= length(s); i++) {
        c = substr(s, i, 1)
        if (esc) { esc = 0; continue }
        if (instr) {
          if (c == "\\") { esc = 1; continue }
          if (c == "\"") instr = 0
          continue
        }
        if (c == "\"") { instr = 1; continue }
        if (c == "{") depth++
        else if (c == "}") {
          depth--
          if (depth == 0) { print substr(s, start, i - start + 1); exit 0 }
        }
      }
      exit 1
    }' "$1" 2>/dev/null
}

# kind 는 **의존성 블록만** 보고 판정합니다. 파일 전체를 grep 하면 scripts 의 명령 이름,
# overrides 의 버전 고정, 주석성 키가 판정을 뒤집습니다.
harness_lang_typescript_kind() {
  local root="${1:-$PWD}" stack="${2:-}" pkg deps="" b fe=0 be=0
  pkg="$root/package.json"
  [[ -f "$pkg" ]] || { printf 'unknown\n'; return 0; }
  for b in dependencies devDependencies peerDependencies optionalDependencies; do
    deps="${deps}$(_harness_lang_typescript_json_block "$pkg" "$b" || true)"
  done
  [[ -n "$deps" ]] || { printf 'unknown\n'; return 0; }
  printf '%s' "$deps" | grep -qE "\"(${HARNESS_LANG_TYPESCRIPT_FRONTEND_DEPS})\"[[:space:]]*:" && fe=1
  printf '%s' "$deps" | grep -qE "\"(${HARNESS_LANG_TYPESCRIPT_BACKEND_DEPS})\"[[:space:]]*:" && be=1
  if [[ "$fe" -eq 1 && "$be" -eq 1 ]]; then
    printf 'fullstack\n'
  elif [[ "$fe" -eq 1 ]]; then
    printf 'frontend\n'
  elif [[ "$be" -eq 1 ]]; then
    printf 'backend\n'
  else
    printf 'unknown\n'
  fi
}

# --- package.json scripts -----------------------------------------------------------
# harness_lang_typescript_has_script <프로젝트루트> <스크립트명>
# jq 가 있으면 jq 로, 없으면 "scripts" 객체만 잘라내 확인합니다.
harness_lang_typescript_has_script() {
  local root="$1" name="$2" block
  local pkg="$root/package.json"
  [[ -f "$pkg" ]] || return 1
  if have_cmd jq; then
    jq -e --arg n "$name" '(.scripts // {}) | has($n)' "$pkg" >/dev/null 2>&1
    return $?
  fi
  block="$(_harness_lang_typescript_json_block "$pkg" scripts)" || return 1
  printf '%s' "$block" | grep -q "\"${name}\"[[:space:]]*:"
}

# 스크립트 실행 명령 접두사.
harness_lang_typescript_run_prefix() {
  case "$1" in
    pnpm) printf 'pnpm run' ;;
    yarn) printf 'yarn run' ;;
    bun) printf 'bun run' ;;
    *) printf 'npm run --silent' ;;
  esac
}

# --- 기본 verify 단계 -------------------------------------------------------------
# 형식: "script|id|layer|required". package.json 의 scripts 에 실제로 존재하는 항목만 단계로 넣습니다.
# 같은 id 가 두 번 나오면(typecheck / type-check) 먼저 발견된 것만 씁니다.

# FE/BE 공통.
HARNESS_LANG_TYPESCRIPT_STEP_MAP=(
  "typecheck|typecheck|quality|true"
  "type-check|typecheck|quality|true"
  "lint|lint|quality|true"
  "format:check|format-check|quality|false"
  "build|build|correctness|true"
  "test:arch|arch-test|architecture|true"
  "arch|arch-test|architecture|true"
  "depcruise|dep-check|architecture|false"
  "test|test|correctness|true"
  "test:unit|unit|correctness|true"
  "test:integration|integration|correctness|true"
  "test:e2e|e2e|behavior|false"
  "e2e|e2e|behavior|false"
  "bench|bench|performance|false"
)

# frontend 에만 의미 있는 단계 (OBS-F1~F5, 번들 크기, 접근성).
HARNESS_LANG_TYPESCRIPT_FRONTEND_STEP_MAP=(
  "test:a11y|a11y|behavior|false"
  "test:visual|visual|behavior|false"
  "test:storybook|storybook|behavior|false"
  "size|bundle-size|performance|false"
  "size-limit|bundle-size|performance|false"
  "lighthouse|lighthouse|performance|false"
)

# backend 에만 의미 있는 단계 (계약·스키마·부하·스모크).
HARNESS_LANG_TYPESCRIPT_BACKEND_STEP_MAP=(
  "test:contract|contract|correctness|false"
  "db:validate|db-validate|architecture|false"
  "prisma:validate|db-validate|architecture|false"
  "migrate:check|migration-check|architecture|false"
  "smoke|smoke|behavior|false"
  "test:load|load|performance|false"
)

# _harness_lang_typescript_steps_from_map <root> <run접두사> <seen문자열변수명> <매핑배열이름>
_harness_lang_typescript_steps_from_map() {
  local root="$1" run="$2" seen_var="$3" map_name="$4"
  local ref="${map_name}[@]" entry script id layer required
  for entry in "${!ref}"; do
    IFS='|' read -r script id layer required <<<"$entry"
    [[ "${!seen_var}" == *" ${id} "* ]] && continue
    if harness_lang_typescript_has_script "$root" "$script"; then
      _emit_step "$id" "$layer" "$required" "${run} ${script}"
      printf -v "$seen_var" '%s%s ' "${!seen_var}" "$id"
    fi
  done
}

harness_lang_typescript_default_steps() {
  local stack="${1:-typescript}" root="${2:-$PWD}" kind="${3:-unknown}"
  local pm run seen=" "
  pm="${stack#typescript}"; pm="${pm#:}"
  [[ -n "$pm" ]] || pm="npm"
  run="$(harness_lang_typescript_run_prefix "$pm")"

  _harness_lang_typescript_steps_from_map "$root" "$run" seen HARNESS_LANG_TYPESCRIPT_STEP_MAP
  case "$kind" in
    frontend)
      _harness_lang_typescript_steps_from_map "$root" "$run" seen HARNESS_LANG_TYPESCRIPT_FRONTEND_STEP_MAP ;;
    backend)
      _harness_lang_typescript_steps_from_map "$root" "$run" seen HARNESS_LANG_TYPESCRIPT_BACKEND_STEP_MAP ;;
    *)
      # fullstack / unknown — 두 kind 의 합집합
      _harness_lang_typescript_steps_from_map "$root" "$run" seen HARNESS_LANG_TYPESCRIPT_FRONTEND_STEP_MAP
      _harness_lang_typescript_steps_from_map "$root" "$run" seen HARNESS_LANG_TYPESCRIPT_BACKEND_STEP_MAP ;;
  esac
}

# --- 보호 패턴 -----------------------------------------------------------------
# FE/BE 공통 차단: lint·타입·의존성 경계 설정. 바뀌면 quality/architecture 계층의 의미가 달라집니다.
HARNESS_LANG_TYPESCRIPT_PROTECTED_PATTERNS=(
  ".eslintrc"
  ".eslintrc.*"
  "eslint.config.*"
  "tsconfig.json"
  "tsconfig.*.json"
  "biome.json"
  "biome.jsonc"
  ".oxlintrc.json"
  ".dependency-cruiser.*"
  ".stylelintrc"
  ".stylelintrc.*"
  "knip.json"
  "knip.config.*"
)

# FE/BE 공통 경고: 바뀌는 것이 정상이지만 테스트 범위·검증 스크립트가 같은 파일에 있습니다.
HARNESS_LANG_TYPESCRIPT_WARN_PATTERNS=(
  "package.json"
  ".eslintignore"
  "vitest.config.*"
  "vitest.workspace.*"
  "jest.config.*"
  ".npmrc"
  ".nvmrc"
  ".node-version"
  "pnpm-workspace.yaml"
  "turbo.json"
  "nx.json"
)

# frontend 추가 차단: 브라우저 관측 채널(OBS-F1~F5)과 성능 예산을 정의하는 파일.
HARNESS_LANG_TYPESCRIPT_FRONTEND_PROTECTED_PATTERNS=(
  "playwright.config.*"
  "cypress.config.*"
  ".size-limit.*"
  "lighthouserc.*"
  ".lighthouserc.*"
  "axe.config.*"
  ".storybook/test-runner.*"
)
HARNESS_LANG_TYPESCRIPT_FRONTEND_WARN_PATTERNS=(
  "vite.config.*"
  "next.config.*"
  "nuxt.config.*"
  "svelte.config.*"
  "angular.json"
  ".storybook/*"
  ".browserslistrc"
  "postcss.config.*"
  "tailwind.config.*"
)

# backend 추가 차단: 통합·E2E 테스트 러너 설정.
HARNESS_LANG_TYPESCRIPT_BACKEND_PROTECTED_PATTERNS=(
  "jest-e2e.json"
  "test/jest-e2e.json"
  ".mocharc.*"
)
HARNESS_LANG_TYPESCRIPT_BACKEND_WARN_PATTERNS=(
  "prisma/schema.prisma"
  "prisma/migrations/*"
  "drizzle.config.*"
  "knexfile.*"
  "ormconfig.*"
  "docker-compose*.yml"
  "docker-compose*.yaml"
)

# 보안 민감 경로: 레지스트리 토큰이 들어가는 파일.
HARNESS_LANG_TYPESCRIPT_SECURITY_PATTERNS='\.npmrc$|\.yarnrc(\.yml)?$'
