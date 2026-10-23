from pathlib import Path
from fastapi.testclient import TestClient
from app.core import create_app


def test_backup_center_authorization_and_listing(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_DB',str(tmp_path/'test.sqlite'))
    monkeypatch.setenv('DOCKERFORGE_SETUP_TOKEN','test-only-bootstrap')
    archive_root=tmp_path/'archives'
    archive_root.mkdir()
    (archive_root/'dockerforge-app-20261023T090000Z.tar.gz').write_bytes(b'test file not real archive')
    (archive_root/'unrelated.tar.gz').write_bytes(b'not listed')
    config=tmp_path/'data.json'
    config.write_text('{"enabled": false,"keep": 7,"volumes":[],"binds":[]}')
    monkeypatch.setenv('DOCKERFORGE_BACKUP_ROOT',str(archive_root))
    monkeypatch.setenv('DOCKERFORGE_DATA_BACKUP_CONFIG',str(config))
    client=TestClient(create_app(),base_url='https://testserver')
    assert client.get('/api/v1/backups/overview').status_code==401
    r=client.post('/api/v1/auth/setup',json={'username':'admin1','password':'secure-long-password'},headers={'X-Setup-Token':'test-only-bootstrap'})
    assert r.status_code==201
    token=client.get('/api/v1/auth/csrf').json()['csrf_token']
    assert client.post('/api/v1/auth/login',json={'username':'admin1','password':'secure-long-password'},headers={'X-CSRF-Token':token}).status_code==200
    data=client.get('/api/v1/backups/overview')
    assert data.status_code==200
    assert data.json()['configuration']['enabled'] is False
    assert data.json()['archive_count']==1
    assert data.json()['archives'][0]['kind']=='application'
    assert not any('test file not real archive' in str(v) for v in data.json().values())
    csrf=client.get('/api/v1/auth/csrf').json()['csrf_token']
    viewer=client.post('/api/v1/users',json={'username':'viewer1','password':'viewer-long-password','role':'viewer'},headers={'X-CSRF-Token':csrf})
    assert viewer.status_code==201
    other=TestClient(client.app,base_url='https://testserver')
    c=other.get('/api/v1/auth/csrf').json()['csrf_token']
    assert other.post('/api/v1/auth/login',json={'username':'viewer1','password':'viewer-long-password'},headers={'X-CSRF-Token':c}).status_code==200
    assert other.get('/api/v1/backups/overview').status_code==403


def test_installer_bundles_helper():
    installer=Path(__file__).resolve().parents[2]/'installer'/'upgrade.sh'
    scripts=Path(__file__).resolve().parents[2]/'scripts'
    assert 'volume-backup.py" /usr/local/sbin/volume-backup.py' in installer.read_text()
    assert (scripts/'volume-backup.py').is_file()
