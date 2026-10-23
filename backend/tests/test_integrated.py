import os
import pytest
from fastapi.testclient import TestClient
from app.core import create_app
@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_DB',str(tmp_path/'test.db'))
    monkeypatch.setenv('DOCKERFORGE_SETUP_TOKEN','bootstrap-secret')
    from app import core
    core._failed.clear()
    return TestClient(create_app(),base_url='https://testserver')
def bootstrap(c):
    assert c.post('/api/v1/auth/setup',json={'username':'rootadmin','password':'correct-horse-battery'},headers={'X-Setup-Token':'bootstrap-secret'}).status_code==201
def test_health_and_errors(client):
    assert client.get('/health').json()['status']=='ok'
    r=client.get('/api/v1/auth/session');assert r.status_code==401 and r.json()['error']['code']=='AUTH_REQUIRED' and r.headers['X-Request-ID']
def test_setup_token_one_time(client):
    body={'username':'rootadmin','password':'correct-horse-battery'}
    assert client.post('/api/v1/auth/setup',json=body).status_code==403
    bootstrap(client)
    assert client.post('/api/v1/auth/setup',json=body,headers={'X-Setup-Token':'bootstrap-secret'}).status_code==403
def test_login_csrf_session_audit_logout(client):
    bootstrap(client)
    assert client.post('/api/v1/auth/login',json={'username':'rootadmin','password':'correct-horse-battery'}).status_code==403
    csrf=client.get('/api/v1/auth/csrf').json()['csrf_token']
    r=client.post('/api/v1/auth/login',json={'username':'rootadmin','password':'correct-horse-battery'},headers={'X-CSRF-Token':csrf})
    assert r.status_code==200,r.text
    assert client.get('/api/v1/auth/session').json()['role']=='super_admin'
    assert len(client.get('/api/v1/audit').json()['items'])>=2
    assert client.post('/api/v1/auth/logout').status_code==403
    assert client.post('/api/v1/auth/logout',headers={'X-CSRF-Token':r.json()['csrf_token']}).status_code==200
    assert client.get('/api/v1/auth/session').status_code==401
def test_no_anonymous_diagnostics(client):
    assert client.get('/api/v1/system/diagnostics').status_code==401
    assert client.get('/api/v1/docker/containers').status_code==401
def test_redaction():
    from app.core import redact
    assert redact({'password':'hello','nested':{'api_key':'abc'},'name':'ok'})=={'password':'[REDACTED]','nested':{'api_key':'[REDACTED]'},'name':'ok'}
