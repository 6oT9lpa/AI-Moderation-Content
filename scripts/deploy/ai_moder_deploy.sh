#!/usr/bin/env bash
set -euo pipefail

ARCHIVE="${ARCHIVE:-/tmp/ai-moder-release.tar.gz}"
ROOT_TMP="${ROOT_TMP:-/root/tmp}"
APP_DIR="${APP_DIR:-/opt/ai-moder}"
BACKUP_DIR="${BACKUP_DIR:-/opt}"
BACKUP="$BACKUP_DIR/ai-moder.backup-$(date +%Y%m%d%H%M%S).tgz"
ROOT_ARCHIVE="$ROOT_TMP/ai-moder-release.tar.gz"
ENV_FILE="${ENV_FILE:-}"
SERVICES=(${SERVICES:-ai-moder.service})

log() {
    printf '[ai-moder-deploy] %s\n' "$*"
}

mkdir -p "$ROOT_TMP"
id -u ai-moder >/dev/null 2>&1 || useradd --system --create-home --home-dir /opt/ai-moder --shell /usr/sbin/nologin ai-moder

log "Copy archive to root tmp..."
cp "$ARCHIVE" "$ROOT_ARCHIVE"

if [ -d "$APP_DIR" ]; then
    log "Create backup..."
    tar -C "$(dirname "$APP_DIR")" -czf "$BACKUP" "$(basename "$APP_DIR")"
else
    log "App directory does not exist yet, backup skipped."
fi

log "Stop services..."
for service in "${SERVICES[@]}"; do
    systemctl stop "$service" || true
done

log "Extract new files over existing project..."
mkdir -p "$APP_DIR"
tar -xzf "$ROOT_ARCHIVE" -C "$APP_DIR"

if [ -n "$ENV_FILE" ]; then
    install -o ai-moder -g ai-moder -m 600 "$ENV_FILE" "$APP_DIR/.env"
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
install -o root -g root -m 644 "$APP_DIR/scripts/deploy/ai-moder.service" /etc/systemd/system/ai-moder.service
mkdir -p "$APP_DIR/logs"
chown -R ai-moder:ai-moder "$APP_DIR"
systemctl daemon-reload

log "Start services..."
for service in "${SERVICES[@]}"; do
    systemctl start "$service"
done

log "Status:"
for service in "${SERVICES[@]}"; do
    systemctl is-active "$service"
done

log "Backup created: ${BACKUP:-none}"
log "Done"
