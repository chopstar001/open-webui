#!/usr/bin/env bash
# =============================================================================
# TASA WebUI Rebrand Script
# =============================================================================
# Run this after every Open WebUI update to re-apply TASA WebUI branding.
#
# Usage:
#   ./tasa-rebrand.sh                  # Patch host source files only
#   ./tasa-rebrand.sh --container      # Also patch running Docker container
#   ./tasa-rebrand.sh --container --restart   # Patch + restart container
#   ./tasa-rebrand.sh --rebuild        # Rebuild Docker image (full, permanent)
#   ./tasa-rebrand.sh --theme-only     # Theme + billing only (no icon/branding changes, license-compliant)
#
# Prerequisites:
#   - favicon_io/ folder with your custom icons
#   - Run from the Open WebUI project root
# =============================================================================

set -uo pipefail

# ---- Configuration ----
OLD_NAME="Open WebUI"
NEW_NAME="TASA WebUI"
CONTAINER_NAME="${WEBUI_CONTAINER_NAME:-open-webui}"
FAVICON_DIR="./favicon_io"
BACKUP_DIR="./icon_backup"

# ---- Parse arguments ----
PATCH_CONTAINER=false
RESTART_CONTAINER=false
REBUILD_IMAGE=false
THEME_ONLY=false

for arg in "$@"; do
    case "$arg" in
        --container)  PATCH_CONTAINER=true ;;
        --restart)    RESTART_CONTAINER=true ;;
        --rebuild)    REBUILD_IMAGE=true ;;
        --theme-only) THEME_ONLY=true ;;
        --help|-h)
            head -17 "$0" | tail -14
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

# ---- Helper functions ----
log()  { echo -e "\033[1;34m[TASA]\033[0m $*"; }
ok()   { echo -e "\033[1;32m[  OK]\033[0m $*"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $*"; }
err()  { echo -e "\033[1;31m[FAIL]\033[0m $*"; exit 1; }

check_prerequisites() {
    if [ ! -d "$FAVICON_DIR" ]; then
        err "Favicon directory '$FAVICON_DIR' not found. Place your custom icons there."
    fi
    for f in android-chrome-192x192.png android-chrome-512x512.png apple-touch-icon.png favicon-32x32.png favicon.ico; do
        if [ ! -f "$FAVICON_DIR/$f" ]; then
            err "Missing icon: $FAVICON_DIR/$f"
        fi
    done
    ok "Favicon directory validated"
}

# =============================================================================
# Step 1: Replace icon files on the host
# =============================================================================
replace_host_icons() {
    log "Replacing icon files on host..."

    # Backup originals (only if not already backed up)
    if [ ! -d "$BACKUP_DIR/static_static" ]; then
        mkdir -p "$BACKUP_DIR/static_static" "$BACKUP_DIR/static_root"
        for f in apple-touch-icon.png favicon-96x96.png favicon-dark.png favicon.ico \
                  favicon.png favicon.svg logo.png site.webmanifest \
                  splash-dark.png splash.png web-app-manifest-192x192.png \
                  web-app-manifest-512x512.png; do
            [ -f "static/static/$f" ] && cp "static/static/$f" "$BACKUP_DIR/static_static/" 2>/dev/null || true
        done
        [ -f "static/favicon-32x32.png" ] && cp "static/favicon-32x32.png" "$BACKUP_DIR/static_root/" 2>/dev/null || true
        [ -f "static/favicon.png" ] && cp "static/favicon.png" "$BACKUP_DIR/static_root/" 2>/dev/null || true
        log "Original icons backed up to $BACKUP_DIR/"
    fi

    # Copy icons to static/static/
    cp "$FAVICON_DIR/android-chrome-192x192.png" static/static/web-app-manifest-192x192.png
    cp "$FAVICON_DIR/android-chrome-512x512.png" static/static/web-app-manifest-512x512.png
    cp "$FAVICON_DIR/apple-touch-icon.png"       static/static/apple-touch-icon.png
    cp "$FAVICON_DIR/favicon.ico"                static/static/favicon.ico
    cp "$FAVICON_DIR/android-chrome-192x192.png" static/static/favicon.png
    cp "$FAVICON_DIR/android-chrome-192x192.png" static/static/favicon-96x96.png
    cp "$FAVICON_DIR/android-chrome-512x512.png" static/static/favicon-dark.png
    cp "$FAVICON_DIR/android-chrome-512x512.png" static/static/splash.png
    cp "$FAVICON_DIR/android-chrome-512x512.png" static/static/splash-dark.png
    cp "$FAVICON_DIR/favicon-32x32.png"          static/static/favicon-32x32.png
    cp "$FAVICON_DIR/favicon-16x16.png"          static/static/favicon-16x16.png 2>/dev/null || true

    # Copy icons to static/ (root)
    cp "$FAVICON_DIR/favicon-32x32.png"          static/favicon-32x32.png
    cp "$FAVICON_DIR/android-chrome-192x192.png" static/favicon.png

    ok "Host icon files replaced"
}

# =============================================================================
# Step 2: Replace branding in host source files
# =============================================================================
replace_host_branding() {
    log "Replacing '$OLD_NAME' -> '$NEW_NAME' in source files..."

    # --- Core constants ---
    sed -i "s/export const APP_NAME = '.*';/export const APP_NAME = '$NEW_NAME';/" src/lib/constants.ts
    ok "src/lib/constants.ts"

    # --- Backend env.py ---
    sed -i "s|WEBUI_NAME = os.getenv('WEBUI_NAME', '.*')|WEBUI_NAME = os.getenv('WEBUI_NAME', '$NEW_NAME')|" backend/open_webui/env.py
    sed -i "s|if WEBUI_NAME != '.*':|if WEBUI_NAME != '$NEW_NAME':|" backend/open_webui/env.py
    sed -i "s|WEBUI_NAME += ' (.*)'|WEBUI_NAME += ' ($NEW_NAME)'|" backend/open_webui/env.py
    ok "backend/open_webui/env.py"

    # --- app.html ---
    sed -i "s|<title>.*</title>|<title>$NEW_NAME</title>|" src/app.html
    # Ensure tasa.css stylesheet is linked
    if ! grep -q 'themes/tasa.css' src/app.html 2>/dev/null; then
        sed -i 's|<link rel="stylesheet" href="/static/custom.css"|<link rel="stylesheet" href="/themes/tasa.css" crossorigin="use-credentials" />\n\t\t<link rel="stylesheet" href="/static/custom.css"|' src/app.html
        ok "src/app.html (tasa.css link added)"
    else
        ok "src/app.html (tasa.css link already present)"
    fi
    ok "src/app.html"

    # --- site.webmanifest ---
    sed -i "s/\"name\": \".*\"/\"name\": \"$NEW_NAME\"/" static/static/site.webmanifest
    sed -i "s/\"short_name\": \".*\"/\"short_name\": \"TASA\"/" static/static/site.webmanifest
    ok "static/static/site.webmanifest"

    # --- opensearch.xml ---
    if [ -f static/opensearch.xml ]; then
        sed -i "s/$OLD_NAME/$NEW_NAME/g" static/opensearch.xml
        ok "static/opensearch.xml"
    fi

    # --- Backend main.py ---
    sed -i "s/title='$OLD_NAME'/title='$NEW_NAME'/" backend/open_webui/main.py
    sed -i "s/$OLD_NAME v{VERSION}/$NEW_NAME v{VERSION}/" backend/open_webui/main.py
    ok "backend/open_webui/main.py"

    # --- Backend constants.py ---
    sed -i "s/'$OLD_NAME: Server Connection Error'/'$NEW_NAME: Server Connection Error'/g" backend/open_webui/constants.py
    ok "backend/open_webui/constants.py"

    # --- Backend __init__.py ---
    sed -i "s/$OLD_NAME version:/$NEW_NAME version:/" backend/open_webui/__init__.py
    ok "backend/open_webui/__init__.py"

    # --- Backend events.py ---
    sed -i "s/'$OLD_NAME'/'$NEW_NAME'/g" backend/open_webui/events.py
    ok "backend/open_webui/events.py"

    # --- Backend oauth.py ---
    sed -i "s/client_name='$OLD_NAME'/client_name='$NEW_NAME'/" backend/open_webui/utils/oauth.py
    ok "backend/open_webui/utils/oauth.py"

    # --- Backend openai.py ---
    sed -i "s/'X-Title': '$OLD_NAME'/'X-Title': '$NEW_NAME'/" backend/open_webui/routers/openai.py
    sed -i "s/'$OLD_NAME: Server Connection Error'/'$NEW_NAME: Server Connection Error'/g" backend/open_webui/routers/openai.py
    ok "backend/open_webui/routers/openai.py"

    # --- Backend audio.py ---
    sed -i "s/'$OLD_NAME: Server Connection Error'/'$NEW_NAME: Server Connection Error'/g" backend/open_webui/routers/audio.py
    ok "backend/open_webui/routers/audio.py"

    # --- Backend memory.py ---
    sed -i "s/You are $OLD_NAME's/You are $NEW_NAME's/" backend/open_webui/utils/memory.py
    ok "backend/open_webui/utils/memory.py"

    # --- Backend automations.py ---
    sed -i "s/'$OLD_NAME'/'$NEW_NAME'/g" backend/open_webui/utils/automations.py
    ok "backend/open_webui/utils/automations.py"

    # --- Svelte frontend files ---
    local svelte_count
    svelte_count=$(find src -name "*.svelte" -exec grep -l "$OLD_NAME" {} \; 2>/dev/null | wc -l)
    if [ "$svelte_count" -gt 0 ]; then
        find src -name "*.svelte" -exec grep -l "$OLD_NAME" {} \; | while read -r f; do
            sed -i "s/$OLD_NAME/$NEW_NAME/g" "$f"
        done
        ok "Svelte files ($svelte_count files updated)"
    else
        ok "Svelte files (already branded)"
    fi

    # --- i18n translation files ---
    local i18n_count
    i18n_count=$(find src/lib/i18n/locales -name "*.json" -exec grep -l "$OLD_NAME" {} \; 2>/dev/null | wc -l)
    if [ "$i18n_count" -gt 0 ]; then
        find src/lib/i18n/locales -name "*.json" -exec grep -l "$OLD_NAME" {} \; | while read -r f; do
            sed -i "s/$OLD_NAME/$NEW_NAME/g" "$f"
        done
        ok "i18n translation files ($i18n_count files updated)"
    else
        ok "i18n translation files (already branded)"
    fi
}

# =============================================================================
# Step 3: Patch running Docker container (optional)
# =============================================================================
patch_container() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        warn "Container '$CONTAINER_NAME' is not running. Skipping container patch."
        return
    fi

    log "Patching running container '$CONTAINER_NAME'..."


    # Copy icon files into container build dir
    docker cp "$FAVICON_DIR/android-chrome-192x192.png" "$CONTAINER_NAME:/app/build/static/web-app-manifest-192x192.png" || true
    docker cp "$FAVICON_DIR/android-chrome-512x512.png" "$CONTAINER_NAME:/app/build/static/web-app-manifest-512x512.png" || true
    docker cp "$FAVICON_DIR/apple-touch-icon.png"       "$CONTAINER_NAME:/app/build/static/apple-touch-icon.png" || true
    docker cp "$FAVICON_DIR/favicon.ico"                "$CONTAINER_NAME:/app/build/static/favicon.ico" || true
    docker cp "$FAVICON_DIR/android-chrome-192x192.png" "$CONTAINER_NAME:/app/build/static/favicon.png" || true
    docker cp "$FAVICON_DIR/android-chrome-192x192.png" "$CONTAINER_NAME:/app/build/static/favicon-96x96.png" || true
    docker cp "$FAVICON_DIR/android-chrome-512x512.png" "$CONTAINER_NAME:/app/build/static/favicon-dark.png" || true
    docker cp "$FAVICON_DIR/android-chrome-512x512.png" "$CONTAINER_NAME:/app/build/static/splash.png" || true
    docker cp "$FAVICON_DIR/android-chrome-512x512.png" "$CONTAINER_NAME:/app/build/static/splash-dark.png" || true
    docker cp "$FAVICON_DIR/favicon-32x32.png"          "$CONTAINER_NAME:/app/build/static/favicon-32x32.png" || true
    ok "Icons copied into container"

    # Patch compiled JS bundles (replace brand name in minified code)
    docker exec "$CONTAINER_NAME" find /app/build -type f \( -name "*.js" -o -name "*.html" -o -name "*.json" \) \
        -exec sed -i "s/$OLD_NAME/$NEW_NAME/g" {} + 2>/dev/null || true

    # Patch source maps too
    docker exec "$CONTAINER_NAME" find /app/build -name "*.js.map" \
        -exec sed -i "s/$OLD_NAME/$NEW_NAME/g" {} + 2>/dev/null || true

    # Patch opensearch.xml in build
    docker exec "$CONTAINER_NAME" sed -i "s/$OLD_NAME/$NEW_NAME/g" /app/build/opensearch.xml 2>/dev/null || true

    # Patch site.webmanifest in build
    docker exec "$CONTAINER_NAME" sed -i "s/$OLD_NAME/$NEW_NAME/g" /app/build/static/site.webmanifest 2>/dev/null || true

    # Patch backend Python files inside container
    docker exec "$CONTAINER_NAME" sed -i \
        "s|WEBUI_NAME = os.getenv('WEBUI_NAME', '.*')|WEBUI_NAME = os.getenv('WEBUI_NAME', '$NEW_NAME')|" \
        /app/backend/open_webui/env.py 2>/dev/null || true
    docker exec "$CONTAINER_NAME" sed -i \
        "s|if WEBUI_NAME != '.*':|if WEBUI_NAME != '$NEW_NAME':|" \
        /app/backend/open_webui/env.py 2>/dev/null || true
    docker exec "$CONTAINER_NAME" sed -i \
        "s|WEBUI_NAME += ' (.*)'|WEBUI_NAME += ' ($NEW_NAME)'|" \
        /app/backend/open_webui/env.py 2>/dev/null || true
    docker exec "$CONTAINER_NAME" sed -i "s/title='$OLD_NAME'/title='$NEW_NAME'/" /app/backend/open_webui/main.py 2>/dev/null || true
    docker exec "$CONTAINER_NAME" sed -i "s/'$OLD_NAME: Server Connection Error'/'$NEW_NAME: Server Connection Error'/g" /app/backend/open_webui/constants.py 2>/dev/null || true
    docker exec "$CONTAINER_NAME" sed -i "s/'$OLD_NAME'/'$NEW_NAME'/g" /app/backend/open_webui/events.py 2>/dev/null || true
    docker exec "$CONTAINER_NAME" sed -i "s/client_name='$OLD_NAME'/client_name='$NEW_NAME'/" /app/backend/open_webui/utils/oauth.py 2>/dev/null || true
    docker exec "$CONTAINER_NAME" sed -i "s/'X-Title': '$OLD_NAME'/'X-Title': '$NEW_NAME'/" /app/backend/open_webui/routers/openai.py 2>/dev/null || true
    docker exec "$CONTAINER_NAME" sed -i "s/'$OLD_NAME: Server Connection Error'/'$NEW_NAME: Server Connection Error'/g" /app/backend/open_webui/routers/openai.py 2>/dev/null || true
    docker exec "$CONTAINER_NAME" sed -i "s/'$OLD_NAME: Server Connection Error'/'$NEW_NAME: Server Connection Error'/g" /app/backend/open_webui/routers/audio.py 2>/dev/null || true

    # Verify
    local remaining
    remaining=$(docker exec "$CONTAINER_NAME" grep -rl "$OLD_NAME" /app/build/ 2>/dev/null | wc -l || true)
    remaining=$(echo "$remaining" | tr -d '[:space:]')
    if [ "$remaining" -eq 0 ]; then
        ok "Container patched — zero '$OLD_NAME' references remain in build dir"
    else
        warn "Container patched but $remaining files still contain '$OLD_NAME' (likely source maps)"
    fi
}

# =============================================================================
# Step 4: Rebuild Docker image (optional, permanent solution)
# =============================================================================
rebuild_image() {
    log "Rebuilding Docker image (this may take several minutes)..."
    docker compose build open-webui
    ok "Docker image rebuilt"

    log "Restarting container..."
    docker compose up -d open-webui
    ok "Container restarted with new image"
}

# =============================================================================
# Step 4.5: Re-apply billing integration patches
# These modifications to upstream files get lost during git pull/rebase.
# New files (models, routers, utils) survive since they don't conflict.
# =============================================================================
patch_billing_integration() {
    log "Re-applying billing/subscription integration patches..."

    # --- backend/open_webui/env.py: SHKeeper env vars ---
    if ! grep -q "SHKEEPER_API_URL" backend/open_webui/env.py 2>/dev/null; then
        cat >> backend/open_webui/env.py << 'BILLING_ENV'


####################################
# SHKeeper Payment Gateway
####################################

SHKEEPER_API_URL = os.getenv('SHKEEPER_API_URL', 'http://host.docker.internal:5555')
SHKEEPER_API_KEY = os.getenv('SHKEEPER_API_KEY', '')
SHKEEPER_WEBHOOK_SECRET = os.getenv('SHKEEPER_WEBHOOK_SECRET', '')
BILLING_ENV
        ok "backend/open_webui/env.py (SHKeeper env vars)"
    else
        ok "backend/open_webui/env.py (SHKeeper env vars already present)"
    fi

    # --- backend/open_webui/main.py: billing router import ---
    if ! grep -q "billing" backend/open_webui/main.py 2>/dev/null; then
        # Add billing to router imports
        sed -i 's/from open_webui.routers import (/from open_webui.routers import (\n    billing,/' backend/open_webui/main.py
        # Add billing router registration after calendar
        sed -i '/app.include_router(calendar/a app.include_router(billing.router, prefix='"'"'/api/v1/billing'"'"', tags=['"'"'billing'"'"'])' backend/open_webui/main.py
        ok "backend/open_webui/main.py (billing router)"
    else
        ok "backend/open_webui/main.py (billing router already present)"
    fi

    # --- backend/open_webui/main.py: billing poller task ---
    if ! grep -q "poll_pending_invoices" backend/open_webui/main.py 2>/dev/null; then
        sed -i '/asyncio.create_task(scheduler_worker_loop/i\    # Billing: poll SHKeeper for pending invoice statuses every 30s\n    from open_webui.billing_poller import poll_pending_invoices\n    asyncio.create_task(poll_pending_invoices())\n' backend/open_webui/main.py
        ok "backend/open_webui/main.py (billing poller)"
    else
        ok "backend/open_webui/main.py (billing poller already present)"
    fi

    # --- docker-compose.yaml: SHKeeper env vars ---
    if ! grep -q "SHKEEPER_API_KEY" docker-compose.yaml 2>/dev/null; then
        # Add SHKeeper env vars after WEBUI_SECRET_KEY
        sed -i "/WEBUI_SECRET_KEY/a\\      # SHKeeper payment gateway\\n      - 'SHKEEPER_API_URL=http://host.docker.internal:5555'\\n      - 'SHKEEPER_API_KEY=\${SHKEEPER_API_KEY}'\\n      - 'SHKEEPER_WEBHOOK_SECRET=\${SHKEEPER_WEBHOOK_SECRET}'" docker-compose.yaml
        ok "docker-compose.yaml (SHKeeper env vars)"
    else
        ok "docker-compose.yaml (SHKeeper env vars already present)"
    fi

    # --- Sidebar: billing menu item ---
    if ! grep -q "billing" src/lib/components/layout/Sidebar.svelte 2>/dev/null; then
        # Add billing to menu items
        sed -i "s/playground: { label: 'Playground'/playground: { label: 'Playground' },\n\t\t\tbilling: { label: 'Subscription', href: '\/billing', iconType: 'billing' }/" src/lib/components/layout/Sidebar.svelte
        # Add billing visibility
        sed -i "s/case 'playground':/case 'billing':\n\t\t\t\treturn true;\n\t\t\tcase 'playground':/" src/lib/components/layout/Sidebar.svelte
        ok "src/lib/components/layout/Sidebar.svelte (billing menu)"
    else
        ok "src/lib/components/layout/Sidebar.svelte (billing menu already present)"
    fi
}

# =============================================================================
# Step 5: Apply TASA theme patches
# These modifications add the warm orange/amber TASA colour theme to the UI.
# Survives upstream updates when this script is re-run.
# =============================================================================
patch_tasa_theme() {
    log "Applying TASA theme patches..."

    # --- Fix upstream bug: space in @apply dark: variant ---
    if grep -q 'dark: !bg-black' src/app.css 2>/dev/null; then
        sed -i 's/@apply !bg-white dark: !bg-black !border-none;/@apply !bg-white dark:\!bg-black !border-none;/' src/app.css
        ok "src/app.css (fixed dark: variant bug)"
    else
        ok "src/app.css (dark: variant already fixed)"
    fi

    # --- src/app.html: default theme to 'tasa' ---
    if ! grep -q "localStorage.theme = 'tasa'" src/app.html 2>/dev/null; then
        sed -i "s/localStorage.theme = 'system';/localStorage.theme = 'tasa';/" src/app.html
        ok "src/app.html (default theme -> tasa)"
    else
        ok "src/app.html (default theme already tasa)"
    fi

    # --- src/app.html: add TASA theme handler on initial load ---
    if ! grep -q "localStorage.theme === 'tasa'" src/app.html 2>/dev/null; then
        # Insert TASA block after the 'light' block and before the 'her' block
        sed -i "/localStorage.theme === 'light'/,/^			} else if.*localStorage.theme === 'her'/{
            /^			} else if.*localStorage.theme === 'her'/i\\
\t\t\t} else if (localStorage.theme === 'tasa') {\\
\t\t\t\tdocument.documentElement.classList.add('light');\\
\t\t\t\tdocument.documentElement.classList.add('tasa');\\
\t\t\t\tmetaThemeColorTag.setAttribute('content', '#f34607');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-50', '#fefaf7');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-100', '#fff0e8');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-200', '#f0c8b0');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-300', '#e0b09a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-400', '#8a6550');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-500', '#6b4a3a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-600', '#5a3a2a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-700', '#4a2a1a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-800', '#3a1a0a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-850', '#2c1810');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-900', '#1a0e08');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-950', '#0d0704');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-blue-400', '#ff6b3a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-blue-500', '#f34607');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-blue-600', '#f34607');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-blue-700', '#c73a06');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-emerald-500', '#ff6b3a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-emerald-600', '#f34607');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-emerald-700', '#c73a06');
        }" src/app.html
        ok "src/app.html (TASA initial-load handler)"
    else
        ok "src/app.html (TASA initial-load handler already present)"
    fi

    # --- src/lib/components/chat/Settings/General.svelte: add 'tasa' to themes array ---
    if ! grep -q "'tasa'" src/lib/components/chat/Settings/General.svelte 2>/dev/null; then
        sed -i "s/let themes = \['dark', 'light', 'oled-dark'\];/let themes = ['dark', 'light', 'oled-dark', 'tasa'];/" src/lib/components/chat/Settings/General.svelte
        ok "General.svelte (themes array)"
    else
        ok "General.svelte (themes array already includes tasa)"
    fi

    # --- General.svelte: add TASA option to theme selector dropdown ---
    if ! grep -q 'value="tasa"' src/lib/components/chat/Settings/General.svelte 2>/dev/null; then
        sed -i "/<option value=\"light\">/a\\\\t\\t\\t\\t\\t\\t\\t\\t<option value=\"tasa\">🔥 \${\$i18n.t('TASA')}</option>" src/lib/components/chat/Settings/General.svelte
        ok "General.svelte (theme selector dropdown)"
    else
        ok "General.svelte (theme selector already includes TASA)"
    fi

    # --- General.svelte: handle tasa in applyTheme ---
    if ! grep -q "_theme === 'tasa'" src/lib/components/chat/Settings/General.svelte 2>/dev/null; then
        # Map tasa to light base theme
        sed -i "s/_theme === 'her' ? 'light' : _theme/_theme === 'her' || _theme === 'tasa' ? 'light' : _theme/" src/lib/components/chat/Settings/General.svelte
        # Add tasa meta theme color
        sed -i "/_theme === 'her'/{
            n
            /#983724/a\\
\t\t\t\t\t\t\t\t\t: _theme === 'tasa'\\
\t\t\t\t\t\t\t\t\t\t? '#f34607'
        }" src/lib/components/chat/Settings/General.svelte
        # Add tasa class + setProperty block after oled block
        sed -i "/document.documentElement.classList.add('dark');$/{
            N
            /\n$/a\\
\\
\t\tif (_theme === 'tasa') {\\
\t\t\tdocument.documentElement.classList.add('tasa');\\
\t\t\tdocument.documentElement.style.setProperty('--color-gray-50', '#fefaf7');\\
\t\t\tdocument.documentElement.style.setProperty('--color-gray-100', '#fff0e8');\\
\t\t\tdocument.documentElement.style.setProperty('--color-gray-200', '#f0c8b0');\\
\t\t\tdocument.documentElement.style.setProperty('--color-gray-300', '#e0b09a');\\
\t\t\tdocument.documentElement.style.setProperty('--color-gray-400', '#8a6550');\\
\t\t\tdocument.documentElement.style.setProperty('--color-gray-500', '#6b4a3a');\\
\t\t\tdocument.documentElement.style.setProperty('--color-gray-600', '#5a3a2a');\\
\t\t\tdocument.documentElement.style.setProperty('--color-gray-700', '#4a2a1a');\\
\t\t\tdocument.documentElement.style.setProperty('--color-gray-800', '#3a1a0a');\\
\t\t\tdocument.documentElement.style.setProperty('--color-gray-850', '#2c1810');\\
\t\t\tdocument.documentElement.style.setProperty('--color-gray-900', '#1a0e08');\\
\t\t\tdocument.documentElement.style.setProperty('--color-gray-950', '#0d0704');\\
\t\t\tdocument.documentElement.style.setProperty('--color-blue-400', '#ff6b3a');\\
\t\t\tdocument.documentElement.style.setProperty('--color-blue-500', '#f34607');\\
\t\t\tdocument.documentElement.style.setProperty('--color-blue-600', '#f34607');\\
\t\t\tdocument.documentElement.style.setProperty('--color-blue-700', '#c73a06');\\
\t\t\tdocument.documentElement.style.setProperty('--color-emerald-500', '#ff6b3a');\\
\t\t\tdocument.documentElement.style.setProperty('--color-emerald-600', '#f34607');\\
\t\t\tdocument.documentElement.style.setProperty('--color-emerald-700', '#c73a06');\\
\t\t} else {\\
\t\t\t['--color-gray-50','--color-gray-100','--color-gray-200','--color-gray-300','--color-gray-400','--color-gray-500','--color-gray-600','--color-gray-700','--color-gray-800','--color-gray-850','--color-gray-900','--color-gray-950','--color-blue-400','--color-blue-500','--color-blue-600','--color-blue-700','--color-emerald-500','--color-emerald-600','--color-emerald-700'].forEach((prop) => document.documentElement.style.removeProperty(prop));\\
\t\t}
        }" src/lib/components/chat/Settings/General.svelte
        # Default theme to tasa
        sed -i "s/localStorage.theme ?? 'system'/localStorage.theme ?? 'tasa'/" src/lib/components/chat/Settings/General.svelte
        ok "General.svelte (applyTheme TASA handling)"
    else
        ok "General.svelte (applyTheme TASA handling already present)"
    fi

    # --- src/routes/+layout.svelte: TASA in desktop event handler ---
    if ! grep -q "newTheme === 'tasa'" src/routes/+layout.svelte 2>/dev/null; then
        sed -i "s/newTheme === 'her' ? 'light' : newTheme/newTheme === 'her' || newTheme === 'tasa' ? 'light' : newTheme/" src/routes/+layout.svelte
        sed -i "s/const themes = \['dark', 'light', 'oled-dark'\];/const themes = ['dark', 'light', 'oled-dark', 'tasa'];/" src/routes/+layout.svelte
        sed -i "/newTheme === 'tasa'.*classList.add('tasa')/!{
            /themeToApply.split.*forEach.*classList.add/{
                N
                /if (newTheme === 'tasa')/!a\\
\t\t\tif (newTheme === 'tasa') {\\
\t\t\t\tdocument.documentElement.classList.add('tasa');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-50', '#fefaf7');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-100', '#fff0e8');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-200', '#f0c8b0');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-300', '#e0b09a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-400', '#8a6550');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-500', '#6b4a3a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-600', '#5a3a2a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-700', '#4a2a1a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-800', '#3a1a0a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-850', '#2c1810');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-900', '#1a0e08');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-gray-950', '#0d0704');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-blue-400', '#ff6b3a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-blue-500', '#f34607');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-blue-600', '#f34607');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-blue-700', '#c73a06');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-emerald-500', '#ff6b3a');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-emerald-600', '#f34607');\\
\t\t\t\tdocument.documentElement.style.setProperty('--color-emerald-700', '#c73a06');\\
\t\t\t} else {\\
\t\t\t\t['--color-gray-50','--color-gray-100','--color-gray-200','--color-gray-300','--color-gray-400','--color-gray-500','--color-gray-600','--color-gray-700','--color-gray-800','--color-gray-850','--color-gray-900','--color-gray-950','--color-blue-400','--color-blue-500','--color-blue-600','--color-blue-700','--color-emerald-500','--color-emerald-600','--color-emerald-700'].forEach((prop) => document.documentElement.style.removeProperty(prop));\\
\t\t\t}
            }
        }" src/routes/+layout.svelte
        ok "src/routes/+layout.svelte (desktop event TASA handling)"
    else
        ok "src/routes/+layout.svelte (desktop event TASA handling already present)"
    fi

    # --- static/static/custom.css: supplementary TASA CSS ---
    if ! grep -q 'html.tasa' static/static/custom.css 2>/dev/null; then
        cat > static/static/custom.css << 'CUSTOM_CSS'
/*
 * TASA WebUI Theme — warm orange/amber light theme
 * Based on the Full Armour (928) colour palette.
 * Applied when the <html> element has class="tasa".
 */

html.tasa {
	background-color: #fefaf7 !important;
	color: #2c1810 !important;
}

html.tasa body {
	background-color: #fefaf7 !important;
	color: #2c1810 !important;
}

html.tasa #sidebar {
	background-color: #fff5ee !important;
	border-color: #f0c8b0 !important;
}

html.tasa #chat-input,
html.tasa #chat-input-container {
	background-color: #fffaf6 !important;
}

html.tasa button.bg-black,
html.tasa .bg-black.text-white {
	background-color: #f34607 !important;
}

html.tasa button.bg-black:hover,
html.tasa .bg-black.text-white:hover {
	background-color: #c73a06 !important;
}

html.tasa button.bg-black > * {
	fill: #ffffff !important;
}

html.tasa .bg-emerald-600 {
	background-color: #f34607 !important;
}

html.tasa .bg-emerald-600:hover {
	background-color: #c73a06 !important;
}

html.tasa input[type='checkbox']:checked {
	background-color: #f34607 !important;
	border-color: #f34607 !important;
}

html.tasa a {
	color: #c73a06 !important;
}

html.tasa a:hover {
	color: #f34607 !important;
}

html.tasa ::-webkit-scrollbar-thumb {
	background-color: rgba(243, 70, 7, 0.2) !important;
	border-color: #fefaf7 !important;
}

html.tasa pre,
html.tasa code {
	background-color: #fff0e8 !important;
}

html.tasa input[type='text'],
html.tasa input[type='email'],
html.tasa input[type='password'],
html.tasa input[type='search'],
html.tasa input[type='url'],
html.tasa input[type='number'],
html.tasa textarea,
html.tasa select {
	background-color: #fffaf6 !important;
	border-color: #f0c8b0 !important;
}

html.tasa input:focus,
html.tasa textarea:focus,
html.tasa select:focus {
	border-color: #ff6b3a !important;
	box-shadow: 0 0 0 2px rgba(243, 70, 7, 0.15) !important;
}

html.tasa input::placeholder,
html.tasa textarea::placeholder {
	color: #8a6550 !important;
	opacity: 0.7;
}

html.tasa hr {
	border-color: #f0c8b0 !important;
}

html.tasa ::selection {
	background-color: rgba(243, 70, 7, 0.2) !important;
	color: #2c1810 !important;
}

html.tasa #splash-screen {
	background: #fefaf7 !important;
}

html.tasa .shimmer {
	background: linear-gradient(110deg, #8a6550 0%, #8a6550 43%, #e0b09a 50%, #8a6550 57%, #8a6550 100%) !important;
	color: #8a6550 !important;
}

html.tasa .tippy-box[data-theme~='dark'] {
	background-color: #2c1810 !important;
	border-color: #4a2a1a !important;
}
CUSTOM_CSS
        ok "static/static/custom.css (TASA supplementary CSS)"
    else
        ok "static/static/custom.css (TASA CSS already present)"
    fi
}

# =============================================================================
# Main
# =============================================================================
main() {
    echo ""
    echo "============================================"
    echo "  TASA WebUI Rebrand Script"
    echo "  Replacing '$OLD_NAME' -> '$NEW_NAME'"
    echo "============================================"
    echo ""

    if [ "$THEME_ONLY" = true ]; then
        echo "  [Theme-only mode: skipping icon/branding replacement per license]"
        echo ""
        check_prerequisites
        patch_billing_integration
        patch_tasa_theme
    else
        check_prerequisites
        replace_host_icons
        replace_host_branding
        patch_billing_integration
        patch_tasa_theme
    fi

    if [ "$REBUILD_IMAGE" = true ]; then
        rebuild_image
    elif [ "$PATCH_CONTAINER" = true ]; then
        patch_container
        if [ "$RESTART_CONTAINER" = true ]; then
            log "Restarting container..."
            docker restart "$CONTAINER_NAME"
            ok "Container restarted"
        fi
    fi

    echo ""
    ok "Rebranding complete!"
    echo ""
    echo "Next steps:"
    if [ "$PATCH_CONTAINER" = false ] && [ "$REBUILD_IMAGE" = false ]; then
        echo "  - Run './tasa-rebrand.sh --container --restart' to patch the running container"
        echo "  - Or run './tasa-rebrand.sh --rebuild' for a permanent Docker rebuild"
    fi
    echo "  - Hard-refresh your browser (Ctrl+Shift+R) to see changes"
    echo ""
}

main
