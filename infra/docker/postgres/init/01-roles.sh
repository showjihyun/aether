#!/usr/bin/env bash
set -euo pipefail

# aether_control / aether_data 역할만 만듭니다(spec 2.8, plan P0-8 순서 2).
# 스키마·테이블·GRANT 는 apps/api/migrations 가 소유합니다 — 역할은 클러스터
# 수준이라 마이그레이션(단일 DB 트랜잭션)이 만들 수 없어 여기서 만듭니다.
#
# 비밀번호는 환경변수로만 받습니다. 원문을 이 파일에 남기지 않습니다.
: "${AETHER_CONTROL_PASSWORD:?AETHER_CONTROL_PASSWORD 환경변수가 필요합니다}"
: "${AETHER_DATA_PASSWORD:?AETHER_DATA_PASSWORD 환경변수가 필요합니다}"
: "${POSTGRES_USER:?POSTGRES_USER 환경변수가 필요합니다}"
: "${POSTGRES_DB:?POSTGRES_DB 환경변수가 필요합니다}"

# DO $do$ ... $do$ 블록을 쓰지 않습니다 — psql 의 `:'var'` 치환은 dollar-quoting
# 안에는 적용되지 않아 `CREATE ROLE ... PASSWORD :'control_pw'` 가 리터럴 문자열
# ":'control_pw'" 로 그대로 들어가거나 구문 오류를 냅니다. `\gexec` 는 psql
# 메타명령이라 치환이 먼저 일어난 뒤 psql 이 그 결과(SELECT 가 낸 SQL 문자열)를
# 실행합니다 — heredoc 이 `'SQL'` 로 인용되어 있어도 동작합니다.
psql -v ON_ERROR_STOP=1 \
     -v control_pw="$AETHER_CONTROL_PASSWORD" \
     -v data_pw="$AETHER_DATA_PASSWORD" \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" <<-'SQL'
SELECT format('CREATE ROLE aether_control LOGIN PASSWORD %L', :'control_pw')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'aether_control') \gexec

SELECT format('CREATE ROLE aether_data LOGIN PASSWORD %L', :'data_pw')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'aether_data') \gexec
SQL
