import pytest
from app.docker.resources import ImagePull, NetworkCreate, VolumeCreate, safe_resource_name, validate_port_availability

def test_resource_name_validation():
    assert safe_resource_name('my-data_1') == 'my-data_1'
    with pytest.raises(ValueError): safe_resource_name('../etc/passwd')

def test_network_create_rejects_reserved():
    with pytest.raises(ValueError): NetworkCreate(name='bridge')

def test_volume_create_rejects_empty():
    with pytest.raises(ValueError): VolumeCreate(name='')

def test_pull_requires_image_name():
    with pytest.raises(ValueError): ImagePull(image='')

def test_port_conflict_detects_running_host_port():
    containers=[{'State':'running','Names':['/a'],'Ports':[{'IP':'127.0.0.1','PublicPort':8091,'PrivatePort':80,'Type':'tcp'}]}]
    with pytest.raises(ValueError, match='8091'):
        validate_port_availability([{'host_ip':'127.0.0.1','host_port':8091,'protocol':'tcp'}], containers)

def test_port_conflict_public_bind_matches_localhost():
    containers=[{'State':'running','Ports':[{'IP':'0.0.0.0','PublicPort':8091,'Type':'tcp'}]}]
    with pytest.raises(ValueError):
        validate_port_availability([{'host_ip':'127.0.0.1','host_port':8091,'protocol':'tcp'}], containers)

def test_provider_resource_paths_and_payloads():
    from app.docker.local_provider import LocalDockerProvider
    class Transport:
        def __init__(self): self.calls=[]
        def request(self,method,path,**kw):
            self.calls.append((method,path,kw))
            return {'ok':True}
    t=Transport(); p=LocalDockerProvider(transport=t)
    p.pull_image('nginx:alpine');p.create_network('mynet');p.create_volume('myvolume')
    p.delete_network('mynet');p.delete_volume('myvolume');p.delete_image('nginx:alpine')
    assert ('POST','/images/create?fromImage=nginx%3Aalpine',{}) in t.calls
    assert ('POST','/networks/create',{'body':{'Name':'mynet','Driver':'bridge','CheckDuplicate':True}}) in t.calls
    assert ('POST','/volumes/create',{'body':{'Name':'myvolume'}}) in t.calls


def test_resources_require_admin_and_typed_delete(monkeypatch,tmp_path):
    import app.core as core
    from app.core import create_app, conn, digest
    from fastapi.testclient import TestClient
    monkeypatch.setenv('DOCKERFORGE_DB',str(tmp_path/'test.db'))
    class Provider:
        def create_volume(self,name):return {'Name':name}
        def delete_volume(self,name):return None
    fake=Provider();monkeypatch.setattr(core,'provider',lambda:fake)
    app=create_app()
    with conn() as db:
        for name,role in [('viewer','viewer'),('admin','admin')]:
            db.execute('INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,0)',(name,'x',role))
            uid=db.execute('SELECT id FROM users WHERE username=?',(name,)).fetchone()[0]
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(digest(name),uid,digest('csrf'),9999999999,9999999999,9999999999))
    client=TestClient(app,base_url='https://testserver')
    client.cookies.set('dockerforge_csrf','csrf');hdr={'X-CSRF-Token':'csrf'}
    client.cookies.set('dockerforge_session','viewer')
    assert client.post('/api/v1/volumes',json={'name':'demo'},headers=hdr).status_code==403
    client.cookies.set('dockerforge_session','admin')
    assert client.post('/api/v1/volumes',json={'name':'demo'},headers=hdr).status_code==201
    assert client.request('DELETE','/api/v1/volumes/demo',json={'confirm_name':'wrong'},headers=hdr).status_code==409
    assert client.request('DELETE','/api/v1/volumes/demo',json={'confirm_name':'demo'},headers=hdr).status_code==200
