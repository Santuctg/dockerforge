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
