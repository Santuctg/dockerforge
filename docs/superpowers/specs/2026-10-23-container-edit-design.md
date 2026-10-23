# Container edit — design

Sub-project 2 of 4. Admin-only. Every action is audited.

## Live edit (no recreate)
- **Resources**: memory (MiB, 16–1048576 or null), CPU (`nano_cpus` ≥ 10 000 000 or null),
  restart policy (`no|always|unless-stopped|on-failure`) via Docker `POST /containers/{id}/update`.
- **Rename** via `POST /containers/{id}/rename` (name pattern as container create).
- **Networks**: connect/disconnect a container to/from a named network. Built-in
  `host`/`none` cannot be connected this way.
Live edit is allowed on Compose containers too.

## Edit & recreate
Editable: image, command, environment, port bindings, mounts (bind `/src:/dst[:ro|rw]` or
named volume `name:/dst[:ro|rw]`), restart, memory, CPU. Option `pull` pulls the image first
("Update image" = same settings + pull).

The new container is built by **overlaying** the edit on the old container's inspect data,
so settings the form does not show (labels, hostname if user-set, user, working dir,
healthcheck, stop signal, privileged/devices/caps, network mode) are kept. Image-provided
defaults are not frozen into the new container: env entries equal to the old image's env,
and Cmd/Entrypoint equal to the old image's, are dropped so the new image's defaults
apply. Every volume mount — including anonymous ones — is passed as an explicit
`name:/dst` bind so data stays attached. Extra networks are reconnected after create.

Steps: (1) validate; reject Compose containers (label `com.docker.compose.project`) with
409 `COMPOSE_MANAGED`; require `acknowledge_high_risk` if the result is high-risk and
`acknowledge_public_ports` for non-localhost ports; (2) if `pull` or image changed, pull
and confirm the image exists, else 422 `IMAGE_UNAVAILABLE` with nothing changed;
(3) stop old (if running); rename to `<name>-old-<UTCstamp>`; (4) create new under the
original name, reconnect networks, start it if the old one was running; after a 3 s
settle check it must be running; (5) on any failure in (4): remove the new container,
rename old back, start it if it was running, return 502 `RECREATE_FAILED` (old restored);
(6) on success record the backup and return the new id.

## Backups
Table `container_backups(name TEXT PRIMARY KEY, new_id, old_id, old_name, created_at)` —
one backup per container name; a second recreate removes the previous backup container
first. **Roll back**: stop+remove the new container, rename the old one back, start it.
**Remove backup**: delete the old container (never its volumes).

## API (Admin, CSRF for writes)
- `GET  /api/v1/containers/{id}/edit` → editable spec, `compose_project`, `backup`
- `POST /api/v1/containers/{id}/resources`, `/rename`, `/recreate`, `/rollback`
- `POST /api/v1/containers/{id}/networks/{network}/connect|disconnect`
- `DELETE /api/v1/containers/{id}/backup`
Registered before the generic `POST /api/v1/containers/{ident}/{action}` route.

## UI
New **Edit** tab in container details (Admin only): live settings form, "Edit &
recreate" form pre-filled from the spec (or "Managed by Compose stack <x> — edit the stack"
link), "Update image" button, and backup panel with Roll back / Remove backup.

## Testing
Fake provider covering: overlay correctness, image-default stripping, anonymous volume
binds, success, start failure and crash-after-start rollback, pull failure (nothing
changed), Compose block, high-risk ack, backup replace/rollback/remove; API RBAC/CSRF and
route ordering; UI markers. Real Docker verification happens on the owner's server.
