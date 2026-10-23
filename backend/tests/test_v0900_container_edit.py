import pytest
from app.docker.local_provider import LocalDockerProvider


class Transport:
    def __init__(self, response=None):
        self.calls = []
        self.response = response
    def request(self, method, path, **kw):
        self.calls.append((method, path, kw))
        return self.response


def test_provider_edit_operations_are_encoded():
    t = Transport()
    p = LocalDockerProvider(transport=t)
    p.update_container('abc', {'Memory': 1})
    p.rename_container('abc', 'new-name')
    p.connect_network('net1', 'abc')
    p.disconnect_network('net1', 'abc')
    p.inspect_image('nginx:1.27')
    assert t.calls == [
        ('POST', '/containers/abc/update', {'body': {'Memory': 1}}),
        ('POST', '/containers/abc/rename?name=new-name', {}),
        ('POST', '/networks/net1/connect', {'body': {'Container': 'abc'}}),
        ('POST', '/networks/net1/disconnect', {'body': {'Container': 'abc', 'Force': False}}),
        ('GET', '/images/nginx%3A1.27/json', {}),
    ]


def test_provider_edit_operations_validate_ids():
    p = LocalDockerProvider(transport=Transport())
    for call in (lambda: p.update_container('../x', {}), lambda: p.rename_container('abc', 'bad name'),
                 lambda: p.connect_network('net/1', 'abc'), lambda: p.disconnect_network('net1', '../x')):
        with pytest.raises(ValueError):
            call()


# --- Task 2: overlay logic ---
import copy
from app.docker import edit as E

OLD_ID = 'a1b2c3d4e5f6' + '0' * 52
ANON = 'f00d' * 16


def old_details():
    return {
        'Id': OLD_ID, 'Name': '/web',
        'Config': {'Hostname': OLD_ID[:12], 'User': 'app', 'WorkingDir': '/srv', 'Labels': {'team': 'x', 'maintainer': 'nginx'},
                   'Healthcheck': {'Test': ['CMD', 'true']}, 'Env': ['PATH=/usr/bin', 'NGINX_VERSION=1.25', 'API_KEY=k1'],
                   'Cmd': ['nginx', '-g', 'daemon off;'], 'Entrypoint': ['/docker-entrypoint.sh'], 'Image': 'nginx:1.25',
                   'ExposedPorts': {'80/tcp': {}}, 'Volumes': {'/data': {}}},
        'HostConfig': {'Binds': ['/srv/conf:/etc/nginx/conf.d:ro', 'named:/var/lib/x'],
                       'PortBindings': {'80/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8080'}]},
                       'RestartPolicy': {'Name': 'always', 'MaximumRetryCount': 0}, 'Memory': 0, 'NanoCpus': 0,
                       'Privileged': False, 'NetworkMode': 'bridge',
                       'Mounts': [{'Type': 'volume', 'Source': 'named', 'Target': '/var/lib/x'},
                                  {'Type': 'tmpfs', 'Target': '/run'}]},
        'Mounts': [{'Type': 'bind', 'Source': '/srv/conf', 'Destination': '/etc/nginx/conf.d', 'RW': False},
                   {'Type': 'volume', 'Name': 'named', 'Destination': '/var/lib/x', 'RW': True},
                   {'Type': 'volume', 'Name': ANON, 'Destination': '/data', 'RW': True},
                   {'Type': 'tmpfs', 'Destination': '/run'}],
        'NetworkSettings': {'Networks': {'bridge': {}, 'backend': {'Aliases': ['web']}}},
        'State': {'Running': True},
    }


OLD_IMAGE = {'Config': {'Env': ['PATH=/usr/bin', 'NGINX_VERSION=1.25'], 'Cmd': ['nginx', '-g', 'daemon off;'],
                        'Entrypoint': ['/docker-entrypoint.sh'], 'Labels': {'maintainer': 'nginx'}}}


def test_edit_spec_shows_only_user_settings():
    spec = E.edit_spec(old_details(), OLD_IMAGE)
    assert spec['name'] == 'web' and spec['image'] == 'nginx:1.25'
    assert spec['environment'] == {'API_KEY': 'k1'}
    assert spec['command'] is None
    assert spec['port_bindings'] == [{'host_ip': '127.0.0.1', 'host_port': 8080, 'container_port': 80, 'protocol': 'tcp'}]
    assert spec['mounts'] == ['/srv/conf:/etc/nginx/conf.d:ro', 'named:/var/lib/x', f'{ANON}:/data']
    assert spec['restart'] == 'always' and spec['memory_mb'] is None and spec['nano_cpus'] is None
    assert spec['running'] is True and spec['compose_project'] is None


def make_edit(**over):
    spec = E.edit_spec(old_details(), OLD_IMAGE)
    data = {k: spec[k] for k in ('image', 'command', 'environment', 'port_bindings', 'mounts', 'restart', 'memory_mb', 'nano_cpus')}
    data['acknowledge_high_risk'] = True
    data.update(over)
    return E.ContainerEdit(**data)


def test_build_body_overlays_edit_and_keeps_hidden_settings():
    details = old_details()
    body, extra = E.build_create_body(details, OLD_IMAGE, make_edit(image='nginx:1.27', environment={'API_KEY': 'k2'},
                                                                    restart='unless-stopped', memory_mb=256))
    assert body['Image'] == 'nginx:1.27'
    assert body['Env'] == ['API_KEY=k2']
    assert 'Cmd' not in body and 'Entrypoint' not in body
    assert body['User'] == 'app' and body['WorkingDir'] == '/srv' and body['Healthcheck'] == {'Test': ['CMD', 'true']}
    assert body['Labels'] == {'team': 'x'}
    assert 'Hostname' not in body and 'Volumes' not in body
    assert body['ExposedPorts'] == {'80/tcp': {}}
    host = body['HostConfig']
    assert host['Binds'] == ['/srv/conf:/etc/nginx/conf.d:ro', 'named:/var/lib/x', f'{ANON}:/data']
    assert host['Mounts'] == [{'Type': 'tmpfs', 'Target': '/run'}]
    assert host['PortBindings'] == {'80/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8080'}]}
    assert host['RestartPolicy'] == {'Name': 'unless-stopped'}
    assert host['Memory'] == 256 * 1024 * 1024 and host['NanoCpus'] == 0
    assert host['Privileged'] is False and host['NetworkMode'] == 'bridge'
    assert extra == [('backend', {'Aliases': ['web']})]
    assert details == old_details()


def test_build_body_keeps_custom_hostname_and_command():
    details = old_details()
    details['Config']['Hostname'] = 'web-host'
    body, _ = E.build_create_body(details, OLD_IMAGE, make_edit(command=['nginx', '-T']))
    assert body['Hostname'] == 'web-host' and body['Cmd'] == ['nginx', '-T']


def test_mount_validation():
    for bad in (['./rel:/x'], ['/a'], ['vol:/x:zz'], ['vol:relative']):
        with pytest.raises(ValueError):
            make_edit(mounts=bad)
    assert make_edit(mounts=['vol_1:/x:ro', '/host/p:/c']).mounts == ['vol_1:/x:ro', '/host/p:/c']


def test_public_port_requires_ack():
    edit = make_edit(port_bindings=[{'host_ip': '0.0.0.0', 'host_port': 80, 'container_port': 80, 'protocol': 'tcp'}])
    with pytest.raises(ValueError):
        E.build_create_body(old_details(), OLD_IMAGE, edit)
    edit.acknowledge_public_ports = True
    body, _ = E.build_create_body(old_details(), OLD_IMAGE, edit)
    assert body['HostConfig']['PortBindings'] == {'80/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '80'}]}


def test_compose_project_and_high_risk():
    details = old_details()
    assert E.compose_project(details) is None
    details['Config']['Labels']['com.docker.compose.project'] = 'df_shop'
    assert E.compose_project(details) == 'df_shop'
    body, _ = E.build_create_body(old_details(), OLD_IMAGE, make_edit())
    assert E.is_high_risk(body) is True
    body, _ = E.build_create_body(old_details(), OLD_IMAGE, make_edit(mounts=['named:/var/lib/x']))
    assert E.is_high_risk(body) is False
    body['HostConfig']['Privileged'] = True
    assert E.is_high_risk(body) is True


# --- Task 3: recreate / rollback / backups ---
from app.docker.errors import DockerOperationError

NOW = 1792224000  # 2026-10-17T08:00:00Z


class Store:
    def __init__(self): self.rows = {}
    def get(self, name): return self.rows.get(name)
    def put(self, name, new_id, old_id, old_name, ts, restart_policy):
        self.rows[name] = {'new_id': new_id, 'old_id': old_id, 'old_name': old_name, 'created_at': ts, 'restart_policy': restart_policy}
    def delete(self, name): self.rows.pop(name, None)


class FakeDocker:
    def __init__(self):
        self.calls = []
        self.containers = {OLD_ID: old_details()}
        self.images = {'nginx:1.25': OLD_IMAGE, 'nginx:1.27': OLD_IMAGE}
        self.pullable = set()
        self.fail_start = False
        self.exits_after_start = False
        self.fail_rename = False
        self.fail_rename_back = False
        self.fail_stop = False
        self.fail_delete = None
        self.pull_errors = set()
        self.counter = 0

    def _find(self, ident):
        for cid, d in self.containers.items():
            if cid == ident or d['Name'].lstrip('/') == ident: return cid
        raise DockerOperationError('Docker Engine rejected the operation (HTTP 404)')

    def inspect_container(self, ident):
        self.calls.append(('inspect', ident)); return copy.deepcopy(self.containers[self._find(ident)])

    def inspect_image(self, ref):
        self.calls.append(('inspect_image', ref))
        if ref not in self.images: raise DockerOperationError('Docker Engine rejected the operation (HTTP 404)')
        return self.images[ref]

    def pull_image(self, ref):
        self.calls.append(('pull', ref))
        if ref in self.pull_errors: return '{"status":"Pulling"}\n{"error":"pull access denied"}\n'
        if ref in self.pullable: self.images[ref] = OLD_IMAGE
        return '{"status":"Downloaded newer image"}\n'

    def stop_container(self, ident):
        self.calls.append(('stop', ident))
        if self.fail_stop:
            from app.docker.errors import DockerUnavailable
            raise DockerUnavailable()
        self.containers[self._find(ident)]['State']['Running'] = False

    def start_container(self, ident):
        self.calls.append(('start', ident))
        cid = self._find(ident)
        if self.fail_start and cid != OLD_ID: raise DockerOperationError('Docker Engine rejected the operation (HTTP 500)')
        self.containers[cid]['State']['Running'] = not (self.exits_after_start and cid != OLD_ID)

    def rename_container(self, ident, new_name):
        self.calls.append(('rename', ident, new_name))
        if self.fail_rename or (self.fail_rename_back and not new_name.startswith('web-old-')):
            raise DockerOperationError('Docker Engine rejected the operation (HTTP 409)')
        self.containers[self._find(ident)]['Name'] = '/' + new_name

    def create_container(self, name, body):
        self.counter += 1
        cid = f'new{self.counter}'.ljust(64, '0')
        self.calls.append(('create', name, body))
        self.containers[cid] = {'Id': cid, 'Name': '/' + name, 'Config': {k: v for k, v in body.items() if k != 'HostConfig'},
                                'HostConfig': body['HostConfig'], 'State': {'Running': False}, 'Mounts': [], 'NetworkSettings': {'Networks': {}}}
        return {'Id': cid}

    def connect_network(self, network, ident, endpoint=None): self.calls.append(('connect', network, ident, endpoint))

    def update_container(self, ident, body): self.calls.append(('update', ident, body))

    def delete_container(self, ident, *, force=False, remove_volumes=False):
        self.calls.append(('delete', ident, force, remove_volumes))
        if self.fail_delete: raise DockerOperationError(self.fail_delete)
        del self.containers[self._find(ident)]

    def ops(self): return [c[0] for c in self.calls if c[0] not in ('inspect', 'inspect_image')]


BACKUP = 'web-old-20261017T080000Z'


def test_recreate_success_keeps_backup():
    d, store = FakeDocker(), Store()
    result = E.recreate(d, 'web', make_edit(image='nginx:1.27'), store, NOW, settle=0)
    assert d.ops() == ['pull', 'stop', 'update', 'rename', 'create', 'connect', 'start']
    assert ('update', OLD_ID, {'RestartPolicy': {'Name': 'no'}}) in d.calls
    assert ('rename', OLD_ID, BACKUP) in d.calls and ('connect', 'backend', result['id'], {'Aliases': ['web']}) in d.calls
    assert result == {'id': result['id'], 'name': 'web', 'backup': BACKUP}
    assert store.get('web') == {'new_id': result['id'], 'old_id': OLD_ID, 'old_name': BACKUP, 'created_at': NOW,
                                'restart_policy': {'Name': 'always', 'MaximumRetryCount': 0}}
    assert d.containers[result['id']]['State']['Running'] is True


def test_recreate_start_failure_restores_old():
    d, store = FakeDocker(), Store()
    d.fail_start = True
    with pytest.raises(E.EditError) as err:
        E.recreate(d, 'web', make_edit(), store, NOW, settle=0)
    assert err.value.code == 'RECREATE_FAILED' and err.value.status == 502
    assert list(d.containers) == [OLD_ID]
    assert d.containers[OLD_ID]['Name'] == '/web' and d.containers[OLD_ID]['State']['Running'] is True
    assert store.rows == {}


def test_recreate_crash_after_start_restores_old():
    d, store = FakeDocker(), Store()
    d.exits_after_start = True
    with pytest.raises(E.EditError):
        E.recreate(d, 'web', make_edit(), store, NOW, settle=0)
    assert list(d.containers) == [OLD_ID] and d.containers[OLD_ID]['State']['Running'] is True


def test_recreate_missing_image_changes_nothing():
    d, store = FakeDocker(), Store()
    with pytest.raises(E.EditError) as err:
        E.recreate(d, 'web', make_edit(image='nginx:9.9'), store, NOW, settle=0)
    assert err.value.code == 'IMAGE_UNAVAILABLE' and err.value.status == 422
    assert d.ops() == ['pull']


def test_recreate_blocks_compose_containers():
    d = FakeDocker()
    d.containers[OLD_ID]['Config']['Labels']['com.docker.compose.project'] = 'df_shop'
    with pytest.raises(E.EditError) as err:
        E.recreate(d, 'web', make_edit(), Store(), NOW, settle=0)
    assert err.value.code == 'COMPOSE_MANAGED' and err.value.status == 409 and d.ops() == []


def test_recreate_high_risk_needs_ack():
    with pytest.raises(E.EditError) as err:
        E.recreate(FakeDocker(), 'web', make_edit(acknowledge_high_risk=False), Store(), NOW, settle=0)
    assert err.value.code == 'HIGH_RISK_CONFIRMATION_REQUIRED' and err.value.status == 403


def test_recreate_backup_name_taken_fails_before_stop():
    d = FakeDocker()
    other = old_details(); other['Id'] = 'b' * 64; other['Name'] = '/' + BACKUP
    d.containers[other['Id']] = other
    with pytest.raises(E.EditError):
        E.recreate(d, 'web', make_edit(), Store(), NOW, settle=0)
    assert 'stop' not in d.ops()


def test_recreate_rename_failure_restarts_old():
    d = FakeDocker()
    d.fail_rename = True
    with pytest.raises(E.EditError):
        E.recreate(d, 'web', make_edit(), Store(), NOW, settle=0)
    assert d.ops() == ['stop', 'update', 'rename', 'update', 'start'] and d.containers[OLD_ID]['State']['Running'] is True


def test_second_recreate_replaces_previous_backup():
    d, store = FakeDocker(), Store()
    first = E.recreate(d, 'web', make_edit(), store, NOW, settle=0)
    second = E.recreate(d, 'web', make_edit(), store, NOW + 60, settle=0)
    assert ('delete', OLD_ID, True, False) in d.calls
    assert store.get('web')['old_id'] == first['id'] and store.get('web')['new_id'] == second['id']
    assert OLD_ID not in d.containers


def test_rollback_restores_previous_container():
    d, store = FakeDocker(), Store()
    new = E.recreate(d, 'web', make_edit(), store, NOW, settle=0)
    result = E.rollback(d, 'web', store)
    assert result == {'id': OLD_ID, 'name': 'web'}
    assert new['id'] not in d.containers
    assert d.containers[OLD_ID]['Name'] == '/web' and d.containers[OLD_ID]['State']['Running'] is True
    assert store.rows == {}


def test_rollback_without_backup():
    with pytest.raises(E.EditError) as err:
        E.rollback(FakeDocker(), 'web', Store())
    assert err.value.code == 'NO_BACKUP' and err.value.status == 404


def test_rollback_when_backup_container_gone():
    d, store = FakeDocker(), Store()
    E.recreate(d, 'web', make_edit(), store, NOW, settle=0)
    del d.containers[OLD_ID]
    with pytest.raises(E.EditError) as err:
        E.rollback(d, 'web', store)
    assert err.value.status == 409 and store.rows == {}


def test_remove_backup_keeps_volumes():
    d, store = FakeDocker(), Store()
    E.recreate(d, 'web', make_edit(), store, NOW, settle=0)
    assert E.remove_backup(d, 'web', store) == {'removed': BACKUP}
    assert ('delete', OLD_ID, True, False) in d.calls and store.rows == {}


# --- Task 4: API ---
from fastapi.testclient import TestClient
import app.core as core
from app.core import create_app


class ApiDocker(FakeDocker):
    def disconnect_network(self, network, ident): self.calls.append(('disconnect', network, ident))


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_DB', str(tmp_path / 'edit.db'))
    monkeypatch.setenv('DOCKERFORGE_SETUP_TOKEN', 'bootstrap')
    docker = ApiDocker()
    provider_kwargs = []
    monkeypatch.setattr(core, 'provider', lambda **kw: (provider_kwargs.append(kw), docker)[1])
    docker.provider_kwargs = provider_kwargs
    monkeypatch.setattr(core, 'RECREATE_SETTLE', 0)
    app = create_app()
    setup = TestClient(app, base_url='https://testserver')
    assert setup.post('/api/v1/auth/setup', json={'username': 'super1', 'password': 'very-long-password'},
                      headers={'X-Setup-Token': 'bootstrap'}).status_code == 201

    def login(username, password):
        c = TestClient(app, base_url='https://testserver')
        csrf = c.get('/api/v1/auth/csrf').json()['csrf_token']
        r = c.post('/api/v1/auth/login', json={'username': username, 'password': password}, headers={'X-CSRF-Token': csrf})
        assert r.status_code == 200, r.text
        c.headers['X-CSRF-Token'] = r.json()['csrf_token']
        return c

    admin = login('super1', 'very-long-password')

    def as_role(role):
        assert admin.post('/api/v1/users', json={'username': role + '1', 'password': 'role-long-password', 'role': role}).status_code == 201
        return login(role + '1', 'role-long-password')

    return admin, as_role, docker


def edit_body(**over):
    spec = E.edit_spec(old_details(), OLD_IMAGE)
    body = {k: spec[k] for k in ('image', 'command', 'environment', 'port_bindings', 'mounts', 'restart', 'memory_mb', 'nano_cpus')}
    body['acknowledge_high_risk'] = True
    body.update(over)
    return body


EDIT_ROUTES = [('get', '/api/v1/containers/web/edit', None), ('post', '/api/v1/containers/web/resources', {'restart': 'always'}),
               ('post', '/api/v1/containers/web/rename', {'name': 'web2'}), ('post', '/api/v1/containers/web/recreate', edit_body()),
               ('post', '/api/v1/containers/web/rollback', None), ('delete', '/api/v1/containers/web/backup', None),
               ('post', '/api/v1/containers/web/networks/backend/connect', None)]


def test_edit_routes_are_admin_only(api):
    _, as_role, _ = api
    for role in ('viewer', 'operator'):
        client = as_role(role)
        for method, path, body in EDIT_ROUTES:
            r = getattr(client, method)(path, **({'json': body} if body is not None else {}))
            assert r.status_code == 403, (role, path, r.status_code)


def test_edit_writes_need_csrf(api):
    admin, _, _ = api
    admin.headers.pop('X-CSRF-Token')
    assert admin.post('/api/v1/containers/web/rename', json={'name': 'web2'}).status_code == 403


def test_get_edit_spec(api):
    admin, _, _ = api
    data = admin.get('/api/v1/containers/web/edit').json()
    assert data['environment'] == {'API_KEY': 'k1'} and data['backup'] is None and data['compose_project'] is None


def test_recreate_rollback_and_backup_via_api(api):
    admin, _, docker = api
    r = admin.post('/api/v1/containers/web/recreate', json=edit_body(environment={'API_KEY': 'k2'}))
    assert r.status_code == 200, r.text
    new_id = r.json()['id']
    assert admin.get('/api/v1/containers/web/edit').json()['backup']['old_name'].startswith('web-old-')
    assert admin.post('/api/v1/containers/web/rollback').json()['id'] == OLD_ID
    assert new_id not in docker.containers
    assert admin.delete('/api/v1/containers/web/backup').status_code == 404
    actions = [row['action'] for row in admin.get('/api/v1/audit').json()['items']]
    assert 'container.recreate' in actions and 'container.rollback' in actions


def test_recreate_error_maps_to_status(api):
    admin, _, docker = api
    docker.containers[OLD_ID]['Config']['Labels']['com.docker.compose.project'] = 'df_shop'
    r = admin.post('/api/v1/containers/web/recreate', json=edit_body())
    assert r.status_code == 409 and r.json()['error']['code'] == 'COMPOSE_MANAGED'


def test_live_edits_call_docker(api):
    admin, _, docker = api
    assert admin.post('/api/v1/containers/web/resources', json={'memory_mb': 256, 'nano_cpus': 500000000, 'restart': 'always'}).status_code == 200
    assert ('update', 'web', {'RestartPolicy': {'Name': 'always'}, 'Memory': 256 * 1024 * 1024, 'MemorySwap': 512 * 1024 * 1024,
                              'NanoCpus': 500000000, 'CpuQuota': 0, 'CpuPeriod': 0}) in docker.calls
    assert admin.post('/api/v1/containers/web/resources', json={'restart': 'no'}).status_code == 200
    assert docker.calls[-1] == ('update', 'web', {'RestartPolicy': {'Name': 'no'}})
    assert admin.post('/api/v1/containers/web/rename', json={'name': 'web2'}).status_code == 200
    assert ('rename', 'web', 'web2') in docker.calls
    assert admin.post('/api/v1/containers/web2/networks/backend/disconnect').status_code == 200
    assert ('disconnect', 'backend', 'web2') in docker.calls
    assert admin.post('/api/v1/containers/web2/networks/host/connect').status_code == 422


# --- Task 5: UI ---
from app.ui import HTML


def test_ui_has_edit_tab_gated_for_admins():
    assert "['overview','configuration','network','mounts','logs','stats','console','edit','raw']" in HTML
    assert "if(!canAdmin())content.textContent='Admin permission required.';else await setupEditWorkspace(content,id,name);" in HTML


def test_ui_edit_functions_and_endpoints():
    for fn in ('setupEditWorkspace', 'saveResources', 'renameContainer', 'recreateContainer', 'rollbackContainer',
               'removeBackup', 'parsePortLines'):
        assert f'function {fn}(' in HTML, fn
    for path in ("'/edit'", "'/resources'", "'/rename'", "'/recreate'", "'/rollback'", "'/backup'", "'/networks/'"):
        assert path in HTML, path
    assert 'Managed by Compose stack ' in HTML


def test_ui_edit_workspace_uses_text_content_only():
    start = HTML.index('function setupEditWorkspace(')
    end = HTML.index('\n', HTML.index('async function removeBackup('))
    assert 'innerHTML' not in HTML[start:end]


# --- final review fixes ---

def test_recreate_refuses_auto_remove_containers():
    d = FakeDocker()
    d.containers[OLD_ID]['HostConfig']['AutoRemove'] = True
    with pytest.raises(E.EditError) as err:
        E.recreate(d, 'web', make_edit(), Store(), NOW, settle=0)
    assert err.value.code == 'AUTO_REMOVE' and err.value.status == 409 and d.ops() == []


def test_memory_change_resets_swap_and_reservation():
    details = old_details()
    details['HostConfig'].update(Memory=512 * 2**20, MemorySwap=1024 * 2**20, MemoryReservation=400 * 2**20)
    body, _ = E.build_create_body(details, OLD_IMAGE, make_edit(memory_mb=2048))
    assert body['HostConfig']['MemorySwap'] == 0 and body['HostConfig']['MemoryReservation'] == 400 * 2**20
    body, _ = E.build_create_body(details, OLD_IMAGE, make_edit(memory_mb=256))
    assert body['HostConfig']['MemoryReservation'] == 0
    body, _ = E.build_create_body(details, OLD_IMAGE, make_edit(memory_mb=512))
    assert body['HostConfig']['MemorySwap'] == 1024 * 2**20


def test_nano_cpus_clears_cpu_quota():
    details = old_details()
    details['HostConfig'].update(CpuQuota=50000, CpuPeriod=100000)
    body, _ = E.build_create_body(details, OLD_IMAGE, make_edit(nano_cpus=10**9))
    assert (body['HostConfig']['NanoCpus'], body['HostConfig']['CpuQuota'], body['HostConfig']['CpuPeriod']) == (10**9, 0, 0)
    body, _ = E.build_create_body(details, OLD_IMAGE, make_edit())
    assert body['HostConfig']['CpuQuota'] == 50000


def test_failed_recreate_restores_backup_restart_policy():
    d = FakeDocker()
    d.fail_start = True
    with pytest.raises(E.EditError):
        E.recreate(d, 'web', make_edit(), Store(), NOW, settle=0)
    updates = [c for c in d.calls if c[0] == 'update']
    assert updates == [('update', OLD_ID, {'RestartPolicy': {'Name': 'no'}}),
                       ('update', OLD_ID, {'RestartPolicy': {'Name': 'always', 'MaximumRetryCount': 0}})]


def test_rollback_restores_restart_policy():
    d, store = FakeDocker(), Store()
    E.recreate(d, 'web', make_edit(), store, NOW, settle=0)
    E.rollback(d, 'web', store)
    assert d.calls[-2:] == [('update', OLD_ID, {'RestartPolicy': {'Name': 'always', 'MaximumRetryCount': 0}}), ('start', OLD_ID)]


def test_restore_continues_when_delete_of_new_fails():
    d = FakeDocker()
    d.fail_start = True
    d.fail_delete = 'Docker Engine rejected the operation (HTTP 500)'
    with pytest.raises(E.EditError) as err:
        E.recreate(d, 'web', make_edit(), Store(), NOW, settle=0)
    assert err.value.code == 'RECREATE_FAILED'
    assert d.containers[OLD_ID]['Name'] == '/web' and d.containers[OLD_ID]['State']['Running'] is True


def test_restore_failure_is_reported_with_backup_name():
    d = FakeDocker()
    d.fail_start = True
    d.fail_rename_back = True
    with pytest.raises(E.EditError) as err:
        E.recreate(d, 'web', make_edit(), Store(), NOW, settle=0)
    assert err.value.code == 'RESTORE_FAILED' and BACKUP in err.value.message


def test_stop_failure_changes_nothing_else():
    d = FakeDocker()
    d.fail_stop = True
    with pytest.raises(E.EditError) as err:
        E.recreate(d, 'web', make_edit(), Store(), NOW, settle=0)
    assert err.value.code == 'RECREATE_FAILED' and 'rename' not in d.ops() and 'create' not in d.ops()


def test_random_and_ipv6_ports_round_trip():
    details = old_details()
    details['HostConfig']['PortBindings'] = {'80/tcp': [{'HostIp': '', 'HostPort': ''}, {'HostIp': '::', 'HostPort': '8443'}]}
    spec = E.edit_spec(details, OLD_IMAGE)
    assert spec['port_bindings'] == [{'host_ip': '', 'host_port': None, 'container_port': 80, 'protocol': 'tcp'},
                                     {'host_ip': '::', 'host_port': 8443, 'container_port': 80, 'protocol': 'tcp'}]
    body, _ = E.build_create_body(details, OLD_IMAGE, make_edit(port_bindings=spec['port_bindings'], acknowledge_public_ports=True))
    assert body['HostConfig']['PortBindings'] == {'80/tcp': [{'HostIp': '', 'HostPort': ''}, {'HostIp': '::', 'HostPort': '8443'}]}


def test_with_default_tag():
    assert E.with_default_tag('nginx') == 'nginx:latest'
    assert E.with_default_tag('registry:5000/app') == 'registry:5000/app:latest'
    assert E.with_default_tag('nginx:1.27') == 'nginx:1.27'
    assert E.with_default_tag('img@sha256:' + 'a' * 64) == 'img@sha256:' + 'a' * 64


def test_update_image_fails_when_pull_reports_error():
    d = FakeDocker()
    d.pull_errors.add('nginx:1.25')
    with pytest.raises(E.EditError) as err:
        E.recreate(d, 'web', make_edit(pull=True), Store(), NOW, settle=0)
    assert err.value.code == 'IMAGE_UNAVAILABLE' and 'stop' not in d.ops()


def test_pull_adds_latest_tag():
    d = FakeDocker()
    d.images['nginx:latest'] = OLD_IMAGE
    E.recreate(d, 'web', make_edit(image='nginx'), Store(), NOW, settle=0)
    assert ('pull', 'nginx:latest') in d.calls


def test_network_endpoints_are_kept():
    details = old_details()
    details['NetworkSettings']['Networks'] = {
        'bridge': {'Aliases': None, 'MacAddress': '02:42:ac:11:00:02', 'IPAMConfig': None, 'NetworkID': 'n1'},
        'backend': {'Aliases': ['web', OLD_ID[:12]], 'IPAMConfig': {'IPv4Address': '172.20.0.5'}, 'Links': None,
                    'DriverOpts': None, 'NetworkID': 'n2'}}
    body, extra = E.build_create_body(details, OLD_IMAGE, make_edit())
    assert body['NetworkingConfig'] == {'EndpointsConfig': {'bridge': {'MacAddress': '02:42:ac:11:00:02'}}}
    assert extra == [('backend', {'Aliases': ['web'], 'IPAMConfig': {'IPv4Address': '172.20.0.5'}})]
    details['HostConfig']['NetworkMode'] = 'n2'
    body, extra = E.build_create_body(details, OLD_IMAGE, make_edit())
    assert list(body['NetworkingConfig']['EndpointsConfig']) == ['backend'] and [n for n, _ in extra] == ['bridge']


def test_image_default_runtime_settings_follow_new_image():
    image = copy.deepcopy(OLD_IMAGE)
    image['Config'].update(WorkingDir='/srv', Healthcheck={'Test': ['CMD', 'true']}, StopSignal='SIGQUIT')
    details = old_details()
    details['Config']['StopSignal'] = 'SIGQUIT'
    body, _ = E.build_create_body(details, image, make_edit())
    assert 'WorkingDir' not in body and 'Healthcheck' not in body and 'StopSignal' not in body
    assert body['User'] == 'app'


def test_remove_backup_reports_docker_errors():
    d, store = FakeDocker(), Store()
    E.recreate(d, 'web', make_edit(), store, NOW, settle=0)
    d.fail_delete = 'Docker Engine is unavailable'
    with pytest.raises(E.EditError):
        E.remove_backup(d, 'web', store)
    assert store.get('web') is not None
    d.fail_delete = 'Docker Engine rejected the operation (HTTP 404)'
    assert E.remove_backup(d, 'web', store) == {'removed': BACKUP} and store.get('web') is None


def test_recreate_route_uses_long_docker_timeout(api):
    admin, _, docker = api
    assert admin.post('/api/v1/containers/web/recreate', json=edit_body()).status_code == 200
    assert any(kw.get('timeout', 0) >= 300 for kw in docker.provider_kwargs)


def test_edit_spec_route_handles_random_ports(api):
    admin, _, docker = api
    docker.containers[OLD_ID]['HostConfig']['PortBindings'] = {'80/tcp': [{'HostIp': '', 'HostPort': ''}]}
    assert admin.get('/api/v1/containers/web/edit').status_code == 200


# --- UI helpers, run in Node ---
import json as _json
import shutil
import subprocess as _sp


def _js_functions(*names):
    lines = HTML.splitlines()
    return '\n'.join(next(l for l in lines if l.startswith(f'function {n}(')) for n in names)


@pytest.mark.skipif(not shutil.which('node'), reason='node not installed')
def test_ui_edit_helpers_round_trip():
    script = _js_functions('formatCommand', 'parseCommand', 'formatEnv', 'parseEnvLines', 'formatPortLines', 'parsePortLines') + '''
const out = {};
const cmd = ["sh","-c","echo hi && sleep 1d"];
out.cmd = parseCommand(formatCommand(cmd));
out.cmdEmpty = parseCommand('');
try { parseCommand('nginx -g'); out.cmdBad = 'no error' } catch (e) { out.cmdBad = 'error' }
const env = {KEY: "line1\\nline2", Q: '"quoted"', PLAIN: 'a=b c'};
out.env = parseEnvLines(formatEnv(env));
const ports = [{host_ip:'',host_port:null,container_port:80,protocol:'tcp'},{host_ip:'::',host_port:8443,container_port:443,protocol:'tcp'},
               {host_ip:'127.0.0.1',host_port:8080,container_port:80,protocol:'udp'}];
out.ports = parsePortLines(formatPortLines(ports));
out.short = parsePortLines('8080:80');
console.log(JSON.stringify(out));
'''
    result = _sp.run(['node', '-e', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    out = _json.loads(result.stdout)
    assert out['cmd'] == ['sh', '-c', 'echo hi && sleep 1d'] and out['cmdEmpty'] is None and out['cmdBad'] == 'error'
    assert out['env'] == {'KEY': 'line1\nline2', 'Q': '"quoted"', 'PLAIN': 'a=b c'}
    assert out['ports'] == [{'host_ip': '', 'host_port': None, 'container_port': 80, 'protocol': 'tcp'},
                            {'host_ip': '::', 'host_port': 8443, 'container_port': 443, 'protocol': 'tcp'},
                            {'host_ip': '127.0.0.1', 'host_port': 8080, 'container_port': 80, 'protocol': 'udp'}]
    assert out['short'] == [{'host_ip': '127.0.0.1', 'host_port': 8080, 'container_port': 80, 'protocol': 'tcp'}]


def test_ui_live_save_sends_only_changed_limits():
    assert 'memory_mb:memoryChanged()' in HTML and 'nano_cpus:cpusChanged()' in HTML
