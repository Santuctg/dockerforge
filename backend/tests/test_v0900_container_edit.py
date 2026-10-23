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
    assert extra == ['backend']
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
    def put(self, name, new_id, old_id, old_name, ts): self.rows[name] = {'new_id': new_id, 'old_id': old_id, 'old_name': old_name, 'created_at': ts}
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
        if ref in self.pullable: self.images[ref] = OLD_IMAGE

    def stop_container(self, ident):
        self.calls.append(('stop', ident)); self.containers[self._find(ident)]['State']['Running'] = False

    def start_container(self, ident):
        self.calls.append(('start', ident))
        cid = self._find(ident)
        if self.fail_start and cid != OLD_ID: raise DockerOperationError('Docker Engine rejected the operation (HTTP 500)')
        self.containers[cid]['State']['Running'] = not (self.exits_after_start and cid != OLD_ID)

    def rename_container(self, ident, new_name):
        self.calls.append(('rename', ident, new_name))
        if self.fail_rename: raise DockerOperationError('Docker Engine rejected the operation (HTTP 409)')
        self.containers[self._find(ident)]['Name'] = '/' + new_name

    def create_container(self, name, body):
        self.counter += 1
        cid = f'new{self.counter}'.ljust(64, '0')
        self.calls.append(('create', name, body))
        self.containers[cid] = {'Id': cid, 'Name': '/' + name, 'Config': {k: v for k, v in body.items() if k != 'HostConfig'},
                                'HostConfig': body['HostConfig'], 'State': {'Running': False}, 'Mounts': [], 'NetworkSettings': {'Networks': {}}}
        return {'Id': cid}

    def connect_network(self, network, ident): self.calls.append(('connect', network, ident))

    def delete_container(self, ident, *, force=False, remove_volumes=False):
        self.calls.append(('delete', ident, force, remove_volumes)); del self.containers[self._find(ident)]

    def ops(self): return [c[0] for c in self.calls if c[0] not in ('inspect', 'inspect_image')]


BACKUP = 'web-old-20261017T080000Z'


def test_recreate_success_keeps_backup():
    d, store = FakeDocker(), Store()
    result = E.recreate(d, 'web', make_edit(image='nginx:1.27'), store, NOW, settle=0)
    assert d.ops() == ['pull', 'stop', 'rename', 'create', 'connect', 'start']
    assert ('rename', OLD_ID, BACKUP) in d.calls and ('connect', 'backend', result['id']) in d.calls
    assert result == {'id': result['id'], 'name': 'web', 'backup': BACKUP}
    assert store.get('web') == {'new_id': result['id'], 'old_id': OLD_ID, 'old_name': BACKUP, 'created_at': NOW}
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
    assert d.ops() == ['stop', 'rename', 'start'] and d.containers[OLD_ID]['State']['Running'] is True


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
    def update_container(self, ident, body): self.calls.append(('update', ident, body))
    def disconnect_network(self, network, ident): self.calls.append(('disconnect', network, ident))


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_DB', str(tmp_path / 'edit.db'))
    monkeypatch.setenv('DOCKERFORGE_SETUP_TOKEN', 'bootstrap')
    docker = ApiDocker()
    monkeypatch.setattr(core, 'provider', lambda: docker)
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
    assert ('update', 'web', {'RestartPolicy': {'Name': 'always'}, 'Memory': 256 * 1024 * 1024, 'MemorySwap': -1, 'NanoCpus': 500000000}) in docker.calls
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
