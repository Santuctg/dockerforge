# Container Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admins can live-edit and safely recreate containers from the web, with automatic rollback and a kept backup.

**Architecture:** Docker calls in `LocalDockerProvider`; pure overlay logic and the recreate/rollback orchestration in a new `backend/app/docker/edit.py` (provider and backup store injected); thin routes in `core.py`; an Edit tab in `ui.py`.

**Tech Stack:** FastAPI, pydantic v2, sqlite, Docker Engine API over the Unix socket, vanilla JS.

**Spec:** `docs/superpowers/specs/2026-10-23-container-edit-design.md`

## Global Constraints
- Admin only (`ADMINS`); writes need `require_csrf`; audit actions `container.resources`, `container.rename`, `container.network_connect`, `container.network_disconnect`, `container.recreate`, `container.rollback`, `container.backup_remove`.
- Backup name `<name>-old-<YYYYMMDDTHHMMSSZ>`; settle check 3 s (injectable, 0 in tests).
- Error codes: `COMPOSE_MANAGED` 409, `IMAGE_UNAVAILABLE` 422, `RECREATE_FAILED` 502, `NO_BACKUP` 404, `INVALID_EDIT` 422, `HIGH_RISK_CONFIRMATION_REQUIRED` 403.
- Never delete volumes (`v=false` always).
- New tests: `backend/tests/test_v0900_container_edit.py`.

## Review Focus
- Old container stopped but rename fails → must restart old and change nothing else.
- Rollback when the old backup container was deleted out-of-band → clear 404/409, no crash.
- Second recreate while a backup exists → previous backup container removed first; DB row replaced.
- Container with `HostConfig.Mounts` (`--mount` style) and anonymous volumes → no duplicate mount points in the create body.
- Name collision: `<name>-old-<stamp>` already exists → fail before stopping.

---

### Task 1: Provider methods
**Files:** `backend/app/docker/local_provider.py`; test file.
**Produces:** `update_container(ident, body: dict)`, `rename_container(ident, new_name)`, `connect_network(network, ident)`, `disconnect_network(network, ident)`, `inspect_image(ref) -> dict`.
- [ ] Test with the `Transport` fake pattern from `test_container_management.py`: exact (method, path, body) for each — `POST /containers/abc/update` body passthrough; `POST /containers/abc/rename?name=new`; `POST /networks/net1/connect` `{'Container':'abc'}`; `POST /networks/net1/disconnect` `{'Container':'abc','Force':False}`; `GET /images/nginx%3A1.27/json`. Invalid ids raise `ValueError`.
- [ ] FAIL → implement (`valid_id` on ids/names, `quote(ref, safe='')`) → PASS → commit.

### Task 2: Overlay logic (pure)
**Files:** create `backend/app/docker/edit.py`.
**Produces:** `class ContainerEdit(BaseModel)` (fields: image, command: list[str]|None, environment: dict[str,str], port_bindings: list[PortBinding], mounts: list[str], restart, memory_mb, nano_cpus, pull: bool=False, acknowledge_public_ports, acknowledge_high_risk); `compose_project(details) -> str|None`; `edit_spec(details, image_details) -> dict`; `build_create_body(details, old_image, edit) -> tuple[dict, list[str]]` (body, extra_networks); `is_high_risk(body) -> bool`.
- [ ] Tests: spec hides image-default env and image-default Cmd; spec lists user env, bindings, mounts (anonymous volume shown as `<volname>:/dst`); body keeps Labels/User/WorkingDir/Healthcheck/Privileged from old; applies new image/env/ports/restart/memory; anonymous + named volumes and binds become `HostConfig.Binds` with no `HostConfig.Mounts`; `Hostname` dropped when it equals old id[:12]; extra networks listed (not the NetworkMode one); mount validation rejects `rel:/x`, `/a`, `vol:/x:zz`; non-localhost port without ack raises `ValueError`.
- [ ] FAIL → implement → PASS → commit.

### Task 3: Recreate / rollback / backup orchestration
**Files:** `edit.py`; backup store in `core.py` (`initialize()` adds the table).
**Consumes:** Task 1 provider methods, Task 2 functions. **Produces:** `recreate(p, ident, edit, store, now: int, settle: float=3.0) -> dict`, `rollback(p, name, store) -> dict`, `remove_backup(p, name, store) -> dict`; `BackupStore` protocol with `get(name)`, `put(name,new_id,old_id,old_name,ts)`, `delete(name)`; exceptions `EditError(code, message, status)`.
- [ ] Tests (FakeProvider recording calls, in-memory store): success path order (pull → inspect_image → stop → rename old → create → connect extra → start → inspect running) and store row; start raises → new removed, old renamed back + started, `RECREATE_FAILED`; started but not running after settle → same rollback; image missing after pull → `IMAGE_UNAVAILABLE`, no stop/rename; Compose label → `COMPOSE_MANAGED`; high-risk without ack → error; backup name collision → error before stop; second recreate removes previous backup container; rollback restores; rollback without row → `NO_BACKUP`; remove_backup deletes with volumes kept.
- [ ] FAIL → implement → PASS → commit.

### Task 4: API routes
**Files:** `core.py` (routes before the generic `/{ident}/{action}`), `SqliteBackupStore` using `conn()`.
- [ ] Tests: viewer/operator 403 on all; missing CSRF 403; admin GET edit returns spec; recreate maps `EditError` to its status/code and audits; resources/rename/network call provider with expected args; `POST /containers/abc/rename` is not swallowed by the generic action route.
- [ ] FAIL → implement → PASS → full suite → commit.

### Task 5: UI Edit tab
**Files:** `ui.py`.
- [ ] Tests on `HTML`: tab list includes `'edit'`; functions `setupEditWorkspace`, `saveResources`, `renameContainer`, `recreateContainer`, `rollbackContainer`, `removeBackup` exist; calls to `'/edit'`, `'/recreate'`, `'/rollback'`, `'/backup'`; Compose message text `Managed by Compose stack`; Edit tab gated by `canAdmin()`. All dynamic text via `textContent`.
- [ ] FAIL → implement → PASS → commit.

### Task 6: Docs and final run
- [ ] README: "Editing containers" section (live edit vs recreate, backup/rollback, Compose rule). Full suite, push.
