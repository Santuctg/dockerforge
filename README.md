# DockerForge R1 v0.7.0 — Backup Center (read-only)

Cumulative upgrade from v0.6.0.

Includes Backup Center sidebar, read-only authenticated API for archive metadata and safe configuration summary, and fixes the v0.6.0 missing `volume-backup.py` helper packaging. No archive downloads, config writes, direct backup execution or restore from the web.

Admin and Super Admin may view metadata; Viewer/Operator receive HTTP 403. Root-only archives are deliberately not made readable to the web service, so the UI may show zero archives. This is not a failure of backup creation. Use CLI `dockerforge-backup`, `dockerforge-volume-backup`, and `dockerforge-bind-backup` for privileged archive operations.

Installer: `bash /root/v0700/installer/upgrade.sh`. Backs up databases and backend before restart; requires healthy existing v0.6.0. All existing data backup timers/settings kept. No Docker volume changes.

## Fresh install

For a new server (Ubuntu/Debian, RHEL/Rocky/AlmaLinux/Fedora, openSUSE/SLES — any systemd Linux with apt, dnf or zypper):

```
git clone https://github.com/Santuctg/dockerforge && cd dockerforge
sudo bash installer/install.sh --domain panel.example.com --email you@example.com   # Let's Encrypt
sudo bash installer/install.sh --domain panel.example.com --email you@example.com --dns cloudflare  # Let's Encrypt via Cloudflare DNS (local IP OK)
sudo bash installer/install.sh                                                     # self-signed, no domain
sudo bash installer/install.sh --check                                             # preflight only
```

The installer installs Python 3.11+, Docker with Compose (asks first; `--yes` to skip the question), creates the `dockerforge` service user, a TLS certificate, and starts the panel on `https://<host>:9443`. It prints a one-time setup token: open the URL, enter the token and create the Super Admin.

- Let's Encrypt needs a DNS A record pointing at the server and port 80 reachable; renewals are automatic and restart the panel. Before changing anything the installer checks that the domain resolves to this server's public IP (`--skip-dns-check` to bypass, e.g. behind NAT). Test with `sudo bash installer/install.sh --check --domain <name> --email <address>`.
- Server only reachable on a local IP (LAN)? Point the domain's A record at the local IP in Cloudflare (DNS only) and use `--dns cloudflare`: certbot proves ownership with a DNS TXT record, so no public IP or port 80 is needed. Create a Cloudflare API token with **Zone → DNS → Edit** for that zone only; the installer asks for it once (or reads `CF_API_TOKEN`) and stores it root-only in `/etc/dockerforge/cloudflare.ini`.
- Re-running is safe: database, users, config, setup token and certificates are kept, and the previous version is backed up to `/root/dockerforge-install-backup-<time>`. A failed run restores it.
- `sudo bash installer/uninstall.sh` removes services and code but keeps data; add `--purge` to delete data, config and backups too. Docker and your containers are never touched.
- The `dockerforge` user is in the `docker` group, which is root-equivalent. Restrict port 9443 to trusted IPs or a VPN.

Windows and macOS are not supported (systemd and a Unix Docker socket are required).

**Limitations:** no Web backup execution or restore; no root helper; no verified backup state exposed; no encrypted offsite storage. Independent security review pending.
