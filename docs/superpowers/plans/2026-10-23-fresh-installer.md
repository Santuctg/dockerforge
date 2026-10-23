# Fresh Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One-command fresh install (and idempotent re-run / uninstall) of DockerForge v0.7.0 on any systemd Linux using apt, dnf or zypper.

**Architecture:** Pure-function helpers live in `installer/lib.sh` (sourced, no side effects on source) so pytest can exercise them through `bash -c`. `installer/install.sh` and `installer/uninstall.sh` are thin step-runners over those helpers. A new `systemd/dockerforge.service` runs uvicorn with TLS from `/etc/dockerforge/tls/`; `installer/tls-deploy-hook.sh` refreshes those files from Let's Encrypt.

**Tech Stack:** bash 4+, systemd, certbot, openssl, Python 3.11+ venv, pytest (subprocess calls to bash).

**Spec:** `docs/superpowers/specs/2026-10-23-fresh-installer-design.md`

## Global Constraints

- Paths: app `/opt/dockerforge/backend`, venv `/opt/dockerforge/venv`, data `/var/lib/dockerforge` (0750 dockerforge), config `/etc/dockerforge` (0750 root:dockerforge), TLS `/etc/dockerforge/tls/{fullchain,privkey}.pem` (0640 root:dockerforge), backups `/var/backups/dockerforge` (0700 root).
- Env file `/etc/dockerforge/dockerforge.env` is 0640 root:dockerforge and is never overwritten once it exists.
- Port 9443 HTTPS; port 80 only when `--domain` is given.
- Python ≥ 3.11 (`backend/pyproject.toml`).
- Supported families: `debian` (apt-get), `rhel` (dnf), `suse` (zypper); everything else exits non-zero with "Unsupported distribution".
- Never modify Docker containers, volumes, or Let's Encrypt certificates on uninstall.
- All scripts `set -Eeuo pipefail` and pass `shellcheck`.
- Re-run backup dir: `/root/dockerforge-install-backup-<UTC stamp>` (0700).

## Review Focus

- `ID_LIKE` with several quoted values (`ID_LIKE="rhel centos fedora"`) or an unknown `ID` with a known `ID_LIKE` must still detect the family → covered in Task 1 tests.
- Re-run on an installed host must keep the existing setup token and env file byte-for-byte → `ensure_env_file` test in Task 1.
- System `python3` older than 3.11 must be rejected, not silently used → `python_version_ok` test in Task 1.
- `--domain` without `--email` (certbot would fail mid-install) must be rejected before any change → Task 3 argument test.
- `dockerforge` user must be created after Docker is installed so the `docker` group exists → ordering asserted in Task 3 (step list test).

---

### Task 1: `installer/lib.sh` helpers

**Files:**
- Create: `installer/lib.sh`
- Test: `backend/tests/test_installer.py`

**Interfaces:**
- Produces (all bash functions; stdout is the result, exit status signals failure):
  - `detect_family <os_release_path>` → prints `debian|rhel|suse`; exit 1 and stderr `Unsupported distribution: <ID>` otherwise. Checks `ID` first, then each word of `ID_LIKE`.
  - `pkg_manager <family>` → prints `apt-get|dnf|zypper`.
  - `python_version_ok <python_bin>` → exit 0 iff the interpreter is ≥ 3.11.
  - `find_python` → prints the first of `python3 python3.13 python3.12 python3.11` that passes `python_version_ok`; exit 1 if none.
  - `ensure_env_file <path>` → if absent, writes env with `DOCKERFORGE_DB=/var/lib/dockerforge/dockerforge.db`, `DOCKERFORGE_DOCKER_SOCKET=/var/run/docker.sock`, `DOCKERFORGE_SETUP_TOKEN=<openssl rand -hex 24>`, mode 0640; if present, does nothing. Prints `created` or `kept`.
  - `log_step <n> <total> <message>` → prints `[n/total] message`.
  - `die <message>` → stderr `ERROR: message`, exit 1.

- [ ] **Step 1: Write failing tests** in `backend/tests/test_installer.py` with a helper `sh(script, *args)` that runs `bash -c 'source <repo>/installer/lib.sh; <script>'` and returns `CompletedProcess`:
  - `test_detect_family_known_ids`: os-release files with `ID=ubuntu`, `ID=debian`, `ID=rocky`, `ID=almalinux`, `ID=fedora`, `ID="opensuse-leap"`, `ID=sles` → `debian, debian, rhel, rhel, rhel, suse, suse`.
  - `test_detect_family_id_like`: `ID=linuxmint\nID_LIKE="ubuntu debian"` → `debian`; `ID=ol\nID_LIKE="fedora"` → `rhel`.
  - `test_detect_family_unsupported`: `ID=arch` → returncode 1, `Unsupported distribution: arch` in stderr.
  - `test_pkg_manager`: `debian→apt-get`, `rhel→dnf`, `suse→zypper`.
  - `test_python_version_ok`: current `sys.executable` passes (suite runs on ≥3.11); a fake script printing `3.9` via `-c` emulation fails — implement as a temp executable `fakepy` that exits 1 for the version check (`#!/bin/sh\nexit 1`).
  - `test_ensure_env_file_creates_then_keeps`: first call prints `created`, file mode `0o640`, contains `DOCKERFORGE_SETUP_TOKEN=` followed by 48 hex chars; second call prints `kept` and file bytes unchanged.

- [ ] **Step 2: Run** `cd backend && python3 -m pytest tests/test_installer.py -v` — Expected: FAIL (lib.sh missing).

- [ ] **Step 3: Implement `installer/lib.sh`.** Parse os-release by sourcing it in a subshell (`( . "$1"; echo "$ID|${ID_LIKE:-}" )`). Family map: debian ← `debian ubuntu`; rhel ← `rhel centos rocky almalinux fedora ol`; suse ← `suse sles opensuse opensuse-leap opensuse-tumbleweed`. `python_version_ok` runs `"$1" -c 'import sys; sys.exit(0 if sys.version_info>=(3,11) else 1)'`.

- [ ] **Step 4: Run** the same pytest command — Expected: PASS. Run `shellcheck installer/lib.sh` — Expected: no output.

- [ ] **Step 5: Commit** `git add installer/lib.sh backend/tests/test_installer.py && git commit -m "installer: add distro detection and env helpers"`

### Task 2: systemd unit and TLS deploy hook

**Files:**
- Create: `systemd/dockerforge.service`, `installer/tls-deploy-hook.sh`
- Test: `backend/tests/test_installer.py`

**Interfaces:**
- Produces: `tls-deploy-hook.sh` installed later as `/usr/local/sbin/dockerforge-tls-deploy`. Reads `$RENEWED_LINEAGE` (set by certbot), copies `fullchain.pem` and `privkey.pem` into `${DOCKERFORGE_TLS_DIR:-/etc/dockerforge/tls}` with `install -m 0640 -o root -g dockerforge`, then `systemctl try-restart dockerforge`. Exits 1 if `RENEWED_LINEAGE` is unset or files are missing.

- [ ] **Step 1: Write failing tests:**
  - `test_service_unit_contents`: parse `systemd/dockerforge.service`; assert `User=dockerforge`, `EnvironmentFile=/etc/dockerforge/dockerforge.env`, `WorkingDirectory=/opt/dockerforge/backend`, `ExecStart` contains `/opt/dockerforge/venv/bin/uvicorn app.main:app`, `--port 9443`, `--ssl-certfile /etc/dockerforge/tls/fullchain.pem`, `--ssl-keyfile /etc/dockerforge/tls/privkey.pem`; and each of `NoNewPrivileges=true`, `ProtectSystem=strict`, `ProtectHome=true`, `PrivateTmp=true`, `ReadWritePaths=/var/lib/dockerforge`, `Restart=on-failure`, `WantedBy=multi-user.target`.
  - `test_tls_hook_requires_lineage`: running the hook with no `RENEWED_LINEAGE` → returncode 1.

- [ ] **Step 2: Run** pytest on these two tests — Expected: FAIL.

- [ ] **Step 3: Create both files.** Unit has `After=network-online.target docker.service`, `Wants=network-online.target docker.service`.

- [ ] **Step 4: Run** pytest and `shellcheck installer/tls-deploy-hook.sh` — Expected: PASS / no output.

- [ ] **Step 5: Commit** `git commit -m "installer: add main service unit and TLS deploy hook"`

### Task 3: `installer/install.sh`

**Files:**
- Create: `installer/install.sh`
- Test: `backend/tests/test_installer.py`

**Interfaces:**
- Consumes: everything from Task 1; `systemd/dockerforge.service` and `installer/tls-deploy-hook.sh` from Task 2.
- Produces: CLI `install.sh [--domain D --email E] [--yes] [--no-firewall] [--check] [--help]`. Env override `DOCKERFORGE_OS_RELEASE` (default `/etc/os-release`) for testing. Functions named `step_preflight step_packages step_docker step_user_dirs step_app step_config step_tls step_services step_firewall step_verify`, called in that order from `main`; `STEPS` array lists those names in order.

- [ ] **Step 1: Write failing tests:**
  - `test_install_help`: `bash installer/install.sh --help` → returncode 0, stdout contains `--domain` and `--check`.
  - `test_install_domain_requires_email`: `--domain x.example.com` alone → returncode 2, stderr contains `--email is required`.
  - `test_install_unknown_option`: `--bogus` → returncode 2.
  - `test_install_step_order`: `bash -c 'source installer/install.sh --source-only; printf "%s\n" "${STEPS[@]}"'` prints the ten step names in the order above (`step_docker` before `step_user_dirs`).
  - `test_install_check_unsupported`: with `DOCKERFORGE_OS_RELEASE` pointing at `ID=arch`, `--check` → returncode 1, `Unsupported distribution` in stderr. (Script must evaluate the distro check before the root check when `--check` is given, so this runs unprivileged.)

- [ ] **Step 2: Run** these tests — Expected: FAIL.

- [ ] **Step 3: Implement `install.sh`.** Behaviour per spec "Install steps" 1–10. Specifics the spec leaves open:
  - `--source-only` makes the script define functions and `STEPS` then `return` (for tests).
  - Port check uses `ss -ltnH "sport = :<port>"`; a port held by `dockerforge.service` counts as free.
  - Packages: debian `python3 python3-venv curl openssl ca-certificates iproute2` (+`certbot`); rhel `python3 python3-pip curl openssl iproute` (+`certbot`, enabling `epel-release` first on non-Fedora); suse `python311 curl openssl iproute2` (+`python3-certbot`). After install, `find_python` must succeed or `die`.
  - Docker missing: prompt `Docker is not installed. Install it now via get.docker.com? [y/N]` unless `--yes`; refusal → `die`.
  - Re-run detection: `/opt/dockerforge/backend/app/core.py` exists → make backup dir, `cp -a` backend, units, `/etc/dockerforge`, and SQLite online backup of the DB (same Python snippet as `upgrade.sh`).
  - `trap rollback ERR`; `rollback` restores backend and units from the backup dir if it exists, `systemctl daemon-reload`, `systemctl restart dockerforge || true`, prints backup path.
  - venv: `"$PY" -m venv /opt/dockerforge/venv` if missing, then `/opt/dockerforge/venv/bin/pip install --quiet /opt/dockerforge/backend`.
  - Self-signed: `openssl req -x509 -newkey rsa:3072 -nodes -days 3650 -subj "/CN=$(hostname -f)" -addext "subjectAltName=DNS:$(hostname -f),IP:<first ip from hostname -I>"`, only if `fullchain.pem` absent.
  - Final message prints the URL (`https://<domain or first IP>:9443`) and the token from the env file only when `/api/v1/auth/setup/status` returns `"setup_required":true`.

- [ ] **Step 4: Run** pytest and `shellcheck installer/install.sh` — Expected: PASS / no output.

- [ ] **Step 5: Commit** `git commit -m "installer: add fresh install script"`

### Task 4: `installer/uninstall.sh`

**Files:**
- Create: `installer/uninstall.sh`
- Test: `backend/tests/test_installer.py`

**Interfaces:**
- Produces: CLI `uninstall.sh [--purge] [--yes] [--help]`.

- [ ] **Step 1: Write failing tests:** `test_uninstall_help` (returncode 0, mentions `--purge`); `test_uninstall_unknown_option` (returncode 2).

- [ ] **Step 2: Run** — Expected: FAIL.

- [ ] **Step 3: Implement** per spec "Uninstall". Units removed: `dockerforge.service dockerforge-metrics.service dockerforge-backup.{service,timer} dockerforge-data-backup.{service,timer}`. CLIs removed: `dockerforge-backup dockerforge-volume-backup volume-backup.py dockerforge-bind-backup dockerforge-data-backup dockerforge-tls-deploy`. `--purge` prompts `Delete all DockerForge data, config and backups? Type DELETE:` unless `--yes`, then removes the three data dirs and `userdel dockerforge`.

- [ ] **Step 4: Run** pytest and shellcheck — Expected: PASS / no output.

- [ ] **Step 5: Commit** `git commit -m "installer: add uninstall script"`

### Task 5: Distro preflight check, docs

**Files:**
- Modify: `README.md` (add "Fresh install" section with the three commands from the spec, the TLS note, and the 9443 restriction reminder)

- [ ] **Step 1:** If Docker works in this environment, for each image `ubuntu:24.04 debian:12 rockylinux:9 opensuse/leap:15.6`, run `docker run --rm -v "$PWD":/src:ro <image> bash /src/installer/install.sh --check` and record that the detected family is correct (systemd absence is an expected preflight failure). If Docker is unavailable, run the detection test suite only and note this.
- [ ] **Step 2:** Update `README.md`.
- [ ] **Step 3:** Run the full suite `cd backend && python3 -m pytest -q` — Expected: all pass.
- [ ] **Step 4: Commit** `git commit -m "docs: document fresh install"` and push the branch.
