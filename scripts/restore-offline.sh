#!/usr/bin/env bash
set -Eeuo pipefail
[[ $(id -u) -eq 0 && $# -eq 2 && $2 == --confirm-offline-restore ]] || { echo 'Usage as root: restore-offline.sh BACKUP_DIRECTORY --confirm-offline-restore' >&2; exit 2; }
DIR="$(realpath -e -- "$1")"
"$(dirname "$0")/verify-backup.sh" "$DIR"
[[ -f "$DIR/etc-dockerforge/dockerforge.env" ]] || { echo 'Backup has no configuration; refusing restore' >&2; exit 1; }
[[ -f "$DIR/dockerforge.service" ]] || { echo 'Backup has no service unit; refusing restore' >&2; exit 1; }
# Explicit downtime and a rollback checkpoint are mandatory.
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
CHECKPOINT=/root/dockerforge-pre-restore-$STAMP
mkdir -m 0700 "$CHECKPOINT"
cp -a /opt/dockerforge/backend "$CHECKPOINT/backend"
cp -a /etc/dockerforge "$CHECKPOINT/etc-dockerforge"
systemctl stop dockerforge-metrics 2>/dev/null || true
systemctl stop dockerforge
cp -a /var/lib/dockerforge/dockerforge.db "$CHECKPOINT/dockerforge.db"
if [[ -f /var/lib/dockerforge/metrics.db ]]; then cp -a /var/lib/dockerforge/metrics.db "$CHECKPOINT/metrics.db"; fi
if [[ -d /var/lib/dockerforge/stacks ]]; then cp -a /var/lib/dockerforge/stacks "$CHECKPOINT/stacks"; fi
cp -a /etc/systemd/system/dockerforge.service "$CHECKPOINT/dockerforge.service"
if [[ -f /etc/systemd/system/dockerforge-metrics.service ]]; then cp -a /etc/systemd/system/dockerforge-metrics.service "$CHECKPOINT/dockerforge-metrics.service"; fi
# Replace, not overlay: files added by the newer version must not survive the restore.
rm -rf /opt/dockerforge/backend
mkdir -m 0755 /opt/dockerforge/backend
cp -a "$DIR/backend/." /opt/dockerforge/backend/
install -m 0600 -o dockerforge -g dockerforge "$DIR/dockerforge.db" /var/lib/dockerforge/dockerforge.db
if [[ -f "$DIR/metrics.db" ]]; then install -m 0600 -o dockerforge -g dockerforge "$DIR/metrics.db" /var/lib/dockerforge/metrics.db; fi
cp -a "$DIR/etc-dockerforge/." /etc/dockerforge/
if [[ -d "$DIR/stacks" ]]; then mkdir -p /var/lib/dockerforge/stacks; cp -a "$DIR/stacks/." /var/lib/dockerforge/stacks/; fi
cp -a "$DIR/dockerforge.service" /etc/systemd/system/dockerforge.service
if [[ -f "$DIR/dockerforge-metrics.service" ]]; then cp -a "$DIR/dockerforge-metrics.service" /etc/systemd/system/dockerforge-metrics.service; fi
for x in alert-rules.json alert-state.json; do if [[ -f "$DIR/$x" ]]; then install -m 0600 -o dockerforge -g dockerforge "$DIR/$x" "/var/lib/dockerforge/$x"; fi; done
systemctl daemon-reload
systemctl start dockerforge
if [[ -f /etc/systemd/system/dockerforge-metrics.service ]]; then systemctl start dockerforge-metrics; fi
echo "Offline restore started; validate health and permissions. Pre-restore checkpoint: $CHECKPOINT"
