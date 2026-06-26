#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  auto_backup.sh — Backup tự động hằng ngày lúc 2:00 AM
#  Thêm vào crontab: 0 2 * * * /path/to/scripts/auto_backup.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Load .env
if [[ -f ".env" ]]; then
    set -a; source .env; set +a
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups/${TIMESTAMP}"
DB_NAME="${POSTGRES_DB:-odoo_prod}"
DB_USER="${POSTGRES_USER:-odoo}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
LOG_FILE="./logs/backup.log"
NOTIFY_EMAIL="${BACKUP_NOTIFY_EMAIL:-}"

mkdir -p "${BACKUP_DIR}" "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
error_exit() { log "❌ ERROR: $1"; send_alert "FAILED" "$1"; exit 1; }

send_alert() {
    local status="$1"
    local message="$2"
    if [[ -n "${NOTIFY_EMAIL}" ]]; then
        echo "Backup ${status}: ${message}" | mail -s "[Odoo Backup] ${status} - $(hostname)" "${NOTIFY_EMAIL}" 2>/dev/null || true
    fi
}

log "═══════════════════════════════════════"
log "🚀 Auto Backup Started: ${TIMESTAMP}"
log "   DB: ${DB_NAME} | Retention: ${RETENTION_DAYS} ngày"

# ── 1. Dump PostgreSQL ─────────────────────────────────────────
log "📦 Step 1/3: Dumping PostgreSQL..."
docker compose exec -T db \
    pg_dump -U "${DB_USER}" -Fc "${DB_NAME}" \
    > "${BACKUP_DIR}/odoo_db.dump" \
    || error_exit "pg_dump failed"

DB_SIZE=$(du -sh "${BACKUP_DIR}/odoo_db.dump" | cut -f1)
log "   ✅ DB dump: ${DB_SIZE}"

# ── 2. Backup Filestore ─────────────────────────────────────────
log "📁 Step 2/3: Compressing filestore..."
docker run --rm \
    -v odoo_filestore:/data:ro \
    -v "$(pwd)/backups/${TIMESTAMP}:/backup" \
    alpine \
    tar czf /backup/odoo_filestore.tar.gz -C /data . \
    || error_exit "Filestore backup failed"

FS_SIZE=$(du -sh "${BACKUP_DIR}/odoo_filestore.tar.gz" | cut -f1)
log "   ✅ Filestore: ${FS_SIZE}"

# ── 3. Cleanup old backups ─────────────────────────────────────
log "🧹 Step 3/3: Cleaning backups older than ${RETENTION_DAYS} days..."
find ./backups -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf {} + 2>/dev/null || true
REMAINING=$(find ./backups -maxdepth 1 -type d | wc -l)
log "   ✅ Remaining backups: $((REMAINING - 1))"

# ── Summary ────────────────────────────────────────────────────
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
log "═══════════════════════════════════════"
log "✅ Backup COMPLETED: ${TIMESTAMP}"
log "   Location: ${BACKUP_DIR}"
log "   Total size: ${TOTAL_SIZE}"
log "═══════════════════════════════════════"

send_alert "SUCCESS" "Backup ${TIMESTAMP} completed. Size: ${TOTAL_SIZE}"
