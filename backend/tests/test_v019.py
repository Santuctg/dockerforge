import pytest
from app.stack.compose import StackDefinition, stack_name
from app.stack.container_tools import ExecCommand, execute, logs

def test_stack_name_rejects_traversal():
    assert stack_name('project_1') == 'project_1'
    for bad in ('../etc', 'AA', '/tmp/pwn', '.hidden'):
        with pytest.raises(ValueError):stack_name(bad)

def test_stack_body_bounds():
    with pytest.raises(Exception):StackDefinition(name='ok',yaml='short',acknowledge_host_risk=True)

def test_exec_argv_not_shell(monkeypatch):
    calls=[]
    def fake_run(args,**kwargs):
        calls.append(args)
        class R: returncode=0; stdout=b'uid=1000\n'; stderr=b''
        return R()
    monkeypatch.setattr('app.stack.container_tools.subprocess.run',fake_run)
    out=execute('demo',ExecCommand(argv=['id','--user']))
    assert out['output']=='uid=1000\n'
    assert calls[0]==['docker','exec','--','demo','id','--user']

def test_logs_bounds(monkeypatch):
    with pytest.raises(ValueError):logs('demo',tail=1001)
    with pytest.raises(ValueError):logs('../bad')

def test_exec_rejects_nul():
    with pytest.raises(ValueError):execute('demo',ExecCommand(argv=['a\x00b']))

def test_compose_validation_and_typed_permissions(monkeypatch,tmp_path):
    import app.core as core
    import app.stack.compose as compose
    from app.core import conn,create_app,digest
    from fastapi.testclient import TestClient
    monkeypatch.setenv('DOCKERFORGE_DB',str(tmp_path/'db.sqlite'))
    monkeypatch.setattr(compose,'STACK_ROOT',tmp_path/'stacks')
    calls=[]
    monkeypatch.setattr(compose,'run_docker',lambda args,timeout=90,cwd=None:calls.append(args) or '')
    app=create_app()
    with conn() as db:
        for name,role in [('viewer','viewer'),('admin','admin')]:
            db.execute('INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,0)',(name,'hash',role))
            uid=db.execute('SELECT id FROM users WHERE username=?',(name,)).fetchone()[0]
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(digest(name),uid,digest('csrf'),9999999999,9999999999,9999999999))
    client=TestClient(app,base_url='https://testserver')
    client.cookies.set('dockerforge_csrf','csrf'); headers={'X-CSRF-Token':'csrf'}
    body={'name':'demo','yaml':'services:\n  web:\n    image: nginx:alpine\n','acknowledge_host_risk':True}
    client.cookies.set('dockerforge_session','viewer')
    assert client.post('/api/v1/stacks',json=body,headers=headers).status_code==403
    client.cookies.set('dockerforge_session','admin')
    assert client.post('/api/v1/stacks',json={**body,'acknowledge_host_risk':False},headers=headers).status_code==403
    assert client.post('/api/v1/stacks',json=body,headers=headers).status_code==201
    assert (tmp_path/'stacks'/'demo'/'compose.yaml').exists()
    assert client.post('/api/v1/stacks',json=body,headers=headers).status_code==409
    assert client.get('/api/v1/stacks').json()['items']==[{'name':'demo','project':'df_demo'}]
    assert client.post('/api/v1/stacks/demo/up',headers=headers).status_code==200
    assert ['compose','-p','df_demo','-f',str(tmp_path/'stacks'/'demo'/'compose.yaml'),'up','-d','--remove-orphans'] in calls
    assert client.post('/api/v1/stacks/demo/whatever',headers=headers).status_code==404

def test_exec_role_and_risk_gate(monkeypatch,tmp_path):
    import app.core as core
    from app.core import create_app,conn,digest
    from fastapi.testclient import TestClient
    monkeypatch.setenv('DOCKERFORGE_DB',str(tmp_path/'db'))
    class P:
        def inspect_container(self,ident):return {'HostConfig':{'Privileged':True}}
    monkeypatch.setattr(core,'provider',lambda:P())
    monkeypatch.setattr(core,'exec_container',lambda name,body:{'output':'ok'})
    app=create_app()
    with conn() as db:
        for name,role in [('operator','operator'),('admin','admin')]:
            db.execute('INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,0)',(name,'hash',role))
            uid=db.execute('SELECT id FROM users WHERE username=?',(name,)).fetchone()[0]
            db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(digest(name),uid,digest('csrf'),9999999999,9999999999,9999999999))
    client=TestClient(app,base_url='https://testserver');client.cookies.set('dockerforge_csrf','csrf')
    headers={'X-CSRF-Token':'csrf'}
    client.cookies.set('dockerforge_session','operator')
    assert client.post('/api/v1/containers/demo/exec',json={'argv':['id']},headers=headers).status_code==403
    client.cookies.set('dockerforge_session','admin')
    assert client.post('/api/v1/containers/demo/exec',json={'argv':['id']},headers=headers).status_code==200
