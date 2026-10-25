# Security notice

DockerForge grants high-privilege Docker-host access. The `dockerforge` service user is in the `docker` group, which is effectively root-equivalent on the host.

- **Keep port 9443 private.** The installer does not open 9443/tcp in the firewall unless you pass `--allow-public`. Use a VPN, SSH tunnel or a source-restricted rule. Never expose the panel directly to the internet without a threat-model review.
- **Trusted proxies only.** Set `DOCKERFORGE_TRUSTED_PROXIES` to the comma-separated IPs/CIDRs of your reverse proxies. Client IPs used for rate limiting and audit come from the right-most untrusted `X-Forwarded-For` hop.
- **Protect secrets.** Never commit live database files, `/etc/dockerforge` (env file, Cloudflare token, TLS keys), backup archives or runtime state. The installer keeps these root-owned or `root:dockerforge` with mode `0640`.
- **Backups.** Keep encrypted offsite copies and rehearse restore separately (`scripts/restore-offline.sh` requires explicit downtime confirmation).

## Status

v0.9.0 is a pre-production preview. An internal review dated 2026-10-25 is published at `docs/security/REVIEW-2026-10-25.md`; it is **not** an independent security audit. Known residual risks (host-root equivalent via Docker socket, self-signed TLS default, root-run backup jobs, no MFA) are listed there.

Report suspected vulnerabilities privately to the repository owner rather than in a public issue.
