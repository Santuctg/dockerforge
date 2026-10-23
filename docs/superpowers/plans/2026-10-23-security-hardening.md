# Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the known access-control, robustness and deployment gaps before adding new features.

**Architecture:** Small, independent edits to `backend/app/core.py`, `backend/app/ui.py`, installer/restore scripts, systemd units, plus a CI workflow. Each task is one test-first change.

**Tech Stack:** FastAPI, pytest + TestClient, bash, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-23-security-hardening-design.md`

## Global Constraints
- Admin roles = `{'super_admin','admin'}` (`ADMINS`), operator roles = `OPS`.
- Redaction marker is exactly `[REDACTED]` (matches existing `redact()`).
- Rate-limit window 300 s, 5 attempts, cap 10 000 keys.
- All new tests in `backend/tests/test_v0800_security.py` (API/unit) or `backend/tests/test_installer.py` (scripts).

## Review Focus
- Env entry without `=` or with `=` in the value (`A=b=c` → `A=[REDACTED]`).
- `Config` missing or `Config.Env` null in inspect output must not crash.
- Viewer still sees inspect (status, mounts) — only env values hidden.
- `upgrade.sh` must still refuse when not root and keep its rollback.
- Headers present on error responses (401/403), not only 200.

---

### Task 1: Redact env for non-admins (spec 1)
**Files:** Modify `backend/app/core.py` (`inspect_container` route). Test `backend/tests/test_v0800_security.py`.
**Interfaces:** Produces `redact_env(details: dict) -> dict` in `core.py` (returns a copy; no mutation).
- [ ] Tests: viewer gets `['DB_PASSWORD=[REDACTED]','A=[REDACTED]','NOVALUE']` for env `['DB_PASSWORD=s3cret','A=b=c','NOVALUE']`; admin gets raw; inspect without `Config` or with `Env: None` returns 200. Use a FakeProvider monkeypatched into `core.provider`.
- [ ] Run → FAIL. Implement. Run → PASS. Commit.

### Task 2: Logs require Operator (spec 2)
**Files:** `core.py` `container_logs` dependency `READ`→`OPS`; `ui.py` logs tab gate. Test same file.
- [ ] Tests: viewer → 403 on `/api/v1/containers/abc/logs`; operator → 200 (monkeypatch `core.fetch_logs`); `ui.HTML` contains the logs-tab gate `tab==='logs'){\n   if(!canOperate())`-equivalent — assert `"if(!canOperate())content.textContent='Operator permission required.';else await setupLogWorkspace"` in HTML.
- [ ] FAIL → implement → PASS → commit.

### Task 3: Bounded rate-limit state (spec 3)
**Files:** `core.py`: `prune_failed(now: int, cap: int = 10000) -> None`, called at the start of `login`.
- [ ] Tests: entries all older than 300 s removed; recent kept; with cap=3 and 5 keys, the 3 with newest attempts remain.
- [ ] FAIL → implement → PASS → commit.

### Task 4: Security headers (spec 6)
**Files:** `core.py` request middleware; also add to the `HTTPException` handler response.
- [ ] Tests: `/health` and an unauthenticated `/api/v1/auth/session` (401) both carry the three headers with exact values.
- [ ] FAIL → implement → PASS → commit.

### Task 5: Scripts and units (spec 4, 5, 7)
**Files:** `scripts/restore-offline.sh`, `installer/upgrade.sh`, `installer/lib.sh` (receive `stage_backend` moved from `install.sh`), `systemd/dockerforge.service`, `systemd/dockerforge-metrics.service`. Tests in `test_installer.py`.
- [ ] Tests: restore script contains `rm -rf /opt/dockerforge/backend` before the `cp -a "$DIR/backend/."` line; `upgrade.sh` contains `. "$ROOT/installer/lib.sh"` and `stage_backend "$ROOT/backend"`; `stage_backend` callable after sourcing only `lib.sh` (existing stage test switched to `sh()`); both units contain `UMask=0027`.
- [ ] FAIL → implement (in `upgrade.sh` replace `mkdir`+`cp -a` staging with `stage_backend "$ROOT/backend" "$STAGING"`) → PASS; shellcheck on changed scripts clean (upgrade.sh: fix its pre-existing SC2034 `i` by `_`) → commit.

### Task 6: CI workflow (spec 8)
**Files:** `.github/workflows/ci.yml`. Test in `test_installer.py`.
- [ ] Test: workflow has `on:` push and pull_request, `python-version: '3.12'`, `pytest -q`, and `shellcheck -x installer/install.sh installer/lib.sh installer/uninstall.sh installer/tls-deploy-hook.sh`.
- [ ] FAIL → write workflow (actions/checkout@v4, actions/setup-python@v5) → PASS → full suite → commit, push.
