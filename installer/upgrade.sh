#!/usr/bin/env bash
set -Eeuo pipefail
[[ $(id -u) -eq 0 ]] || { echo 'Must run as root' >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP=/opt/dockerforge/backend
[[ -f "$APP/app/core.py" && -f /etc/dockerforge/dockerforge.env ]] || { echo 'Existing Task 1-5 foundation not detected; refusing update' >&2; exit 1; }
command -v python3 >/dev/null
command -v systemctl >/dev/null
systemctl is-active --quiet dockerforge || { echo 'DockerForge is not active; inspect service first' >&2; exit 1; }
NEW_VERSION=$(grep '^version = ' "$ROOT/backend/pyproject.toml" | cut -d '"' -f 2)
[[ $NEW_VERSION = 0.7.0 ]] || { echo 'Unexpected package version' >&2; exit 1; }
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=/root/dockerforge-upgrade-backup-$STAMP
mkdir -m 0700 "$BACKUP"
cp -a "$APP" "$BACKUP/backend"
cp -a /etc/systemd/system/dockerforge.service "$BACKUP/dockerforge.service"
cp -a /etc/dockerforge "$BACKUP/etc-dockerforge"
chmod -R go-rwx "$BACKUP/etc-dockerforge"
# Compose stack configuration is user-managed and must be preserved.
if [[ -d /var/lib/dockerforge/stacks ]]; then cp -a /var/lib/dockerforge/stacks "$BACKUP/stacks"; fi
if [[ -f /etc/systemd/system/dockerforge-metrics.service ]]; then cp -a /etc/systemd/system/dockerforge-metrics.service "$BACKUP/dockerforge-metrics.service"; fi
# SQLite online backup, not an unsafe live file copy.
APP_BACKUP="$BACKUP/dockerforge.db"
export APP_BACKUP
/opt/dockerforge/venv/bin/python - <<'PY'
import os,sqlite3
from pathlib import Path
source='/var/lib/dockerforge/dockerforge.db'
if not Path(source).is_file():raise SystemExit('Database missing: refusing upgrade')
with sqlite3.connect(source) as src, sqlite3.connect(os.environ['APP_BACKUP']) as dst:src.backup(dst)
PY
chmod 0600 "$APP_BACKUP"
# Back up alert state/rules if re-running this or a future upgrade.
for alert_file in alert-rules.json alert-state.json; do
  if [[ -f "/var/lib/dockerforge/$alert_file" ]]; then
    cp -a "/var/lib/dockerforge/$alert_file" "$BACKUP/$alert_file"
  fi
done
# Preserve optional v0.7.0 historical metrics when upgrading again.
if [[ -f /var/lib/dockerforge/metrics.db ]]; then
  METRICS_BACKUP="$BACKUP/metrics.db"; export METRICS_BACKUP
  /opt/dockerforge/venv/bin/python - <<'PYMETRICS'
import os,sqlite3
with sqlite3.connect('/var/lib/dockerforge/metrics.db') as src, sqlite3.connect(os.environ['METRICS_BACKUP']) as dst:src.backup(dst)
PYMETRICS
  chmod 0600 "$METRICS_BACKUP"
fi
STAGING=/opt/dockerforge/.v0700-staging-$STAMP
mkdir -m 0755 "$STAGING"
cp -a "$ROOT/backend/." "$STAGING/"
/opt/dockerforge/venv/bin/python -m compileall -q "$STAGING/app"
rollback() {
  echo 'Upgrade failed, restoring previous backend...' >&2
  if [[ -d "$BACKUP/backend" ]]; then
    rm -rf "$APP"
    cp -a "$BACKUP/backend" "$APP"
  fi
  systemctl stop dockerforge-metrics 2>/dev/null || true
  if [[ -f "$BACKUP/dockerforge-metrics.service" ]]; then cp -a "$BACKUP/dockerforge-metrics.service" /etc/systemd/system/dockerforge-metrics.service; else rm -f /etc/systemd/system/dockerforge-metrics.service; fi
  systemctl daemon-reload
  systemctl restart dockerforge || true
  systemctl enable --now dockerforge-metrics 2>/dev/null || true
  echo "Backup retained: $BACKUP" >&2
}
trap rollback ERR
systemctl stop dockerforge-metrics 2>/dev/null || true
systemctl stop dockerforge
# Swap backend; existing venv, DB, user, settings, certificate and service remain untouched.
rm -rf "$APP"
mv "$STAGING" "$APP"
install -m 0644 "$ROOT/systemd/dockerforge-metrics.service" /etc/systemd/system/dockerforge-metrics.service
install -m 0750 "$ROOT/scripts/backup-manager.py" /usr/local/sbin/dockerforge-backup
install -m 0750 "$ROOT/scripts/volume-backup.py" /usr/local/sbin/dockerforge-volume-backup
install -m 0644 "$ROOT/scripts/volume-backup.py" /usr/local/sbin/volume-backup.py
install -m 0750 "$ROOT/scripts/bind-backup.py" /usr/local/sbin/dockerforge-bind-backup
install -m 0750 "$ROOT/scripts/data-backup-job.py" /usr/local/sbin/dockerforge-data-backup
install -m 0644 "$ROOT/systemd/dockerforge-data-backup.service" /etc/systemd/system/dockerforge-data-backup.service
install -m 0644 "$ROOT/systemd/dockerforge-data-backup.timer" /etc/systemd/system/dockerforge-data-backup.timer
if [[ ! -e /etc/dockerforge/data-backup.json ]]; then install -m 0600 "$ROOT/data-backup.example.json" /etc/dockerforge/data-backup.json; fi
install -m 0644 "$ROOT/systemd/dockerforge-backup.service" /etc/systemd/system/dockerforge-backup.service
install -m 0644 "$ROOT/systemd/dockerforge-backup.timer" /etc/systemd/system/dockerforge-backup.timer
systemctl daemon-reload
systemctl start dockerforge
systemctl enable --now dockerforge-metrics
for i in {1..15}; do
 if curl -kfsS --silent --max-time 2 https://127.0.0.1:9443/health 2>/dev/null | grep -q '"status":"ok"'; then
   systemctl is-active --quiet dockerforge-metrics || { echo "Collector inactive" >&2; false; }
   trap - ERR
   echo "DockerForge upgraded to v0.7.0 ($NEW_VERSION). Backup: $BACKUP"
   echo 'Preview: security review required; existing backup timer settings retained; keep port 9443 restricted.'
   exit 0
 fi
 sleep 1
done
false
