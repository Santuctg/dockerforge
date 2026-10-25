"""Regression tests for the v0.9.0 security-hardening pass."""
import re
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.core as core
from app.core import create_app
from app.docker.containers import CreateContainer, PortBinding, is_public_host_ip
from app.docker.resources import validate_port_availability
from app.monitoring import collector


# --- CSRF: several tabs must not invalidate each other -----------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_DB', str(tmp_path / 'hardening.db'))
    monkeypatch.setenv('DOCKERFORGE_SETUP_TOKEN', 'bootstrap')
    core._failed.clear()
    core._failed_ip.clear()
    c = TestClient(create_app(), base_url='https://testserver')
    assert c.post('/api/v1/auth/setup', json={'username': 'root1', 'password': 'very-long-password'},
                  headers={'X-Setup-Token': 'bootstrap'}).status_code == 201
    csrf = c.get('/api/v1/auth/csrf').json()['csrf_token']
    r = c.post('/api/v1/auth/login', json={'username': 'root1', 'password': 'very-long-password'},
               headers={'X-CSRF-Token': csrf})
    assert r.status_code == 200, r.text
    c.login_csrf = r.json()['csrf_token']
    yield c
    core._failed.clear()
    core._failed_ip.clear()


def _post(client, token):
    # Invalid body is fine (422); only CSRF rejection (403) matters here.
    return client.post('/api/v1/containers', json={}, headers={'X-CSRF-Token': token})


def test_older_token_still_valid_after_another_tab_refreshes_cookie(client):
    old = client.login_csrf
    newer = client.get('/api/v1/auth/csrf').json()['csrf_token']
    assert newer != old
    # The shared browser cookie now holds the newer token; this tab still sends the old one.
    assert client.cookies.get(core.CSRF_COOKIE) == newer
    assert _post(client, old).status_code != 403


def test_unknown_csrf_token_is_rejected(client):
    client.get('/api/v1/auth/csrf')
    assert _post(client, 'not-a-session-token').status_code == 403


def test_csrf_tokens_per_session_are_bounded(client):
    old = client.login_csrf
    for _ in range(core.CSRF_TOKENS_PER_SESSION):
        client.get('/api/v1/auth/csrf')
    # The oldest token has been evicted instead of storing every token forever.
    assert _post(client, old).status_code == 403


def test_login_tabs_share_one_pre_auth_csrf_token(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_DB', str(tmp_path / 'login.db'))
    monkeypatch.setenv('DOCKERFORGE_SETUP_TOKEN', 'bootstrap')
    app = create_app()
    first = TestClient(app, base_url='https://testserver')
    second = TestClient(app, base_url='https://testserver')
    token = first.get('/api/v1/auth/csrf').json()['csrf_token']
    # Tabs share a cookie jar in a real browser; the second tab reuses the same token
    # instead of rotating the cookie.
    second.cookies.set(core.CSRF_COOKIE, token)
    assert second.get('/api/v1/auth/csrf').json()['csrf_token'] == token
    assert first.post('/api/v1/auth/setup',
                      json={'username': 'root1', 'password': 'very-long-password'},
                      headers={'X-Setup-Token': 'bootstrap'}).status_code == 201
    r = first.post('/api/v1/auth/login',
                   json={'username': 'root1', 'password': 'very-long-password'},
                   headers={'X-CSRF-Token': token})
    assert r.status_code == 200, r.text


# --- CSP and escaped UI ------------------------------------------------------

def test_panel_sets_nonce_csp_and_has_no_inline_handlers(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_DB', str(tmp_path / 'csp.db'))
    c = TestClient(create_app(), base_url='https://testserver')
    r = c.get('/')
    assert r.status_code == 200
    policy = r.headers['Content-Security-Policy']
    match = re.search(r"script-src 'nonce-([^']+)'", policy)
    assert match, policy
    assert "object-src 'none'" in policy and "frame-ancestors 'none'" in policy
    assert f'<script nonce="{match.group(1)}">' in r.text
    assert '__CSP_NONCE__' not in r.text
    for attribute in ('onclick="', 'onchange="', 'oninput="', 'onsubmit="'):
        assert attribute not in r.text
    assert 'data-action="navigate"' in r.text


def test_api_responses_get_a_locked_down_default_csp(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_DB', str(tmp_path / 'api.db'))
    c = TestClient(create_app(), base_url='https://testserver')
    r = c.get('/api/v1/auth/setup/status')
    assert r.headers['Content-Security-Policy'].startswith("default-src 'none'")
    assert r.headers['X-Content-Type-Options'] == 'nosniff'
    assert r.headers['X-Frame-Options'] == 'DENY'
    assert 'camera=()' in r.headers['Permissions-Policy']


# --- Trusted reverse proxy client IP ----------------------------------------

def _request(peer, forwarded=None):
    headers = {} if forwarded is None else {'x-forwarded-for': forwarded}
    return SimpleNamespace(client=SimpleNamespace(host=peer) if peer else None, headers=headers)


def test_forwarded_for_is_ignored_from_untrusted_peer(monkeypatch):
    monkeypatch.delenv('DOCKERFORGE_TRUSTED_PROXIES', raising=False)
    assert core.client_ip(_request('198.51.100.7', '203.0.113.9')) == '198.51.100.7'


def test_rightmost_untrusted_hop_is_used_behind_trusted_proxy(monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_TRUSTED_PROXIES', '10.0.0.0/8, 192.0.2.1')
    assert core.client_ip(_request('10.0.0.5', '1.2.3.4, 203.0.113.9, 10.0.0.7')) == '203.0.113.9'
    # A client-supplied prefix cannot impersonate its own address.
    assert core.client_ip(_request('10.0.0.5', '1.2.3.4, 203.0.113.9')) == '203.0.113.9'
    assert core.client_ip(_request('10.0.0.5', 'garbage, 203.0.113.9')) == '203.0.113.9'


def test_unparsable_peer_is_returned_as_is(monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_TRUSTED_PROXIES', '127.0.0.1')
    assert core.client_ip(_request('testclient', '203.0.113.9')) == 'testclient'


# --- Bounded audit trail -----------------------------------------------------

def test_prune_audit_applies_retention_then_row_cap(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_DB', str(tmp_path / 'audit.db'))
    core.initialize()
    now = 1_800_000_000
    with core.conn() as db:
        for i in range(5):
            db.execute('INSERT INTO audit(ts,action,result,metadata) VALUES(?,?,?,?)',
                       (now - 1000 - i, 'test', 'success', '{}'))
        db.execute('INSERT INTO audit(ts,action,result,metadata) VALUES(?,?,?,?)',
                   (now - 200 * 86400, 'test', 'success', '{}'))
    with core.conn() as db:
        core.prune_audit(db, now=now, retention_days=180, max_rows=3)
        assert db.execute('SELECT COUNT(*) FROM audit').fetchone()[0] == 3
        assert db.execute('SELECT MIN(ts) FROM audit').fetchone()[0] >= now - 180 * 86400


# --- Host port bindings ------------------------------------------------------

def test_port_binding_accepts_ipv6_and_wildcards():
    assert PortBinding(host_ip='::1', host_port=1, container_port=2).host_ip == '::1'
    assert PortBinding(host_ip='2001:db8::5', host_port=1, container_port=2).host_ip == '2001:db8::5'
    assert PortBinding(host_ip='', host_port=1, container_port=2).host_ip == ''
    assert PortBinding(host_ip='*', host_port=1, container_port=2).host_ip == ''
    with pytest.raises(ValidationError):
        PortBinding(host_ip='not-an-ip', host_port=1, container_port=2)
    assert is_public_host_ip('::1') is False
    assert is_public_host_ip('127.0.0.1') is False
    assert is_public_host_ip('') is True
    assert is_public_host_ip('::') is True


def test_wildcard_binding_needs_public_acknowledgement():
    payload = CreateContainer(name='web', image='nginx', port_bindings=[
        {'host_ip': '::', 'host_port': 8080, 'container_port': 80}])
    with pytest.raises(ValueError):
        payload.docker_payload()
    acked = CreateContainer(name='web', image='nginx', acknowledge_public_ports=True,
                            port_bindings=[{'host_ip': '::', 'host_port': 8080, 'container_port': 80}])
    assert acked.docker_payload()['HostConfig']['PortBindings']['80/tcp'][0]['HostIp'] == '::'


def test_loopback_ipv6_binding_does_not_need_acknowledgement():
    payload = CreateContainer(name='web', image='nginx', port_bindings=[
        {'host_ip': '::1', 'host_port': 8080, 'container_port': 80}])
    assert payload.docker_payload()['HostConfig']['PortBindings']['80/tcp'][0]['HostIp'] == '::1'


def test_duplicate_wildcard_bindings_are_rejected():
    with pytest.raises(ValueError):
        CreateContainer(name='web', image='nginx', acknowledge_public_ports=True, port_bindings=[
            {'host_ip': '', 'host_port': 8080, 'container_port': 80},
            {'host_ip': '0.0.0.0', 'host_port': 8080, 'container_port': 80},
        ]).docker_payload()


def test_port_availability_compares_ipv6_and_wildcards():
    running = [{'State': 'running', 'Ports': [{'PublicPort': 8080, 'Type': 'tcp', 'IP': '::1'}]}]
    with pytest.raises(ValueError):
        validate_port_availability([{'host_ip': '0:0:0:0:0:0:0:1', 'host_port': 8080}], running)
    wildcard = [{'State': 'running', 'Ports': [{'PublicPort': 8080, 'Type': 'tcp', 'IP': '::'}]}]
    with pytest.raises(ValueError):
        validate_port_availability([{'host_ip': '127.0.0.1', 'host_port': 8080}], wildcard)
    # Different loopback addresses on the same port do not conflict.
    validate_port_availability([{'host_ip': '127.0.0.2', 'host_port': 8080}], running)


# --- Collector ---------------------------------------------------------------

def _stats():
    return {'cpu_stats': {}, 'precpu_stats': {},
            'memory_stats': {'usage': 1024, 'limit': 4096}, 'networks': {}}


def test_collect_once_accepts_prefetched_inventory(tmp_path):
    class Provider:
        def list_containers(self, all=False):
            raise AssertionError('inventory must be fetched once by the caller')

    result = collector.collect_once(Provider(), str(tmp_path / 'm.db'),
                                    running=[{'Id': 'a' * 64}], fetch=lambda _: _stats())
    assert (result['running'], result['collected'], result['failed']) == (1, 1, 0)


def test_inventory_counts_do_not_treat_paused_as_stopped():
    containers = [{'State': 'running'}, {'State': 'paused'}, {'State': 'exited'},
                  {'State': 'dead'}, {'State': 'created'}, {'State': 'restarting'}, None]
    assert collector.inventory_counts(containers) == (3, 1)


# --- Installer regressions ---------------------------------------------------

def test_installer_backup_config_is_readable_by_service_user():
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]
    install = (repo / 'installer' / 'install.sh').read_text()
    upgrade = (repo / 'installer' / 'upgrade.sh').read_text()
    assert 'install -m 0640 -o root -g dockerforge' in install
    assert 'chown root:dockerforge "$CONF/data-backup.json"' in install
    assert 'chown root:dockerforge /etc/dockerforge/data-backup.json' in upgrade
    assert 'install -m 0600 "$ROOT/data-backup.example.json"' not in install


def test_upgrade_reads_version_and_installs_dependencies():
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]
    upgrade = (repo / 'installer' / 'upgrade.sh').read_text()
    assert 'NEW_VERSION=$(sed -n' in upgrade
    assert '[[ $NEW_VERSION = 0.7.0 ]]' not in upgrade
    assert 'Refusing to downgrade' in upgrade
    assert 'pip install --quiet --disable-pip-version-check -r "$reqs"' in upgrade
