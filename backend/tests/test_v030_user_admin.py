import pytest
from fastapi.testclient import TestClient
from app.core import create_app

@pytest.fixture
def c(tmp_path,monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_DB',str(tmp_path/'users.db'))
    monkeypatch.setenv('DOCKERFORGE_SETUP_TOKEN','bootstrap')
    c=TestClient(create_app(),base_url='https://testserver')
    assert c.post('/api/v1/auth/setup',json={'username':'super1','password':'very-long-password'},headers={'X-Setup-Token':'bootstrap'}).status_code==201
    csrf=c.get('/api/v1/auth/csrf').json()['csrf_token']
    r=c.post('/api/v1/auth/login',json={'username':'super1','password':'very-long-password'},headers={'X-CSRF-Token':csrf})
    assert r.status_code==200,r.text
    return c,r.json()['csrf_token']

def test_user_management_lifecycle(c):
    client,csrf=c; h={'X-CSRF-Token':csrf}
    assert len(client.get('/api/v1/users').json()['items'])==1
    assert client.post('/api/v1/users',json={'username':'user2','password':'new-password-long','role':'viewer'}).status_code==403
    created=client.post('/api/v1/users',json={'username':'user2','password':'new-password-long','role':'viewer'},headers=h)
    assert created.status_code==201,created.text
    uid=created.json()['id']
    assert client.post('/api/v1/users',json={'username':'user2','password':'new-password-long','role':'viewer'},headers=h).status_code==409
    assert client.put(f'/api/v1/users/{uid}/role',json={'role':'operator'},headers=h).status_code==200
    assert client.put(f'/api/v1/users/{uid}/password',json={'password':'another-long-password'},headers=h).status_code==200
    assert client.delete(f'/api/v1/users/{uid}',headers=h).json()['deleted']
    assert client.get('/api/v1/users').json()['items'][0]['username']=='super1'
    assert 'password_hash' not in str(client.get('/api/v1/users').json())

def test_super_admin_safety(c):
    client,csrf=c; h={'X-CSRF-Token':csrf}
    uid=client.get('/api/v1/users').json()['items'][0]['id']
    assert client.delete(f'/api/v1/users/{uid}',headers=h).status_code==409
    assert client.put(f'/api/v1/users/{uid}/role',json={'role':'viewer'},headers=h).status_code==409
    assert client.post('/api/v1/users',json={'username':'hey','password':'secure-long-string','role':'invalid'},headers=h).status_code==422

def test_session_revocation(c):
    client,csrf=c;h={'X-CSRF-Token':csrf}
    uid=client.post('/api/v1/users',json={'username':'operator1','password':'operator-password','role':'operator'},headers=h).json()['id']
    other=TestClient(client.app,base_url='https://testserver')
    token=other.get('/api/v1/auth/csrf').json()['csrf_token']
    login=other.post('/api/v1/auth/login',json={'username':'operator1','password':'operator-password'},headers={'X-CSRF-Token':token})
    assert login.status_code==200
    assert other.get('/api/v1/auth/session').status_code==200
    assert other.get('/api/v1/users').status_code==403
    assert client.put(f'/api/v1/users/{uid}/role',json={'role':'viewer'},headers=h).status_code==200
    assert other.get('/api/v1/auth/session').status_code==401
