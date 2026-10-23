#!/usr/bin/env bash
# Shared helpers for install.sh/uninstall.sh. Sourcing this file has no side effects.

die() { echo "ERROR: $*" >&2; exit 1; }
log_step() { echo "[$1/$2] $3"; }

# Print debian|rhel|suse for an os-release file; ID wins over ID_LIKE.
detect_family() {
  local fields id like word
  # shellcheck source=/dev/null
  fields=$( . "$1"; echo "${ID:-}|${ID_LIKE:-}" ) || die "Cannot read $1"
  id=${fields%%|*}; like=${fields#*|}
  for word in $id $like; do
    case $word in
      debian|ubuntu) echo debian; return 0 ;;
      rhel|centos|rocky|almalinux|fedora|ol) echo rhel; return 0 ;;
      suse|sles|opensuse|opensuse-leap|opensuse-tumbleweed) echo suse; return 0 ;;
    esac
  done
  echo "Unsupported distribution: ${id:-unknown}" >&2
  return 1
}

pkg_manager() {
  case $1 in
    debian) echo apt-get ;;
    rhel) echo dnf ;;
    suse) echo zypper ;;
    *) return 1 ;;
  esac
}

python_version_ok() {
  "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
}

find_python() {
  local candidate
  for candidate in python3 python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1 && python_version_ok "$candidate"; then
      command -v "$candidate"; return 0
    fi
  done
  return 1
}

# Create the service env file once; never touch an existing one (keeps the setup token).
ensure_env_file() {
  local path=$1 token tmp
  if [[ -e $path ]]; then echo kept; return 0; fi
  token=$(openssl rand -hex 24) || return 1
  [[ $token =~ ^[0-9a-f]{48}$ ]] || return 1
  tmp=$(mktemp "$path.XXXXXX") || return 1
  printf 'DOCKERFORGE_DB=/var/lib/dockerforge/dockerforge.db\nDOCKERFORGE_DOCKER_SOCKET=/var/run/docker.sock\nDOCKERFORGE_SETUP_TOKEN=%s\n' "$token" >"$tmp" || { rm -f "$tmp"; return 1; }
  if ! { chmod 0640 "$tmp" && mv "$tmp" "$path"; }; then rm -f "$tmp"; return 1; fi
  echo created
}

# Print the backend's runtime dependencies, one per line (python >= 3.11 has tomllib).
backend_requirements() {
  "$1" - "$2" <<'PY'
import sys, tomllib
with open(sys.argv[1], 'rb') as f:
    print('\n'.join(tomllib.load(f)['project']['dependencies']))
PY
}

# Best-effort primary IPv4 address, used for the self-signed SAN and the printed URL.
primary_ip() {
  local ip
  ip=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}') || true
  echo "${ip:-127.0.0.1}"
}

port_in_use() {
  command -v ss >/dev/null 2>&1 || return 1
  [[ -n $(ss -ltnH "sport = :$1" 2>/dev/null) ]]
}
