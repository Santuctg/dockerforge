# Fresh installer for DockerForge v0.7.0 — design

## Goal

Install DockerForge from this repository on a new Linux server with one
command, so the whole Docker host is managed from the web panel. Today the
repo only ships `installer/upgrade.sh`, which requires an existing v0.6.0
install; there is no fresh install path and no main `dockerforge.service`.

## Scope

In scope:
- `installer/install.sh` — fresh install and idempotent re-run.
- `installer/uninstall.sh` — remove services; keep data unless `--purge`.
- `systemd/dockerforge.service` — the main web service unit.
- `installer/tls-deploy-hook.sh` — copy renewed Let's Encrypt certs and restart.
- Tests for the installer (static checks and distro detection).

Out of scope: Windows/macOS (no systemd, no Unix Docker socket; a container
image can be a later sub-project), new web features, changes to the API.

## Supported systems

Any systemd Linux with one of these package managers, detected via
`/etc/os-release` (`ID`, then `ID_LIKE`):

| Family | IDs | Package manager |
|---|---|---|
| Debian | ubuntu, debian, (ID_LIKE debian) | apt-get |
| Red Hat | rhel, rocky, almalinux, centos, fedora, (ID_LIKE rhel/fedora) | dnf |
| SUSE | opensuse-leap, opensuse-tumbleweed, sles, (ID_LIKE suse) | zypper |

Anything else: exit with a clear "unsupported distribution" message.
Python 3.11+ is required (`pyproject.toml`); if the system `python3` is older
the installer tries the distro's `python3.11`/`python3.12` package, else exits.

## Command line

```
sudo bash installer/install.sh --domain panel.example.com --email you@example.com
sudo bash installer/install.sh                 # no domain: self-signed cert
sudo bash installer/install.sh --check         # preflight only, change nothing
```

Options: `--domain`, `--email` (required with `--domain`), `--yes` (accept
installing Docker without prompting), `--no-firewall`, `--check`.

## Install steps

1. **Preflight**: root; systemd running; supported distro; Python ≥ 3.11
   available or installable; ports 9443 (and 80 when `--domain`) free unless
   held by an existing DockerForge. `--check` stops here and prints results.
2. **Packages**: python3, venv support, curl, openssl, and certbot when
   `--domain` is given.
3. **Docker**: if `docker` or `docker compose` is missing, ask (or `--yes`)
   then install via `https://get.docker.com`; enable and start `docker`.
4. **User/dirs**: system user `dockerforge` (no login shell), added to the
   `docker` group — this is root-equivalent and is documented as such.
   Directories and modes:
   - `/opt/dockerforge` 0755 root; `backend/`, `venv/`
   - `/var/lib/dockerforge` 0750 dockerforge (DB, stacks, metrics, alerts)
   - `/etc/dockerforge` 0750 root:dockerforge; `tls/` 0750
   - `/var/backups/dockerforge` 0700 root
5. **App**: stage backend to `/opt/dockerforge/.staging-<stamp>`, compile, then
   swap into `/opt/dockerforge/backend`. Create venv if missing and
   `pip install` the backend (`pyproject.toml` dependencies).
6. **Config**: create `/etc/dockerforge/dockerforge.env` (0640
   root:dockerforge) only if absent, with a fresh random
   `DOCKERFORGE_SETUP_TOKEN` and the DB/socket paths. Existing env is never
   overwritten. Install `data-backup.json` from the example only if absent.
7. **TLS**:
   - `--domain`: `certbot certonly --standalone -d <domain> -m <email>
     --agree-tos --non-interactive --deploy-hook /usr/local/sbin/dockerforge-tls-deploy`.
     The hook copies `fullchain.pem`/`privkey.pem` to `/etc/dockerforge/tls/`
     (0640 root:dockerforge) and restarts `dockerforge`. Installer runs the
     hook once directly after the first issue. certbot's own timer renews.
   - no domain: generate a self-signed cert (10 years, CN = hostname, SAN =
     hostname + primary IP) into the same paths, only if none exists.
8. **Services**: install `dockerforge.service` plus existing metrics, backup
   and data-backup units and the backup CLIs (same targets as `upgrade.sh`).
   `daemon-reload`; enable and start `dockerforge` and `dockerforge-metrics`;
   enable `dockerforge-backup.timer`. The data-backup timer stays opt-in.
9. **Firewall**: if `ufw` or `firewalld` is active, open 9443/tcp and (with
   `--domain`) 80/tcp. Skipped with `--no-firewall`.
10. **Verify**: poll `https://127.0.0.1:9443/health` for up to 30 s. Print the
    panel URL, the setup token (only while no user exists), and a reminder
    to restrict 9443 to trusted networks/VPN.

## `dockerforge.service`

Runs as `dockerforge`, `EnvironmentFile=/etc/dockerforge/dockerforge.env`,
`ExecStart=/opt/dockerforge/venv/bin/uvicorn app.main:app --host 0.0.0.0
--port 9443 --ssl-certfile /etc/dockerforge/tls/fullchain.pem --ssl-keyfile
/etc/dockerforge/tls/privkey.pem`, `WorkingDirectory=/opt/dockerforge/backend`,
`Restart=on-failure`, `NoNewPrivileges`, `ProtectSystem=strict`,
`ProtectHome`, `PrivateTmp`, `ReadWritePaths=/var/lib/dockerforge`. The
`upgrade.sh` prerequisites (`/opt/dockerforge/backend/app/core.py`,
`/etc/dockerforge/dockerforge.env`, active `dockerforge`) are all satisfied,
so future upgrades keep working.

## Re-running (idempotency)

Existing user, DB, env file, setup token, certs, stacks and backup settings
are kept. Only code, venv dependencies, units and CLIs are refreshed. Before
replacing anything on a re-run, the installer copies the previous backend,
units and `/etc/dockerforge` to `/root/dockerforge-install-backup-<stamp>`
(0700) and takes an SQLite online backup of the DB, like `upgrade.sh`.

## Failure handling

`set -Eeuo pipefail`; every step logs `[n/10] …`. An `ERR` trap restores the
previous backend and units from the re-run backup (if any), restarts the old
service, and prints where the backup is. On a first install with no previous
state, it stops the new service and leaves files in place for inspection.

## Uninstall

`installer/uninstall.sh`: stop and disable all `dockerforge*` units, remove
unit files, CLIs in `/usr/local/sbin`, the TLS deploy hook and
`/opt/dockerforge`. Keeps `/var/lib/dockerforge`, `/etc/dockerforge`,
`/var/backups/dockerforge` and the user unless `--purge` (which asks for
confirmation, or `--yes`). Never touches Docker, containers, volumes or
Let's Encrypt certificates.

## Testing

- `shellcheck` on all installer scripts.
- `backend/tests/test_installer.py`: distro detection function against sample
  `os-release` files for each family and an unsupported one; the unit file
  has the required paths/user/hardening; `install.sh --help` exits 0.
- Run `install.sh --check` inside ubuntu, debian, rockylinux and opensuse
  containers where available to confirm detection and preflight output.
- Existing pytest suite still passes.
- Not testable here: real Let's Encrypt issuance and a full systemd boot;
  the user verifies these on a real server.
