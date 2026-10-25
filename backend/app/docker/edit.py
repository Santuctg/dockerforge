"""Edit and recreate existing containers: overlay edits on the old container's settings."""
import copy
import json
import re
import time
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from .containers import IMAGE_RE, is_public_host_ip, normalize_host_ip
from .errors import DockerOperationError

MOUNT_RE = re.compile(r'^(/[^:]+|[A-Za-z0-9][A-Za-z0-9_.-]*):(/[^:]*)(:(ro|rw))?$')
COMPOSE_LABEL = 'com.docker.compose.project'
# Runtime settings an image provides; when the container just inherited them, the new image's apply.
IMAGE_DEFAULTS = ('Entrypoint', 'WorkingDir', 'User', 'Healthcheck', 'StopSignal', 'OnBuild')
ENDPOINT_KEYS = ('IPAMConfig', 'Aliases', 'Links', 'MacAddress', 'DriverOpts')


class EditPortBinding(BaseModel):
    host_ip: str = '127.0.0.1'   # '' = all interfaces (IPv4 and IPv6)
    host_port: int | None = Field(default=None, ge=1, le=65535)   # None = random port
    container_port: int = Field(ge=1, le=65535)
    protocol: Literal['tcp', 'udp', 'sctp'] = 'tcp'

    @field_validator('host_ip')
    @classmethod
    def valid_host_ip(cls, value):
        return normalize_host_ip(value)


class ContainerEdit(BaseModel):
    image: str = Field(min_length=1, max_length=255)
    command: list[str] | None = None
    environment: dict[str, str] = Field(default_factory=dict)
    port_bindings: list[EditPortBinding] = Field(default_factory=list)
    mounts: list[str] = Field(default_factory=list)
    restart: Literal['no', 'always', 'unless-stopped', 'on-failure'] = 'unless-stopped'
    memory_mb: int | None = Field(default=None, ge=16, le=1048576)
    nano_cpus: int | None = Field(default=None, ge=10000000)
    pull: bool = False
    acknowledge_public_ports: bool = False
    acknowledge_high_risk: bool = False

    @field_validator('image')
    @classmethod
    def valid_image(cls, value):
        if not IMAGE_RE.fullmatch(value): raise ValueError('Invalid image reference')
        return value

    @field_validator('environment')
    @classmethod
    def valid_environment(cls, value):
        if any(not k or '=' in k or '\x00' in k + v for k, v in value.items()): raise ValueError('Invalid environment variable')
        return value

    @field_validator('mounts')
    @classmethod
    def valid_mounts(cls, value):
        for mount in value:
            if not MOUNT_RE.fullmatch(mount): raise ValueError('Mounts must be /host/path:/container/path or volume:/container/path, optionally :ro or :rw')
        return value


class EditError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def compose_project(details):
    labels = (details.get('Config') or {}).get('Labels') or {}
    return labels.get(COMPOSE_LABEL)


def with_default_tag(ref):
    """Docker pulls every tag of a repository when none is given; the CLI adds :latest."""
    if '@' in ref or ':' in ref.rsplit('/', 1)[-1]: return ref
    return ref + ':latest'


def _not_found(exc):
    return 'HTTP 404' in str(exc)


def _pull_failed(result):
    for line in str(result or '').splitlines() if not isinstance(result, dict) else [json.dumps(result)]:
        try: item = json.loads(line)
        except ValueError: continue
        if isinstance(item, dict) and (item.get('error') or item.get('errorDetail')): return True
    return False


def _mount_strings(details):
    result = []
    for m in details.get('Mounts') or []:
        if m.get('Type') == 'bind': source = m.get('Source')
        elif m.get('Type') == 'volume': source = m.get('Name')
        else: continue
        result.append(f"{source}:{m.get('Destination')}" + ('' if m.get('RW', True) else ':ro'))
    return result


def _port_bindings(details):
    result = []
    for key, entries in ((details.get('HostConfig') or {}).get('PortBindings') or {}).items():
        port, _, protocol = key.partition('/')
        for entry in entries or []:
            host_port = entry.get('HostPort') or ''
            result.append({'host_ip': entry.get('HostIp') or '', 'host_port': int(host_port) if host_port else None,
                           'container_port': int(port), 'protocol': protocol or 'tcp'})
    return result


def edit_spec(details, image_details):
    """Settings the user chose, without values the image provides by default."""
    config = details.get('Config') or {}
    host = details.get('HostConfig') or {}
    image_config = (image_details or {}).get('Config') or {}
    image_env = set(image_config.get('Env') or [])
    environment = dict(e.split('=', 1) for e in config.get('Env') or [] if '=' in e and e not in image_env)
    command = config.get('Cmd')
    if command == image_config.get('Cmd'): command = None
    memory = host.get('Memory') or 0
    return {'name': (details.get('Name') or '').lstrip('/'), 'image': config.get('Image'),
            'command': command, 'environment': environment, 'port_bindings': _port_bindings(details),
            'mounts': _mount_strings(details), 'restart': (host.get('RestartPolicy') or {}).get('Name') or 'no',
            'memory_mb': memory // (1024 * 1024) if memory else None, 'nano_cpus': host.get('NanoCpus') or None,
            'running': bool((details.get('State') or {}).get('Running')), 'compose_project': compose_project(details)}


def _endpoint(settings, short_id, network):
    endpoint = {k: settings[k] for k in ENDPOINT_KEYS if settings.get(k)}
    aliases = [a for a in endpoint.get('Aliases') or [] if a != short_id]
    if aliases and network != 'bridge': endpoint['Aliases'] = aliases
    else: endpoint.pop('Aliases', None)
    return endpoint


def build_create_body(details, old_image, edit):
    """Return (create body, [(network, endpoint config)] to connect after create)."""
    config = copy.deepcopy(details.get('Config') or {})
    host = copy.deepcopy(details.get('HostConfig') or {})
    old_host = details.get('HostConfig') or {}
    image_config = (old_image or {}).get('Config') or {}
    short_id = (details.get('Id') or '')[:12]
    if config.get('Hostname') == short_id: config.pop('Hostname', None)
    for key in ('Volumes', 'ExposedPorts', 'Env', 'Cmd'): config.pop(key, None)
    for key in IMAGE_DEFAULTS:
        if key in config and config[key] == image_config.get(key): config.pop(key)
    image_labels = image_config.get('Labels') or {}
    config['Labels'] = {k: v for k, v in (config.get('Labels') or {}).items() if image_labels.get(k) != v}
    config['Image'] = edit.image
    config['Env'] = [f'{k}={v}' for k, v in edit.environment.items()]
    if edit.command is not None: config['Cmd'] = edit.command
    bindings, exposed = {}, {}
    for b in edit.port_bindings:
        if is_public_host_ip(b.host_ip) and not edit.acknowledge_public_ports:
            raise ValueError('Non-localhost port exposure requires explicit acknowledgement')
        key = f'{b.container_port}/{b.protocol}'
        exposed[key] = {}
        bindings.setdefault(key, []).append({'HostIp': b.host_ip, 'HostPort': str(b.host_port) if b.host_port else ''})
    config['ExposedPorts'] = exposed
    host['PortBindings'] = bindings
    host['Binds'] = list(edit.mounts)
    # Binds carry every bind/volume mount; keep only other --mount types (tmpfs, ...) to avoid duplicates.
    other = [m for m in host.get('Mounts') or [] if m.get('Type') not in ('bind', 'volume')]
    if other: host['Mounts'] = other
    else: host.pop('Mounts', None)
    host['RestartPolicy'] = {'Name': edit.restart}
    memory = edit.memory_mb * 1024 * 1024 if edit.memory_mb else 0
    if memory != (old_host.get('Memory') or 0):
        # The old swap limit was derived from the old memory limit; let the daemon derive a new one.
        host['MemorySwap'] = 0
        if memory and (host.get('MemoryReservation') or 0) > memory: host['MemoryReservation'] = 0
    host['Memory'] = memory
    host['NanoCpus'] = edit.nano_cpus or 0
    if edit.nano_cpus: host['CpuQuota'] = host['CpuPeriod'] = 0   # Docker rejects NanoCpus together with quota/period
    networks = (details.get('NetworkSettings') or {}).get('Networks') or {}
    mode = host.get('NetworkMode') or 'default'
    mode = 'bridge' if mode == 'default' else mode
    primary = mode if mode in networks else next((n for n, s in networks.items() if (s.get('NetworkID') or '').startswith(mode)), mode)
    if primary in networks:
        body_networks = {'EndpointsConfig': {primary: _endpoint(networks[primary], short_id, primary)}}
    else:
        body_networks = None
    extra = [(n, _endpoint(s, short_id, n)) for n, s in networks.items() if n != primary]
    body = {**config, 'HostConfig': host}
    if body_networks: body['NetworkingConfig'] = body_networks
    return body, extra


def is_high_risk(body):
    host = body.get('HostConfig') or {}
    return bool(host.get('Privileged') or host.get('NetworkMode') == 'host' or host.get('PidMode') == 'host'
                or host.get('Devices') or host.get('CapAdd') or any(b.startswith('/') for b in host.get('Binds') or []))


def _exists(p, ident):
    try:
        p.inspect_container(ident)
        return True
    except DockerOperationError:
        return False


def _set_policy(p, ident, policy):
    try: p.update_container(ident, {'RestartPolicy': policy})
    except DockerOperationError: pass


def recreate(p, ident, edit, store, now, settle=3.0):
    """Replace a container with an edited copy; restore the old one if the new one does not run."""
    details = p.inspect_container(ident)
    if compose_project(details):
        raise EditError('COMPOSE_MANAGED', 'Container is managed by Docker Compose; edit its stack instead', 409)
    if (details.get('HostConfig') or {}).get('AutoRemove'):
        raise EditError('AUTO_REMOVE', 'Container was started with --rm and would be deleted when stopped; it cannot be recreated', 409)
    name, old_id = (details.get('Name') or '').lstrip('/'), details['Id']
    config = details.get('Config') or {}
    policy = (details.get('HostConfig') or {}).get('RestartPolicy') or {'Name': 'no'}
    try: old_image = p.inspect_image(details.get('Image') or config.get('Image'))
    except DockerOperationError: old_image = {}
    try: body, extra = build_create_body(details, old_image, edit)
    except ValueError as exc: raise EditError('INVALID_EDIT', str(exc), 422) from exc
    if is_high_risk(body) and not edit.acknowledge_high_risk:
        raise EditError('HIGH_RISK_CONFIRMATION_REQUIRED', 'Explicit acknowledgement required for host-level Docker options', 403)
    if edit.pull or edit.image != config.get('Image'):
        try: failed = _pull_failed(p.pull_image(with_default_tag(edit.image)))
        except DockerOperationError: failed = True
        if failed and edit.pull: raise EditError('IMAGE_UNAVAILABLE', 'Image could not be pulled', 422)
        try: p.inspect_image(with_default_tag(edit.image))
        except DockerOperationError as exc: raise EditError('IMAGE_UNAVAILABLE', 'Image could not be pulled', 422) from exc
    backup = name[:100] + '-old-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(now))
    if _exists(p, backup): raise EditError('INVALID_EDIT', 'Backup name already in use; retry in a second', 409)
    was_running = bool((details.get('State') or {}).get('Running'))
    if was_running:
        try: p.stop_container(old_id)
        except DockerOperationError as exc:
            raise EditError('RECREATE_FAILED', 'Could not stop the container; nothing else was changed', 502) from exc
    # A stopped backup with restart=always would come back after a daemon restart and fight the new container.
    _set_policy(p, old_id, {'Name': 'no'})
    try:
        p.rename_container(old_id, backup)
    except DockerOperationError as exc:
        _set_policy(p, old_id, policy)
        if was_running: p.start_container(old_id)
        raise EditError('RECREATE_FAILED', 'Could not set the previous container aside; it was restarted', 502) from exc
    new_id = None
    try:
        new_id = p.create_container(name, body)['Id']
        for network, endpoint in extra: p.connect_network(network, new_id, endpoint)
        if was_running:
            p.start_container(new_id)
            if settle: time.sleep(settle)
            state = p.inspect_container(new_id).get('State') or {}
            if not state.get('Running') or state.get('Restarting'): raise RuntimeError('new container is not running')
    except Exception as exc:
        _restore(p, new_id, old_id, name, backup, policy, was_running)
        raise EditError('RECREATE_FAILED', 'New container failed to start; the previous container was restored', 502) from exc
    previous = store.get(name)
    if previous:
        try: p.delete_container(previous['old_id'], force=True, remove_volumes=False)
        except DockerOperationError: pass
    store.put(name, new_id, old_id, backup, now, policy)
    return {'id': new_id, 'name': name, 'backup': backup}


def _restore(p, new_id, old_id, name, backup, policy, was_running):
    """Undo a failed recreate step by step; every step is attempted even if an earlier one fails."""
    if new_id:
        try: p.delete_container(new_id, force=True, remove_volumes=False)
        except DockerOperationError: pass
    try:
        p.rename_container(old_id, name)
    except DockerOperationError as exc:
        raise EditError('RESTORE_FAILED', f'New container failed and the previous one could not be renamed back; it is stopped as {backup}', 502) from exc
    _set_policy(p, old_id, policy)
    if was_running:
        try: p.start_container(old_id)
        except DockerOperationError as exc:
            raise EditError('RESTORE_FAILED', f'Previous container {name} was restored but could not be started', 502) from exc


def rollback(p, name, store):
    row = store.get(name)
    if not row: raise EditError('NO_BACKUP', 'No backup for this container', 404)
    if not _exists(p, row['old_id']):
        store.delete(name)
        raise EditError('NO_BACKUP', 'Backup container no longer exists', 409)
    running = False
    try:
        current = p.inspect_container(name)
        if current['Id'] != row['new_id']:
            raise EditError('INVALID_EDIT', 'Container was replaced since the backup was made', 409)
        running = bool((current.get('State') or {}).get('Running'))
        p.delete_container(current['Id'], force=True, remove_volumes=False)
    except DockerOperationError:
        pass
    p.rename_container(row['old_id'], name)
    _set_policy(p, row['old_id'], row.get('restart_policy') or {'Name': 'no'})
    if running: p.start_container(row['old_id'])
    store.delete(name)
    return {'id': row['old_id'], 'name': name}


def remove_backup(p, name, store):
    row = store.get(name)
    if not row: raise EditError('NO_BACKUP', 'No backup for this container', 404)
    try: p.delete_container(row['old_id'], force=True, remove_volumes=False)
    except DockerOperationError as exc:
        if not _not_found(exc): raise EditError('BACKUP_REMOVE_FAILED', 'Backup container could not be removed', 502) from exc
    store.delete(name)
    return {'removed': row['old_name']}
