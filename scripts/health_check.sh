#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  health_check.sh — Kiểm tra toàn bộ stack Odoo
#  Sử dụng: ./scripts/health_check.sh
#  Cron (mỗi 5 phút): */5 * * * * /path/to/scripts/health_check.sh
# ─────────────────────────────────────────────────────────────
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

if [[ -f ".env" ]]; then
    set -a; source .env; set +a
fi

LOG_FILE="./logs/health.log"
ALERT_EMAIL="${HEALTH_ALERT_EMAIL:-}"
ERRORS=()

mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
fail() { log "  ❌ FAIL: $1"; ERRORS+=("$1"); }
pass() { log "  ✅ OK: $1"; }

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "🏥 Health Check: $(date '+%Y-%m-%d %H:%M:%S')"

# ── 1. Docker containers running ─────────────────────────────
log "🐳 [1] Docker containers..."
for container in odoo_app odoo_db odoo_redis odoo_nginx; do
    status=$(sudo docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "not_found")
    health=$(sudo docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")
    if [[ "$status" == "running" ]]; then
        pass "$container ($health)"
    else
        fail "$container — status: $status"
    fi
done

# ── 2. Odoo HTTP health endpoint ──────────────────────────────
log "🌐 [2] Odoo HTTP health..."
ODOO_HEALTH=$(sudo docker compose exec -T odoo \
    curl -sf http://localhost:8069/web/health 2>/dev/null || echo "FAIL")
if echo "$ODOO_HEALTH" | grep -q "pass"; then
    pass "Odoo /web/health → {\"status\": \"pass\"}"
else
    fail "Odoo /web/health → $ODOO_HEALTH"
fi

# ── 3. Nginx HTTPS ────────────────────────────────────────────
log "🔒 [3] Nginx HTTPS..."
HTTPS_STATUS=$(curl -sko /dev/null -w "%{http_code}" --max-time 10 \
    https://localhost/web/health 2>/dev/null || echo "000")
if [[ "$HTTPS_STATUS" == "200" ]]; then
    pass "Nginx HTTPS → HTTP $HTTPS_STATUS"
else
    fail "Nginx HTTPS → HTTP $HTTPS_STATUS"
fi

# ── 4. PostgreSQL ─────────────────────────────────────────────
log "🗄️ [4] PostgreSQL..."
PG_RESULT=$(sudo docker compose exec -T db \
    pg_isready -U "${POSTGRES_USER:-odoo}" -d "${POSTGRES_DB:-odoo_prod}" 2>&1)
if echo "$PG_RESULT" | grep -q "accepting connections"; then
    pass "PostgreSQL: $PG_RESULT"
else
    fail "PostgreSQL: $PG_RESULT"
fi

# ── 5. Redis ─────────────────────────────────────────────────
log "⚡ [5] Redis..."
REDIS_RESULT=$(sudo docker compose exec -T redis \
    redis-cli -a "${REDIS_PASSWORD:-}" ping 2>/dev/null | tr -d '\r')
if [[ "$REDIS_RESULT" == "PONG" ]]; then
    pass "Redis: PONG"
else
    fail "Redis: Expected PONG, got: $REDIS_RESULT"
fi

# ── 6. Disk Space ─────────────────────────────────────────────
log "💾 [6] Disk space..."
DISK_USAGE=$(df -h / | awk 'NR==2{print $5}' | tr -d '%')
if [[ "${DISK_USAGE}" -lt 85 ]]; then
    pass "Disk: ${DISK_USAGE}% used"
else
    fail "Disk: ${DISK_USAGE}% used (> 85% threshold!)"
fi

# ── 7. Memory ─────────────────────────────────────────────────
log "🧠 [7] Memory..."
MEM_TOTAL=$(free -m | awk 'NR==2{print $2}')
MEM_USED=$(free -m | awk 'NR==2{print $3}')
MEM_PCT=$((MEM_USED * 100 / MEM_TOTAL))
if [[ "$MEM_PCT" -lt 90 ]]; then
    pass "Memory: ${MEM_PCT}% used (${MEM_USED}/${MEM_TOTAL} MB)"
else
    fail "Memory: ${MEM_PCT}% used (> 90% threshold!)"
fi

# ── 8. Backup freshness ───────────────────────────────────────
log "📦 [8] Backup freshness..."
LATEST_BACKUP=$(find ./backups -maxdepth 1 -type d -name "2*" | sort | tail -1)
if [[ -z "$LATEST_BACKUP" ]]; then
    fail "Không tìm thấy backup nào!"
else
    BACKUP_AGE=$(( ($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")) / 3600 ))
    if [[ "$BACKUP_AGE" -lt 25 ]]; then
        pass "Backup gần nhất: ${BACKUP_AGE}h trước"
    else
        fail "Backup gần nhất: ${BACKUP_AGE}h trước (> 25h!)"
    fi
fi

# ── Summary ───────────────────────────────────────────────────
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ ${#ERRORS[@]} -eq 0 ]]; then
    log "🟢 ALL CHECKS PASSED"
else
    log "🔴 ${#ERRORS[@]} CHECK(S) FAILED:"
    for err in "${ERRORS[@]}"; do
        log "   • $err"
    done
    # Gửi alert email nếu có
    if [[ -n "$ALERT_EMAIL" ]]; then
        printf "Health Check FAILED:\n\n%s\n" "$(printf '%s\n' "${ERRORS[@]}")" \
            | mail -s "[🔴 Odoo Alert] Health Check Failed — $(hostname)" "$ALERT_EMAIL" 2>/dev/null || true
    fi
    exit 1
fi
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
