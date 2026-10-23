# DockerForge R1 v0.7.0 — Backup Center (read-only)

Cumulative upgrade from v0.6.0.

Includes Backup Center sidebar, read-only authenticated API for archive metadata and safe configuration summary, and fixes the v0.6.0 missing `volume-backup.py` helper packaging. No archive downloads, config writes, direct backup execution or restore from the web.

Admin and Super Admin may view metadata; Viewer/Operator receive HTTP 403. Root-only archives are deliberately not made readable to the web service, so the UI may show zero archives. This is not a failure of backup creation. Use CLI `dockerforge-backup`, `dockerforge-volume-backup`, and `dockerforge-bind-backup` for privileged archive operations.

Installer: `bash /root/v0700/installer/upgrade.sh`. Backs up databases and backend before restart; requires healthy existing v0.6.0. All existing data backup timers/settings kept. No Docker volume changes.

**Limitations:** no Web backup execution or restore; no root helper; no verified backup state exposed; no encrypted offsite storage. Independent security review pending.
