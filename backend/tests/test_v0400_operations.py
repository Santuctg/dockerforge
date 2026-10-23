from fastapi.testclient import TestClient
from app.core import create_app
import pytest

@pytest.fixture
def admin(tmp_path,monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_DB',str(tmp_path/'app.db'))
    monkeypatch.setenv('DOCKERFORGE_SETUP_TOKEN','bootstrap')
    client=TestClient(create_app(),base_url='https://testserver')
    assert client.post('/api/v1/auth/setup',json={'username':'super1','password':'very-long-password'},headers={'X-Setup-Token':'bootstrap'}).status_code==201
    csrf=client.get('/api/v1/auth/csrf').json()['csrf_token']
    login=client.post('/api/v1/auth/login',json={'username':'super1','password':'very-long-password'},headers={'X-CSRF-Token':csrf})
    assert login.status_code==200
    return client,login.json()['csrf_token']

def test_session_list_and_revocation(admin):
    c,csrf=admin
    headers={'X-CSRF-Token':csrf}
    uid=c.get('/api/v1/users').json()['items'][0]['id']
    result=c.get(f'/api/v1/users/{uid}/sessions')
    assert result.status_code==200
    assert result.json()['count']==1
    assert 'id_hash' not in str(result.json())
    assert c.post(f'/api/v1/users/{uid}/revoke-sessions').status_code==403
    revoked=c.post(f'/api/v1/users/{uid}/revoke-sessions',headers=headers)
    assert revoked.status_code==200 and revoked.json()['revoked']==1
    assert c.get('/api/v1/auth/session').status_code==401

def test_session_missing_user_and_rbac(admin):
    c,csrf=admin
    assert c.get('/api/v1/users/999999/sessions').status_code==404
    assert c.post('/api/v1/users/999999/revoke-sessions',headers={'X-CSRF-Token':csrf}).status_code==404
    uid=c.post('/api/v1/users',json={'username':'viewer1','password':'viewer-password-long','role':'viewer'},headers={'X-CSRF-Token':csrf}).json()['id']
    viewer=TestClient(c.app,base_url='https://testserver')
    x=viewer.get('/api/v1/auth/csrf').json()['csrf_token']
    v=viewer.post('/api/v1/auth/login',json={'username':'viewer1','password':'viewer-password-long'},headers={'X-CSRF-Token':x})
    assert v.status_code==200
    assert viewer.get(f'/api/v1/users/{uid}/sessions').status_code==403
    assert viewer.post(f'/api/v1/users/{uid}/revoke-sessions',headers={'X-CSRF-Token':v.json()['csrf_token']}).status_code==403
