# TASA WebUI — Agent Context & Upgrade Guide

This file is for AI agents (Kilo) working on the TASA fork of Open WebUI. Read this first before making changes.

## Project Overview

- **Fork**: `chopstar001/open-webui` (GitHub)
- **Upstream**: `open-webui/open-webui` (GitHub)
- **Branch**: `tasa-upgrade` (based on `v0.11.4`)
- **Purpose**: Custom billing/SHKeeper crypto payments + TASA theme on top of Open WebUI

## Architecture

### Custom Backend Files (TASA-specific, not in upstream)
| File | Purpose |
|---|---|
| `backend/open_webui/billing_poller.py` | Background task polling SHKeeper for payment confirmations |
| `backend/open_webui/models/subscription.py` | SQLAlchemy models: `SubscriptionPlan`, `UserSubscription`, `PaymentInvoice` |
| `backend/open_webui/routers/billing.py` | REST API: plan CRUD, subscription management, invoice creation |
| `backend/open_webui/utils/billing.py` | Billing helpers and tier enforcement |
| `backend/open_webui/utils/shkeeper.py` | SHKeeper crypto payment gateway client |
| `backend/open_webui/migrations/versions/c7e4a2b9d3f1_add_subscription_tables.py` | Migration for subscription tables (idempotent) |

### Custom Frontend Files (TASA-specific)
| File | Purpose |
|---|---|
| `src/lib/apis/billing/index.ts` | Billing API client |
| `src/routes/(app)/billing/` | Billing pages (plans, checkout, invoices) |
| `static/themes/tasa.css` | TASA theme CSS (loaded via `<link>` in `app.html`) |
| `static/static/custom.css` | Supplementary TASA CSS |
| `tasa-rebrand.sh` | Re-apply branding after upstream updates |

### Modified Files (custom patches on upstream code)
| File | Change | Risk |
|---|---|---|
| `Dockerfile` | `NODE_OPTIONS=8192` for frontend build OOM | Low |
| `backend/open_webui/utils/middleware.py` | A0 bridge `<!--STATUS:-->` detection + tool call status events | Medium |
| `backend/open_webui/utils/models.py` | Keep disabled base models visible (re-enable bug fix) | Low |
| `backend/open_webui/routers/files.py` | A0 proxy notification + archive detection (skip RAG for zips) | Low |
| `src/app.html` | `tasa.css` link, `tasa` theme in inline script | Low |
| `src/app.css` | `prose-headings:font-normal` (TASA font weight) | Low |
| `src/lib/constants.ts` | `WEBUI_HOSTNAME`/`WEBUI_BASE_URL` browser-aware | Low |
| `src/lib/components/chat/Settings/General.svelte` | `tasa` theme in themes array + dropdown option | Low |
| `src/lib/components/layout/Sidebar.svelte` | Heavy TASA customization (1661 lines) | High |
| `src/lib/components/layout/Sidebar/UserMenu.svelte` | Billing tier display in user menu | Medium |
| `src/lib/components/chat/Settings/Account.svelte` | Heavy TASA customization (718 lines) | High |
| `src/routes/+layout.svelte` | `tasa` in themes array, `WEBUI_HOSTNAME` import | Low |

## Upgrade Procedure

### 1. Backup
```bash
docker commit open-webui open-webui-backup:$(date +%Y%m%d)
docker run --rm -v open-webui_open-webui:/data -v $(pwd):/backup alpine \
  tar czf /backup/open-webui-data-$(date +%Y%m%d).tar.gz -C /data .
```

### 2. Save custom files
```bash
mkdir -p /tmp/tasa-custom-backup
git diff --name-only <old-base> tasa-upgrade | while read f; do
  mkdir -p "/tmp/tasa-custom-backup/$(dirname "$f")"
  cp "$f" "/tmp/tasa-custom-backup/$f" 2>/dev/null
done
```

### 3. Create upgrade branch
```bash
git checkout -b tasa-upgrade-NEW vX.Y.Z
```

### 4. Re-apply custom files
- **New files** (billing, theme, scripts): copy directly from backup
- **Modified files**: take upstream version, re-apply TASA patches (see table above)
- **High-risk files** (`Sidebar.svelte`, `Account.svelte`): may need manual re-implementation against upstream changes

### 5. Fix migration chain
- Check migration HEAD: `python3 -c "..."` (find head revision)
- Create new migration if needed, chained to upstream HEAD
- Migration must be **idempotent** (check `inspector.get_table_names()` before `create_table`)
- Verify single HEAD after adding migration

### 6. Build & test
```bash
docker build -t open-webui:vX.Y.Z-tasa .
docker stop open-webui && docker rm open-webui
docker run -d --name open-webui -p 3000:8080 \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui_open-webui:/app/backend/data \
  --restart always open-webui:vX.Y.Z-tasa
```

### 7. Verify
- Container healthy: `docker ps`
- Migrations ran: `docker logs open-webui | grep alembic`
- Theme works: select TASA in Settings → General → Theme
- Billing works: check subscription pages load

## Known Issues & Gotchas

1. **Migration conflicts**: Custom migrations must chain to upstream HEAD. Always check for multiple heads after adding a migration. Use idempotent patterns (`if table not in existing`).

2. **Frontend OOM**: Dockerfile needs `NODE_OPTIONS="--max-old-space-size=8192"` for `npm run build`. The upstream Dockerfile has this commented out.

3. **Theme CSS loading**: `tasa.css` is loaded via `<link href="/themes/tasa.css">` in `app.html`. The inline theme script in `app.html` must handle `tasa` case (falls through to `dark` otherwise).

4. **Chatbox background**: `#message-input-container` uses `bg-white/5 backdrop-blur-sm` in upstream. TASA CSS must override with solid background + `overflow: hidden` for rounded corners.

5. **`General.svelte` themes array**: Must include `'tasa'` AND have a corresponding `<option value="tasa">` in the dropdown HTML.

6. **`+layout.svelte` themes array**: Must include `'tasa'` so the class is removed when switching themes.

7. **VS Code History**: File recovery from `~/.config/Code - OSS/User/History/` saved us after `git filter-repo` disaster. Each history directory has `entries.json` (path + timestamps) and snapshot files (actual content). Always take the latest timestamp.

8. **Docker container is a recovery source**: `docker cp open-webui:/app/backend/open_webui/` extracts the backend code from the running container. Useful when git history is lost.

## Git Remotes

- `origin` = `https://github.com/chopstar001/open-webui.git` (fork)
- `upstream` = `https://github.com/open-webui/open-webui.git` (upstream)

## Deployment

- Container name: `open-webui`
- Port: `3000` → `8080`
- Volume: `open-webui_open-webui:/app/backend/data` (SQLite DB, uploads, config)
- Restart: `./run.sh` (builds + restarts) or `./restart.sh` (restart only)
