import os, tempfile
from fastapi.testclient import TestClient
from app.core import create_app, conn, digest
from app.docker.local_provider import LocalDockerProvider
from app.docker.errors import DockerOperationError

class Transport:
    def __init__(self): self.calls=[]
    def request(self, method, path, **kw):
        self.calls.append((method,path,kw))
        if path.endswith('/json') and method=='GET':return {'Id':'abc','State':{'Status':'running'}}
        if path.endswith('/stats?stream=false'):return {'cpu_stats':{}}
        if method=='POST' and path.startswith('/containers/create'):return {'Id':'created'}
        return None

def test_provider_container_operations_are_encoded():
    t=Transport();p=LocalDockerProvider(transport=t)
    p.inspect_container('abc');p.container_stats('abc');p.start_container('abc');p.stop_container('abc');p.restart_container('abc');p.pause_container('abc');p.unpause_container('abc');p.delete_container('abc');p.create_container('sample',{'Image':'nginx:alpine'})
    assert ('POST','/containers/abc/start',{}) in t.calls
    assert ('DELETE','/containers/abc?force=false&v=false',{}) in t.calls
    assert ('POST','/containers/create?name=sample',{'body':{'Image':'nginx:alpine'}}) in t.calls
    try:p.start_container('../bad');assert False
    except ValueError:pass

def test_read_only_transport_handles_post_json():
    t=Transport();p=LocalDockerProvider(transport=t)
    assert p.create_container('x',{'Image':'alpine'})['Id']=='created'

class FakeProvider:
    def __init__(self):self.calls=[]
    def inspect_container(self, ident):return {'Id':ident}
    def container_stats(self,ident):return {'id':ident}
    def start_container(self,ident):self.calls.append(('start',ident))
    def delete_container(self,ident, **kwargs):self.calls.append(('delete',ident))
    def create_container(self,name,body):self.calls.append(('create',name,body));return {'Id':'new-id'}

def test_route_rejects_viewer_and_csrf_and_records_audit(monkeypatch):
    import app.core as core
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv('DOCKERFORGE_DB',d+'/test.db')
        app=create_app();fake=FakeProvider();monkeypatch.setattr(core,'provider',lambda:fake)
        with conn() as db:
            db.execute("INSERT INTO users(username,password_hash,role,created_at) VALUES('v','x','viewer',0)")
            db.execute("INSERT INTO users(username,password_hash,role,created_at) VALUES('a','x','admin',0)")
            viewer=db.execute("SELECT id FROM users WHERE username='v'").fetchone()[0]
            admin=db.execute("SELECT id FROM users WHERE username='a'").fetchone()[0]
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(digest('viewer-token'),viewer,digest('csrf-v'),9999999999,9999999999,9999999999))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(digest('admin-token'),admin,digest('csrf-a'),9999999999,9999999999,9999999999))
        client=TestClient(app,base_url='https://testserver')
        client.cookies.set('dockerforge_session','viewer-token');client.cookies.set('dockerforge_csrf','csrf-v')
        assert client.post('/api/v1/containers/abc/start',headers={'X-CSRF-Token':'csrf-v'}).status_code==403
        client.cookies.set('dockerforge_session','admin-token');client.cookies.set('dockerforge_csrf','csrf-a')
        assert client.post('/api/v1/containers/abc/start').status_code==403
        resp=client.post('/api/v1/containers/abc/start',headers={'X-CSRF-Token':'csrf-a'})
        assert resp.status_code==200 and fake.calls==[('start','abc')]
        assert client.delete('/api/v1/containers/abc',headers={'X-CSRF-Token':'csrf-a'}).status_code==422
        assert client.request('DELETE','/api/v1/containers/abc',headers={'X-CSRF-Token':'csrf-a'},json={'confirm_name':'abc'}).status_code==200
        with conn() as db:assert db.execute("SELECT COUNT(*) FROM audit WHERE action='container.start'").fetchone()[0]==1

def test_operator_cannot_create_and_admin_must_acknowledge_high_risk(monkeypatch):
    import app.core as core
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv('DOCKERFORGE_DB',d+'/test.db')
        app=create_app();fake=FakeProvider();monkeypatch.setattr(core,'provider',lambda:fake)
        with conn() as db:
            for n,role in [('op','operator'),('admin','admin')]:
                db.execute('INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,0)',(n,'x',role))
                uid=db.execute('SELECT id FROM users WHERE username=?',(n,)).fetchone()[0]
                db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(digest(n),uid,digest('csrf'),9999999999,9999999999,9999999999))
        client=TestClient(app,base_url='https://testserver');client.cookies.set('dockerforge_csrf','csrf')
        headers={'X-CSRF-Token':'csrf'}
        client.cookies.set('dockerforge_session','op')
        assert client.post('/api/v1/containers',json={'name':'sample','image':'alpine'},headers=headers).status_code==403
        client.cookies.set('dockerforge_session','admin')
        assert client.post('/api/v1/containers',json={'name':'sample','image':'alpine','privileged':True},headers=headers).status_code==403
        assert client.post('/api/v1/containers',json={'name':'sample','image':'alpine','privileged':True,'acknowledge_high_risk':True},headers=headers).status_code==201
        assert fake.calls[-1][2]['HostConfig']['Privileged'] is True
