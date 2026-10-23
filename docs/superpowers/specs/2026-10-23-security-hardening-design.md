# Security hardening — design

Sub-project 1 of 4 (then container edit, storage, volume file browser).

## Changes

1. **Secrets hidden from non-admins in container inspect.** `GET /api/v1/containers/{id}`:
   for roles other than `super_admin`/`admin`, every `Config.Env` entry `KEY=value`
   becomes `KEY=[REDACTED]` (entries without `=` unchanged). Admins see the raw data.
2. **Container logs need Operator.** `GET /api/v1/containers/{id}/logs` requires
   `super_admin`, `admin` or `operator`; viewers get 403. The UI Logs tab shows
   "Operator permission required." for viewers, like the Console tab.
3. **Bounded login rate-limit state.** On each login attempt, entries in `_failed`
   whose attempts are all older than 300 s are removed. If more than 10 000 keys
   remain, the oldest (by latest attempt) are dropped down to 10 000.
   The 5-attempts/300 s rule is unchanged.
4. **`scripts/restore-offline.sh` replaces the backend.** After the pre-restore
   checkpoint, it empties `/opt/dockerforge/backend` before copying the backup in,
   so files from the newer version cannot remain.
5. **`installer/upgrade.sh` stages like the installer.** `stage_backend` moves from
   `install.sh` to `installer/lib.sh`; `upgrade.sh` sources `lib.sh` and uses it, so
   the deployed code is root-owned and contains no `tests/`, `.pytest_cache`,
   `__pycache__`.
6. **Response headers** on every response: `X-Frame-Options: DENY`,
   `Referrer-Policy: no-referrer`, `Strict-Transport-Security: max-age=31536000`.
7. **`UMask=0027`** in `dockerforge.service` and `dockerforge-metrics.service`.
8. **CI**: `.github/workflows/ci.yml` runs on push and pull request: Python 3.12,
   `pip install` the backend test deps, `pytest -q` in `backend/`, and `shellcheck -x`
   on `installer/install.sh installer/lib.sh installer/uninstall.sh
   installer/tls-deploy-hook.sh` (shellcheck from `shellcheck-py`).

## Testing

Each change gets a test that fails first: API tests with the existing TestClient
pattern for 1, 2, 6; a unit test for the rate-limit pruning (3); a bash test with a
temporary root for `restore-offline.sh` is not practical (hard-coded system paths), so
4 is covered by a test asserting the script removes the backend before copying;
5 by a test that `upgrade.sh` sources `lib.sh` and calls `stage_backend`; 7 by
unit-file assertions; 8 by a test that the workflow file names those commands.
Full suite and shellcheck must stay green.
