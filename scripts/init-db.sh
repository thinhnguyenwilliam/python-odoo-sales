#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  init-db.sh — chạy 1 lần khi PostgreSQL khởi tạo lần đầu
# ─────────────────────────────────────────────────────────────
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Tối ưu PostgreSQL cho Odoo
    ALTER SYSTEM SET max_connections       = '100';
    ALTER SYSTEM SET shared_buffers        = '256MB';
    ALTER SYSTEM SET effective_cache_size  = '768MB';
    ALTER SYSTEM SET work_mem              = '16MB';
    ALTER SYSTEM SET maintenance_work_mem  = '128MB';
    ALTER SYSTEM SET checkpoint_completion_target = '0.9';
    ALTER SYSTEM SET wal_buffers           = '16MB';
    ALTER SYSTEM SET default_statistics_target = '100';
    ALTER SYSTEM SET random_page_cost      = '1.1';
    ALTER SYSTEM SET effective_io_concurrency = '200';
    SELECT pg_reload_conf();
EOSQL

echo "✅ PostgreSQL tuning applied for Odoo production."
