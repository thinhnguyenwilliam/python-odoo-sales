#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  backup.sh — Backup PostgreSQL + Odoo filestore
#  Sử dụng: ./scripts/backup.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups/${TIMESTAMP}"
DB_NAME="${POSTGRES_DB:-odoo_prod}"
DB_USER="${POSTGRES_USER:-odoo}"

echo "📦 Starting backup: ${TIMESTAMP}"
mkdir -p "${BACKUP_DIR}"

# 1. Dump PostgreSQL
echo "   → Dumping database ${DB_NAME}..."
docker compose exec -T db \
    pg_dump -U "${DB_USER}" -Fc "${DB_NAME}" \
    > "${BACKUP_DIR}/odoo_db.dump"

# 2. Backup filestore
echo "   → Compressing filestore..."
docker run --rm \
    -v odoo_filestore:/data:ro \
    -v "$(pwd)/backups/${TIMESTAMP}:/backup" \
    alpine \
    tar czf /backup/odoo_filestore.tar.gz -C /data .

echo "✅ Backup saved to: ${BACKUP_DIR}"
echo "   Files:"
ls -lh "${BACKUP_DIR}"
