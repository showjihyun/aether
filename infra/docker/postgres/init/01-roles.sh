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

psql -v ON_ERROR_STOP=1 \
     -v control_pw="$AETHER_CONTROL_PASSWORD" \
     -v data_pw="$AETHER_DATA_PASSWORD" \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" <<-'SQL'
DO
$do$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'aether_control') THEN
      CREATE ROLE aether_control LOGIN PASSWORD :'control_pw';
   END IF;

   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'aether_data') THEN
      CREATE ROLE aether_data LOGIN PASSWORD :'data_pw';
   END IF;
END
$do$;
SQL
