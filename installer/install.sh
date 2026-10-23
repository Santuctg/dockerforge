#!/usr/bin/env bash
# DockerForge fresh installer (and safe re-run) for systemd Linux with apt, dnf or zypper.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=installer/lib.sh
. "$ROOT/installer/lib.sh"

APP=/opt/dockerforge/backend
VENV=/opt/dockerforge/venv
DATA=/var/lib/dockerforge
CONF=/etc/dockerforge
TLS=$CONF/tls
ENV_FILE=$CONF/dockerforge.env
BACKUPS=/var/backups/dockerforge
OS_RELEASE=${DOCKERFORGE_OS_RELEASE:-/etc/os-release}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
UNITS=(dockerforge.service dockerforge-metrics.service dockerforge-backup.service dockerforge-backup.timer
       dockerforge-data-backup.service dockerforge-data-backup.timer)
# Firewall before TLS: certbot's standalone check needs port 80 already open.
STEPS=(step_preflight step_packages step_docker step_user_dirs step_app
       step_config step_firewall step_tls step_services step_verify)
SYSTEMD_DIR=/etc/systemd/system
TLS_HOOK=/usr/local/sbin/dockerforge-tls-deploy

DOMAIN='' EMAIL='' ASSUME_YES=0 NO_FIREWALL=0 CHECK_ONLY=0 SKIP_DNS=0 DNS_PROVIDER=''
FAMILY='' OS_ID='' PY='' BACKUP='' STAGING='' APP_SWAPPED=0 DONE=0

usage() {
  cat <<'EOF'
Usage: sudo bash installer/install.sh [options]

  --domain NAME    Get a Let's Encrypt certificate for NAME (port 80 open, unless --dns)
  --email ADDRESS  Contact address for Let's Encrypt (required with --domain)
  --dns cloudflare Get the certificate with a DNS challenge through Cloudflare instead of
                   port 80; works with a local IP. Token from CF_API_TOKEN or asked once
  --yes            Install Docker without asking if it is missing
  --no-firewall    Do not open ports in ufw/firewalld
  --skip-dns-check Do not check that --domain points to this server
  --check          Run preflight checks only; change nothing
  --help           Show this help

Without --domain a self-signed certificate is created.
Re-running keeps the database, users, config, setup token and certificates.
EOF
}

parse_args() {
  while (($#)); do
    case $1 in
      --domain) [[ $# -ge 2 ]] || { echo '--domain needs a value' >&2; exit 2; }; DOMAIN=$2; shift ;;
      --email) [[ $# -ge 2 ]] || { echo '--email needs a value' >&2; exit 2; }; EMAIL=$2; shift ;;
      --yes) ASSUME_YES=1 ;;
      --no-firewall) NO_FIREWALL=1 ;;
      --skip-dns-check) SKIP_DNS=1 ;;
      --dns) [[ $# -ge 2 ]] || { echo '--dns needs a value' >&2; exit 2; }; DNS_PROVIDER=$2; shift ;;
      --check) CHECK_ONLY=1 ;;
      --help|-h) usage; exit 0 ;;
      *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
  done
  case $DNS_PROVIDER in
    ''|cloudflare) ;;
    *) echo "Unsupported --dns provider: $DNS_PROVIDER (supported: cloudflare)" >&2; exit 2 ;;
  esac
  if [[ -n $DNS_PROVIDER && -z $DOMAIN ]]; then echo '--dns needs --domain' >&2; exit 2; fi
  if [[ -n $DOMAIN && -z $EMAIL ]]; then echo '--email is required with --domain' >&2; exit 2; fi
  if [[ -n $DOMAIN && ! $DOMAIN =~ ^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$ ]]; then
    echo "Invalid domain: $DOMAIN" >&2; exit 2
  fi
}

confirm() {
  [[ $ASSUME_YES -eq 1 ]] && return 0
  local reply=''
  read -r -p "$1 [y/N] " reply </dev/tty || true
  [[ $reply =~ ^[Yy] ]] || die "$2"
}

pkg_install() {
  case $FAMILY in
    debian) DEBIAN_FRONTEND=noninteractive apt-get install -y -q "$@" ;;
    rhel) dnf -y -q install "$@" ;;
    suse) zypper --non-interactive --quiet install "$@" ;;
  esac
}

step_preflight() {
  FAMILY=$(detect_family "$OS_RELEASE") || exit 1
  # shellcheck source=/dev/null
  OS_ID=$( . "$OS_RELEASE"; echo "${ID:-}" )
  echo "Distribution: $OS_ID (family $FAMILY, $(pkg_manager "$FAMILY"))"
  [[ $(id -u) -eq 0 ]] || die 'Must run as root (use sudo)'
  [[ -d /run/systemd/system ]] || die 'systemd is required and must be running'
  if PY=$(find_python); then echo "Python: $PY"; else echo 'Python 3.11+: not found, will be installed'; fi
  if port_in_use 9443 && ! systemctl is-active --quiet dockerforge; then
    die 'Port 9443 is already in use by another program'
  fi
  preflight_domain
  if [[ -f $APP/app/core.py ]]; then echo 'Existing DockerForge found: code will be updated, data kept'; fi
}

# Let's Encrypt prerequisites: DNS must point here and port 80 be free, unless a DNS challenge is used.
preflight_domain() {
  [[ -n $DOMAIN ]] || return 0
  if [[ -n $DNS_PROVIDER ]]; then
    echo "Certificate: Let's Encrypt DNS challenge via $DNS_PROVIDER (port 80 and public IP not needed)"
    return 0
  fi
  [[ -d /etc/letsencrypt/live/$DOMAIN ]] && return 0
  if [[ $SKIP_DNS -ne 1 ]]; then
    local resolved
    resolved=$(getent ahosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ') || true
    dns_check "$DOMAIN" "$resolved" "$(public_ip)" || exit 1
    echo "DNS: $DOMAIN -> $resolved"
  fi
  if port_in_use 80; then
    die 'Port 80 is in use; Let'"'"'s Encrypt needs it free to issue the certificate (or use --dns cloudflare)'
  fi
}

step_packages() {
  local base extra=()
  if [[ -n $DOMAIN ]]; then
    extra=(certbot)
    [[ $DNS_PROVIDER == cloudflare ]] && extra+=(python3-certbot-dns-cloudflare)
  fi
  case $FAMILY in
    debian)
      apt-get update -q
      base=(python3 python3-venv curl openssl ca-certificates iproute2) ;;
    rhel)
      base=(python3 python3-pip openssl iproute hostname)
      # EL9 ships curl-minimal, which conflicts with the curl package.
      command -v curl >/dev/null 2>&1 || base+=(curl)
      if [[ -n $DOMAIN && $OS_ID != fedora ]]; then
        pkg_install epel-release || die 'certbot needs EPEL; enable the EPEL repository and re-run'
      fi ;;
    suse)
      base=(python311 curl openssl iproute2)
      # openSUSE names the certbot package python3-certbot.
      if [[ -n $DOMAIN ]]; then extra[0]=python3-certbot; fi ;;
  esac
  pkg_install "${base[@]}" "${extra[@]}"
  if ! PY=$(find_python); then
    case $FAMILY in
      debian) pkg_install python3.11 python3.11-venv ;;
      rhel) pkg_install python3.11 ;;
      suse) pkg_install python311 ;;
    esac
    PY=$(find_python) || die 'Python 3.11 or newer is required and could not be installed'
  fi
  echo "Python: $PY"
}

# How to install Docker Engine when it is missing: get.docker.com does not support Rocky/Alma/Oracle.
docker_install_method() {
  case $1 in
    debian) echo get.docker.com ;;
    rhel) if [[ $2 == fedora ]]; then echo get.docker.com; else echo docker-ce-repo; fi ;;
    suse) echo zypper ;;
  esac
}

install_docker_engine() {
  case $(docker_install_method "$FAMILY" "$OS_ID") in
    get.docker.com)
      local script
      script=$(mktemp)
      curl -fsSL https://get.docker.com -o "$script"
      sh "$script" || { rm -f "$script"; die 'Docker install failed; install Docker Engine manually (docs.docker.com/engine/install) and re-run'; }
      rm -f "$script" ;;
    docker-ce-repo)
      pkg_install dnf-plugins-core
      dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
      pkg_install docker-ce docker-ce-cli containerd.io docker-compose-plugin ;;
    zypper)
      pkg_install docker docker-compose ;;
  esac
}

# Existing engine without Compose: add only the plugin, never reinstall the engine under running containers.
install_compose_plugin() {
  case $FAMILY in
    debian) pkg_install docker-compose-plugin || pkg_install docker-compose-v2 ;;
    rhel) pkg_install docker-compose-plugin ;;
    suse) pkg_install docker-compose ;;
  esac
}

step_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    confirm 'Docker is not installed. Install Docker Engine with Compose now?' 'Docker is required. Install it, or re-run with --yes'
    install_docker_engine
  elif ! docker compose version >/dev/null 2>&1; then
    confirm 'Docker is installed but the Compose plugin is missing. Install the plugin now?' 'Docker Compose is required. Install it, or re-run with --yes'
    install_compose_plugin
  fi
  systemctl enable --now docker
  docker compose version >/dev/null 2>&1 || die 'Docker Compose plugin is missing (docker compose)'
  echo "Docker: $(docker --version)"
}

step_user_dirs() {
  if ! getent passwd dockerforge >/dev/null; then
    useradd --system --user-group --home-dir "$DATA" --no-create-home --shell "$(command -v nologin || echo /bin/false)" dockerforge
  fi
  # Docker group access is root-equivalent; see SECURITY.md.
  usermod -aG docker dockerforge
  install -d -m 0755 -o root -g root /opt/dockerforge
  install -d -m 0750 -o dockerforge -g dockerforge "$DATA"
  install -d -m 0700 -o dockerforge -g dockerforge "$DATA/stacks" "$DATA/.docker"
  install -d -m 0750 -o root -g dockerforge "$CONF" "$TLS"
  install -d -m 0700 -o root -g root "$BACKUPS"
}

backup_existing() {
  BACKUP=/root/dockerforge-install-backup-$STAMP
  mkdir -m 0700 "$BACKUP"
  cp -a "$APP" "$BACKUP/backend"
  cp -a "$CONF" "$BACKUP/etc-dockerforge"
  mkdir "$BACKUP/units"
  local unit
  for unit in "${UNITS[@]}"; do
    [[ -f /etc/systemd/system/$unit ]] && cp -a "/etc/systemd/system/$unit" "$BACKUP/units/"
  done
  if [[ -f $DATA/dockerforge.db ]]; then
    "$PY" - "$DATA/dockerforge.db" "$BACKUP/dockerforge.db" <<'PY'
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as src, sqlite3.connect(sys.argv[2]) as dst:
    src.backup(dst)
PY
    chmod 0600 "$BACKUP/dockerforge.db"
  fi
  echo "Previous install backed up to $BACKUP"
}

step_app() {
  [[ -f $APP/app/core.py ]] && backup_existing
  STAGING=/opt/dockerforge/.staging-$STAMP
  local staging=$STAGING
  stage_backend "$ROOT/backend" "$staging"
  "$PY" -m compileall -q "$staging/app"
  [[ -x $VENV/bin/python ]] || "$PY" -m venv "$VENV"
  local reqs
  reqs=$(mktemp)
  backend_requirements "$VENV/bin/python" "$staging/pyproject.toml" >"$reqs"
  "$VENV/bin/pip" install --quiet --disable-pip-version-check -r "$reqs"
  rm -f "$reqs"
  systemctl stop dockerforge-metrics dockerforge 2>/dev/null || true
  rm -rf "$APP"
  mv "$staging" "$APP"
  APP_SWAPPED=1
}

step_config() {
  printf 'Env file: '
  ensure_env_file "$ENV_FILE" || die "Could not create $ENV_FILE"
  chown root:dockerforge "$ENV_FILE"
  if [[ ! -e $CONF/data-backup.json ]]; then
    install -m 0600 "$ROOT/data-backup.example.json" "$CONF/data-backup.json"
  fi
}

step_tls() {
  install -m 0750 "$ROOT/installer/tls-deploy-hook.sh" "$TLS_HOOK"
  if [[ -n $DOMAIN ]]; then
    local auth=(--standalone)
    if [[ $DNS_PROVIDER == cloudflare ]]; then
      printf 'Cloudflare credentials: '
      ensure_cloudflare_credentials "$CONF/cloudflare.ini" ||
        die 'A Cloudflare API token with Zone > DNS > Edit permission is required (set CF_API_TOKEN or enter it when asked)'
      auth=(--dns-cloudflare --dns-cloudflare-credentials "$CONF/cloudflare.ini" --dns-cloudflare-propagation-seconds 30)
    fi
    certbot certonly "${auth[@]}" --non-interactive --agree-tos --keep-until-expiring \
      -m "$EMAIL" -d "$DOMAIN" --deploy-hook "$TLS_HOOK"
    RENEWED_LINEAGE=/etc/letsencrypt/live/$DOMAIN "$TLS_HOOK"
    ensure_renew_timer
    echo "Let's Encrypt certificate installed for $DOMAIN"
  elif [[ ! -f $TLS/fullchain.pem ]]; then
    local host ip
    host=$(hostname -f 2>/dev/null || hostname)
    ip=$(primary_ip)
    openssl req -x509 -newkey rsa:3072 -nodes -days 3650 -subj "/CN=$host" \
      -addext "subjectAltName=DNS:$host,IP:$ip" \
      -keyout "$TLS/privkey.pem" -out "$TLS/fullchain.pem" 2>/dev/null
    chown root:dockerforge "$TLS/privkey.pem" "$TLS/fullchain.pem"
    chmod 0640 "$TLS/privkey.pem" "$TLS/fullchain.pem"
    echo 'Self-signed certificate created (browser will warn once)'
  else
    echo 'Existing certificate kept'
  fi
}

# Use the distro's certbot timer if it ships one, otherwise install our own.
ensure_renew_timer() {
  local listed timer
  listed=$(systemctl list-unit-files --no-legend 'certbot*.timer' 'snap.certbot*.timer' 2>/dev/null || true)
  for timer in certbot.timer certbot-renew.timer snap.certbot.renew.timer; do
    if awk -v t="$timer" '$1 == t {found=1} END {exit !found}' <<<"$listed"; then
      systemctl enable --now "$timer"
      echo "Certificate renewal: $timer"
      return 0
    fi
  done
  install -m 0644 "$ROOT/systemd/dockerforge-certbot-renew.service" "$SYSTEMD_DIR/dockerforge-certbot-renew.service"
  install -m 0644 "$ROOT/systemd/dockerforge-certbot-renew.timer" "$SYSTEMD_DIR/dockerforge-certbot-renew.timer"
  systemctl daemon-reload
  systemctl enable --now dockerforge-certbot-renew.timer
  echo 'Certificate renewal: dockerforge-certbot-renew.timer'
}

step_services() {
  local unit
  for unit in "${UNITS[@]}"; do
    install -m 0644 "$ROOT/systemd/$unit" "/etc/systemd/system/$unit"
  done
  install -m 0750 "$ROOT/scripts/backup-manager.py" /usr/local/sbin/dockerforge-backup
  install -m 0750 "$ROOT/scripts/volume-backup.py" /usr/local/sbin/dockerforge-volume-backup
  install -m 0644 "$ROOT/scripts/volume-backup.py" /usr/local/sbin/volume-backup.py
  install -m 0750 "$ROOT/scripts/bind-backup.py" /usr/local/sbin/dockerforge-bind-backup
  install -m 0750 "$ROOT/scripts/data-backup-job.py" /usr/local/sbin/dockerforge-data-backup
  systemctl daemon-reload
  systemctl enable dockerforge dockerforge-metrics
  systemctl restart dockerforge dockerforge-metrics
  systemctl enable --now dockerforge-backup.timer
}

step_firewall() {
  if [[ $NO_FIREWALL -eq 1 ]]; then echo 'Firewall: skipped (--no-firewall)'; return 0; fi
  local http=0
  if [[ -n $DOMAIN && -z $DNS_PROVIDER ]]; then http=1; fi
  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q 'Status: active'; then
    ufw allow 9443/tcp
    if [[ $http -eq 1 ]]; then ufw allow 80/tcp; fi
  elif command -v firewall-cmd >/dev/null 2>&1 && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --quiet --permanent --add-port=9443/tcp
    if [[ $http -eq 1 ]]; then firewall-cmd --quiet --permanent --add-port=80/tcp; fi
    firewall-cmd --quiet --reload
  else
    echo 'Firewall: no active ufw/firewalld found, nothing changed'
    return 0
  fi
  if [[ $http -eq 1 ]]; then echo 'Firewall: opened 9443/tcp and 80/tcp'; else echo 'Firewall: opened 9443/tcp'; fi
}

step_verify() {
  local i healthy=0
  for i in $(seq 1 30); do
    if curl -kfsS --max-time 2 https://127.0.0.1:9443/health 2>/dev/null | grep -q '"status":"ok"'; then healthy=1; break; fi
    sleep 1
  done
  [[ $healthy -eq 1 ]] || die 'DockerForge did not become healthy; check: journalctl -u dockerforge'
  systemctl is-active --quiet dockerforge-metrics || die 'Metrics collector is not running; check: journalctl -u dockerforge-metrics'
  DONE=1
  local host=${DOMAIN:-$(primary_ip)}
  echo
  echo "DockerForge is running: https://$host:9443"
  if curl -kfsS --max-time 2 https://127.0.0.1:9443/api/v1/auth/setup/status 2>/dev/null | grep -q '"setup_required":true'; then
    echo "First-run setup token: $(sed -n 's/^DOCKERFORGE_SETUP_TOKEN=//p' "$ENV_FILE")"
    echo 'Open the URL, enter this token and create your Super Admin account.'
  fi
  [[ -n $BACKUP ]] && echo "Previous install backup: $BACKUP"
  echo 'Security: DockerForge controls the whole Docker host. Restrict port 9443 to trusted IPs or a VPN.'
}

rollback() {
  echo 'Install failed.' >&2
  if [[ -n $STAGING && -d $STAGING ]]; then rm -rf "$STAGING"; fi
  if [[ $APP_SWAPPED -eq 1 && -n $BACKUP && -d $BACKUP/backend ]]; then
    echo 'Restoring previous version...' >&2
    rm -rf "$APP"
    cp -a "$BACKUP/backend" "$APP"
    cp -a "$BACKUP/units/." /etc/systemd/system/ 2>/dev/null || true
    systemctl daemon-reload || true
    systemctl restart dockerforge dockerforge-metrics || true
    echo "Backup kept at: $BACKUP" >&2
  elif [[ $APP_SWAPPED -eq 1 ]]; then
    systemctl stop dockerforge dockerforge-metrics 2>/dev/null || true
    echo 'New services stopped; files left in place for inspection.' >&2
  elif [[ -n $BACKUP ]]; then
    echo "The running install was not changed. Backup kept at: $BACKUP" >&2
  fi
}

on_exit() {
  local rc=$?
  if [[ $rc -ne 0 && $DONE -ne 1 ]]; then rollback; fi
}

main() {
  parse_args "$@"
  if [[ $CHECK_ONLY -eq 1 ]]; then
    step_preflight
    echo 'Preflight OK'
    return 0
  fi
  trap on_exit EXIT
  local i=0 step
  for step in "${STEPS[@]}"; do
    i=$((i + 1))
    log_step "$i" "${#STEPS[@]}" "${step#step_}"
    "$step"
  done
}

# `source install.sh --source-only` loads the functions without running anything (tests).
if [[ ${BASH_SOURCE[0]} != "$0" ]]; then return 0; fi
main "$@"
