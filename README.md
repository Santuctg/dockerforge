# DockerForge R1 v0.9.0 — security hardening

Cumulative release containing the container-edit work (the v0.9.0 test line) and the security-hardening work (the v0.8.0 test line), plus the fixes from the 2026-10-25 security review. The version is unified at 0.9.0 because the tree already contains both feature sets.

This release hardens the panel and fixes the defects found in the v0.7.0 review:

- **CSP with a per-response nonce.** The panel script is the only executable script; inline event-handler attributes were replaced by delegated `data-action` listeners, and responses carry a restrictive `Content-Security-Policy`, `Permissions-Policy`, `nosniff`, `DENY` framing and HSTS.
- **Multi-tab CSRF fixed.** Up to 8 recently issued tokens per session stay valid (`session_csrf` table), so opening a second tab no longer invalidates the first tab's actions. Login still issues a fresh session and token.
- **Firewall closed by default.** The installer no longer publishes 9443/tcp unless `--allow-public` is given; reach the panel through a VPN, SSH tunnel or an existing rule. Port 80 is still opened when Let's Encrypt HTTP-01 is used.
- **Trusted reverse proxies.** Set `DOCKERFORGE_TRUSTED_PROXIES` to comma-separated IPs/CIDRs; the right-most untrusted `X-Forwarded-For` hop becomes the client IP for rate limiting and audit.
- **Bounded audit trail.** Rows older than 180 days are pruned at startup, and the table is capped at 200,000 rows and pruned periodically.
- **Installer/upgrade fixes.** `data-backup.json` is `0640 root:dockerforge` so the Backup Center can read it; `upgrade.sh` reads the version from `pyproject.toml`, refuses downgrades, installs changed dependencies and keeps rollback.
- **Consistent port validation.** Container create now accepts IPv6 and wildcard (`*`/empty) bindings, and port-conflict checks compare parsed addresses instead of raw strings.
- **Collector fixes.** One container inventory call per cycle; paused containers are no longer reported as stopped.
- **Non-Linux host stats.** If `/proc` is unavailable the snapshot falls back to `sysconf`, so the endpoint no longer fails.

Cumulative feature note (v0.7.0): Backup Center sidebar, read-only authenticated API for archive metadata and safe configuration summary, and fixes the v0.6.0 missing `volume-backup.py` helper packaging. No archive downloads, config writes, direct backup execution or restore from the web.

Admin and Super Admin may view metadata; Viewer/Operator receive HTTP 403. Root-only archives are deliberately not made readable to the web service, so the UI may show zero archives. This is not a failure of backup creation. Use CLI `dockerforge-backup`, `dockerforge-volume-backup`, and `dockerforge-bind-backup` for privileged archive operations.

Upgrade: `sudo bash installer/upgrade.sh` from the new release checkout. It backs up databases and backend before restart, refuses downgrades, and keeps existing data backup timers/settings. No Docker volume changes.

## Fresh install

For a new server (Ubuntu/Debian, RHEL/Rocky/AlmaLinux/Fedora, openSUSE/SLES — any systemd Linux with apt, dnf or zypper):

```
git clone https://github.com/Santuctg/dockerforge && cd dockerforge
sudo bash installer/install.sh --domain panel.example.com --email you@example.com   # Let's Encrypt
sudo bash installer/install.sh --domain panel.example.com --email you@example.com --dns cloudflare  # Let's Encrypt via Cloudflare DNS (local IP OK)
sudo bash installer/install.sh                                                     # self-signed, no domain
sudo bash installer/install.sh --allow-public                                      # also open 9443/tcp in the firewall
sudo bash installer/install.sh --check                                             # preflight only
```

The installer installs Python 3.11+, Docker with Compose (asks first; `--yes` to skip the question), creates the `dockerforge` service user, a TLS certificate, and starts the panel on `https://<host>:9443`. It prints a one-time setup token: open the URL, enter the token and create the Super Admin.

By default the firewall is **not** changed to expose the panel; use a VPN, SSH tunnel, or `--allow-public` when 9443/tcp must be reachable from other hosts. `--no-firewall` skips firewall changes entirely.

- Let's Encrypt needs a DNS A record pointing at the server and port 80 reachable; renewals are automatic and restart the panel. Before changing anything the installer checks that the domain resolves to this server's public IP (`--skip-dns-check` to bypass, e.g. behind NAT). Test with `sudo bash installer/install.sh --check --domain <name> --email <address>`.
- Server only reachable on a local IP (LAN)? Point the domain's A record at the local IP in Cloudflare (DNS only) and use `--dns cloudflare`: certbot proves ownership with a DNS TXT record, so no public IP or port 80 is needed. Create a Cloudflare API token with **Zone → DNS → Edit** for that zone only; the installer asks for it once (or reads `CF_API_TOKEN`) and stores it root-only in `/etc/dockerforge/cloudflare.ini`.
- Re-running is safe: database, users, config, setup token and certificates are kept, and the previous version is backed up to `/root/dockerforge-install-backup-<time>`. A failed run restores it.
- `sudo bash installer/uninstall.sh` removes services and code but keeps data; add `--purge` to delete data, config and backups too. Docker and your containers are never touched.
- The `dockerforge` user is in the `docker` group, which is root-equivalent. Restrict port 9443 to trusted IPs or a VPN.
- Behind a reverse proxy, set `DOCKERFORGE_TRUSTED_PROXIES` (for example `127.0.0.1,10.0.0.0/8`) in `/etc/dockerforge/dockerforge.env` so rate limiting and audit logs see the real client address. Only listed proxies are trusted; client-supplied `X-Forwarded-For` prefixes are ignored.
- The panel binds `0.0.0.0:9443` and always requires HTTPS. Keep the host firewall closed, use a private network, and do not expose it directly to the internet without a review of your threat model.

Windows and macOS are not supported (systemd and a Unix Docker socket are required).

## Editing containers

Admins get an **Edit** tab in container details.

- **Live settings** apply immediately without a restart: memory and CPU limits, restart policy, rename, and connect/disconnect networks. Removing a memory limit entirely needs a recreate.
- **Edit & recreate** changes the image/tag, command, environment, ports and mounts. DockerForge keeps every setting the form does not show (labels, user, working dir, healthcheck, privileged/devices, network mode), stops the old container, renames it `<name>-old-<time>`, and starts a new one under the original name. If the new container does not start, or exits within 3 seconds, it is removed and the old one is restored. Volumes, including anonymous ones, stay attached, and data is never deleted.
- **Update image** pulls the image again and recreates with the same settings.
- Form formats:
  - Command is a JSON array (`["sh","-c","echo hi && sleep 1d"]`); leave it empty to use the image default.
  - Environment is one `KEY=value` per line; values with line breaks are written as JSON strings (`KEY="line1\nline2"`).
  - Ports are `[host_ip:]host_port:container_port[/proto]`, where `*` means all interfaces, an empty host port means a random one, and IPv6 goes in brackets (`[::]:443:443`).
- Containers started with `--rm` can't be recreated, because Docker deletes them when they stop.
- The old container is kept, stopped, as a **backup**: **Roll back** brings it back, and **Remove backup** deletes it (volumes are kept). A new recreate replaces the previous backup.
- Containers that belong to a Docker Compose project can't be recreated here. Edit the stack instead, so the next deploy keeps the change. Live settings still work on them.

**Limitations:** no Web backup execution or restore; no root helper; no verified backup state exposed; no encrypted offsite storage. An internal security review is in `docs/security/REVIEW-2026-10-25.md`; an independent external audit has not been performed.
