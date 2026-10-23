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
  local path=$1 token
  if [[ -e $path ]]; then echo kept; return 0; fi
  token=$(openssl rand -hex 24)
  (
    umask 027
    cat >"$path" <<EOF
DOCKERFORGE_DB=/var/lib/dockerforge/dockerforge.db
DOCKERFORGE_DOCKER_SOCKET=/var/run/docker.sock
DOCKERFORGE_SETUP_TOKEN=$token
EOF
  )
  chmod 0640 "$path"
  echo created
}
