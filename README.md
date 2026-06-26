# 🏭 Python Odoo ERP — Production Stack

Production-ready **Odoo 17** deployment với Docker Compose, PostgreSQL, Redis, và Nginx.

## 🏗️ Kiến Trúc

```
Internet
   │
   ▼
[Nginx :443]  ─── SSL termination, rate limiting, gzip
   │
   ├──► [Odoo :8069]   ─── Web + JSON-RPC
   │
   └──► [Odoo :8072]   ─── Longpolling / LiveChat
          │
          ├──► [PostgreSQL :5432]  ─── Database
          └──► [Redis :6379]       ─── Session / Cache

🔗 Network: odoo_net (bridge)
```

## 📁 Cấu Trúc

```
Python-Odoo-ERP/
├── docker-compose.yml        # Stack chính
├── .env.example              # Template biến môi trường
├── .gitignore
│
├── config/
│   └── odoo.conf             # Odoo production config
│
├── nginx/
│   ├── nginx.conf            # Nginx main config
│   ├── conf.d/
│   │   └── odoo.conf         # Virtual host + SSL
│   └── ssl/                  # SSL certificates (gitignored)
│
├── custom_addons/            # Custom Odoo modules
│   ├── sale_management_custom/
│   ├── purchase_management_custom/
│   └── stock_management_custom/
│
├── scripts/
│   ├── start.sh              # Khởi động stack
│   ├── backup.sh             # Backup DB + filestore
│   ├── restore.sh            # Restore từ backup
│   └── init-db.sh            # PostgreSQL tuning (auto-run)
│
├── logs/
│   └── odoo/                 # Odoo log files
└── backups/                  # Backup archives
```

## 🚀 Cài Đặt & Chạy

### 1. Clone & Cấu hình

```bash
cd /home/thinh/WorkSpace/Python-Odoo-ERP

# Copy và chỉnh sửa biến môi trường
cp .env.example .env
nano .env   # ← thay tất cả CHANGE_ME bằng password thật
```

### 2. Cấp quyền scripts

```bash
chmod +x scripts/*.sh
```

### 3. Khởi động

```bash
./scripts/start.sh
```

Hoặc thủ công:
```bash
docker compose up -d
```

### 4. Theo dõi logs

```bash
docker compose logs -f odoo          # Odoo logs
docker compose logs -f db            # PostgreSQL logs
docker compose logs -f nginx         # Nginx access/error logs
```

## 🔧 Lệnh Hay Dùng

| Lệnh | Mô tả |
|------|--------|
| `docker compose ps` | Xem trạng thái services |
| `docker compose restart odoo` | Restart Odoo |
| `docker compose exec odoo bash` | Vào shell Odoo |
| `docker compose exec db psql -U odoo` | Vào PostgreSQL |
| `./scripts/backup.sh` | Backup toàn bộ |
| `./scripts/restore.sh backups/20240101_120000` | Restore |

## 🔐 Network

- **Tên network**: `odoo_net` (bridge driver)
- PostgreSQL & Redis **không expose** port ra host
- Chỉ Nginx expose port **80** và **443**

## 🛡️ Security Checklist

- [x] `list_db = False` — ẩn danh sách database
- [x] HTTPS only với TLS 1.2+
- [x] HSTS header
- [x] Rate limiting login (5 req/min)
- [x] DB không expose port ra ngoài
- [x] `.env` trong `.gitignore`
- [x] Session cookie: `Secure` + `HttpOnly`

## 📦 Custom Modules

| Module | Mô Tả |
|--------|--------|
| `sale_management_custom` | Bán hàng + approval flow |
| `purchase_management_custom` | Mua hàng + vendor evaluation |
| `stock_management_custom` | Kho + internal transfer |

## 🔄 Update Odoo

```bash
# Pull image mới
docker compose pull odoo

# Restart với update modules
docker compose up -d odoo

# Update module cụ thể
docker compose exec odoo odoo -d odoo_prod -u sale_management_custom --stop-after-init
```
