#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  start.sh — Khởi động Odoo ERP production stack
# ─────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"

# Kiểm tra .env
if [[ ! -f ".env" ]]; then
    echo "❌  File .env chưa tồn tại. Copy từ .env.example:"
    echo "    cp .env.example .env && nano .env"
    exit 1
fi

# Tạo thư mục cần thiết
mkdir -p logs/odoo backups nginx/ssl

# Kiểm tra SSL certs (tùy chọn — dev mode dùng self-signed)
if [[ ! -f "nginx/ssl/fullchain.pem" ]]; then
    echo "⚠️  SSL cert chưa có. Tạo self-signed cert cho dev:"
    openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
        -keyout nginx/ssl/privkey.pem \
        -out nginx/ssl/fullchain.pem \
        -subj "/CN=localhost"
    echo "   ✅ Self-signed cert created (chỉ dùng cho dev/test)"
fi

echo "🚀 Starting Odoo ERP stack..."
docker compose up -d --remove-orphans

echo ""
echo "📋 Service status:"
docker compose ps

echo ""
echo "🌐 Odoo đang chạy tại:"
echo "   HTTP : http://localhost"
echo "   HTTPS: https://localhost"
echo ""
echo "📝 Xem logs:"
echo "   docker compose logs -f odoo"
