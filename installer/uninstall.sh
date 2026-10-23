#!/usr/bin/env bash
# Remove DockerForge services and code. Data, config and backups are kept unless --purge.
# Never touches Docker, containers, volumes or Let's Encrypt certificates.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=installer/lib.sh
. "$ROOT/installer/lib.sh"

UNITS=(dockerforge.service dockerforge-metrics.service dockerforge-backup.service dockerforge-backup.timer
       dockerforge-data-backup.service dockerforge-data-backup.timer
       dockerforge-certbot-renew.service dockerforge-certbot-renew.timer)
CLIS=(dockerforge-backup dockerforge-volume-backup volume-backup.py dockerforge-bind-backup
      dockerforge-data-backup dockerforge-tls-deploy)
PURGE=0 ASSUME_YES=0

usage() {
  cat <<'EOF'
Usage: sudo bash installer/uninstall.sh [--purge] [--yes]

  --purge   Also delete /var/lib/dockerforge, /etc/dockerforge, /var/backups/dockerforge
            and the dockerforge user (asks you to type DELETE unless --yes)
  --yes     Do not ask for confirmation
  --help    Show this help
EOF
}

while (($#)); do
  case $1 in
    --purge) PURGE=1 ;;
    --yes) ASSUME_YES=1 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

[[ $(id -u) -eq 0 ]] || die 'Must run as root (use sudo)'

if [[ $PURGE -eq 1 && $ASSUME_YES -ne 1 ]]; then
  reply=''
  read -r -p 'Delete all DockerForge data, config and backups? Type DELETE: ' reply </dev/tty || true
  [[ $reply == DELETE ]] || die 'Not confirmed; nothing removed'
fi

for unit in "${UNITS[@]}"; do
  systemctl disable --now "$unit" 2>/dev/null || true
  rm -f "/etc/systemd/system/$unit"
done
systemctl daemon-reload
for cli in "${CLIS[@]}"; do rm -f "/usr/local/sbin/$cli"; done
rm -rf /opt/dockerforge
echo 'DockerForge services and code removed.'

if [[ $PURGE -eq 1 ]]; then
  rm -rf /var/lib/dockerforge /etc/dockerforge /var/backups/dockerforge
  if getent passwd dockerforge >/dev/null; then
    userdel dockerforge || echo 'Warning: could not remove user dockerforge (a process may still use it).' >&2
  fi
  echo 'Data, config, backups and the dockerforge user removed.'
else
  echo 'Kept: /var/lib/dockerforge, /etc/dockerforge, /var/backups/dockerforge (use --purge to delete).'
fi
