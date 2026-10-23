import pytest
from fastapi.testclient import TestClient
import app.core as core
from app.core import create_app

ENV = ['DB_PASSWORD=s3cret', 'A=b=c', 'NOVALUE']


class FakeProvider:
    details = {'Id': 'abc', 'Config': {'Env': list(ENV), 'Image': 'nginx'}, 'HostConfig': {}}
    def inspect_container(self, ident):
        import copy
        return copy.deepcopy(self.details)


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_DB', str(tmp_path / 'sec.db'))
    monkeypatch.setenv('DOCKERFORGE_SETUP_TOKEN', 'bootstrap')
    core._failed.clear()
    monkeypatch.setattr(core, 'provider', lambda: FakeProvider())
    admin = TestClient(create_app(), base_url='https://testserver')
    assert admin.post('/api/v1/auth/setup', json={'username': 'super1', 'password': 'very-long-password'},
                      headers={'X-Setup-Token': 'bootstrap'}).status_code == 201

    def login(username, password):
        c = TestClient(admin.app, base_url='https://testserver')
        csrf = c.get('/api/v1/auth/csrf').json()['csrf_token']
        r = c.post('/api/v1/auth/login', json={'username': username, 'password': password}, headers={'X-CSRF-Token': csrf})
        assert r.status_code == 200, r.text
        return c, r.json()['csrf_token']

    super_client, csrf = login('super1', 'very-long-password')

    def as_role(role):
        name = role + '1'
        r = super_client.post('/api/v1/users', json={'username': name, 'password': 'role-long-password', 'role': role},
                              headers={'X-CSRF-Token': csrf})
        assert r.status_code == 201, r.text
        return login(name, 'role-long-password')[0]

    return super_client, as_role


def test_inspect_redacts_env_for_viewer(make_client):
    _, as_role = make_client
    viewer = as_role('viewer')
    data = viewer.get('/api/v1/containers/abc').json()
    assert data['Config']['Env'] == ['DB_PASSWORD=[REDACTED]', 'A=[REDACTED]', 'NOVALUE']
    assert data['Config']['Image'] == 'nginx'


def test_inspect_redacts_env_for_operator(make_client):
    _, as_role = make_client
    assert as_role('operator').get('/api/v1/containers/abc').json()['Config']['Env'][0] == 'DB_PASSWORD=[REDACTED]'


def test_inspect_raw_for_admin(make_client):
    super_client, as_role = make_client
    assert super_client.get('/api/v1/containers/abc').json()['Config']['Env'] == ENV
    assert as_role('admin').get('/api/v1/containers/abc').json()['Config']['Env'] == ENV


def test_inspect_without_env_ok(make_client, monkeypatch):
    _, as_role = make_client
    viewer = as_role('viewer')
    for details in ({'Id': 'abc'}, {'Id': 'abc', 'Config': {'Env': None}}):
        monkeypatch.setattr(FakeProvider, 'details', details)
        assert viewer.get('/api/v1/containers/abc').status_code == 200


def test_logs_forbidden_for_viewer(make_client, monkeypatch):
    _, as_role = make_client
    monkeypatch.setattr(core, 'fetch_logs', lambda ident, tail, ts: {'output': 'secret line', 'truncated': False})
    r = as_role('viewer').get('/api/v1/containers/abc/logs')
    assert r.status_code == 403
    assert 'secret line' not in r.text


def test_logs_allowed_for_operator(make_client, monkeypatch):
    _, as_role = make_client
    monkeypatch.setattr(core, 'fetch_logs', lambda ident, tail, ts: {'output': 'line', 'truncated': False})
    assert as_role('operator').get('/api/v1/containers/abc/logs').json()['output'] == 'line'


def test_ui_hides_logs_tab_from_viewers():
    from app.ui import HTML
    assert "if(!canOperate())content.textContent='Operator permission required.';else await setupLogWorkspace(content,id);" in HTML
