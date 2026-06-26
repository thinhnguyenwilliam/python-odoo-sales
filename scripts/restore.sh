#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  restore.sh — Restore PostgreSQL + Odoo filestore
#  Sử dụng: ./scripts/restore.sh backups/20240101_120000
# ─────────────────────────────────────────────────────────────
set -euo pipefail

BACKUP_DIR="${1:-}"
if [[ -z "${BACKUP_DIR}" ]]; then
    echo "❌  Usage: $0 <backup_dir>"
    echo "   Example: $0 backups/20240101_120000"
    exit 1
fi

DB_NAME="${POSTGRES_DB:-odoo_prod}"
DB_USER="${POSTGRES_USER:-odoo}"

echo "🔄 Restoring from: ${BACKUP_DIR}"

# 1. Restore database
echo "   → Restoring database..."
docker compose exec -T db \
    psql -U "${DB_USER}" -c "DROP DATABASE IF EXISTS ${DB_NAME};"
docker compose exec -T db \
    psql -U "${DB_USER}" -c "CREATE DATABASE ${DB_NAME};"
cat "${BACKUP_DIR}/odoo_db.dump" | docker compose exec -T db \
    pg_restore -U "${DB_USER}" -d "${DB_NAME}" --no-owner

# 2. Restore filestore
echo "   → Restoring filestore..."
docker run --rm \
    -v odoo_filestore:/data \
    -v "$(pwd)/${BACKUP_DIR}:/backup:ro" \
    alpine \
    sh -c "rm -rf /data/* && tar xzf /backup/odoo_filestore.tar.gz -C /data"

echo "✅ Restore completed successfully."
