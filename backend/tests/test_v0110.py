from pathlib import Path
import pytest
from app.stack import compose

def test_error_classification_does_not_leak_secrets():
    assert compose.classify_compose_error('driver failed programming external connectivity: Bind for 127.0.0.1:8094 failed: port is already allocated')=='port_conflict'
    assert compose.classify_compose_error('listen tcp: bind: address already in use')=='port_conflict'
    assert compose.classify_compose_error('permission denied')=='permission'
    assert compose.classify_compose_error('manifest unknown')=='image_unavailable'
    assert compose.classify_compose_error('secret_credential=foo')=='operation'

def test_docker_runner_uses_stack_cwd_and_hides_stderr(monkeypatch,tmp_path):
    calls=[]
    def fake_run(*args,**kwargs):
        calls.append(kwargs)
        class Result:
            returncode=1
            stdout=''
            stderr='Bind for 127.0.0.1:8094 failed: port is already allocated; PASSWORD=secret123'
        return Result()
    monkeypatch.setattr(compose.subprocess,'run',fake_run)
    with pytest.raises(compose.ComposeFailure) as e:
        compose.run_docker(['compose','up'],cwd=tmp_path)
    assert e.value.category=='port_conflict'
    assert 'secret123' not in str(e.value)
    assert calls[0]['cwd']==str(tmp_path)

def test_stack_action_cwd_and_project(monkeypatch,tmp_path):
    root=tmp_path/'stacks'
    folder=root/'demo';folder.mkdir(parents=True)
    (folder/'compose.yaml').write_text('services:\n  web:\n    image: nginx:alpine\n')
    monkeypatch.setattr(compose,'STACK_ROOT',root)
    observed=[]
    monkeypatch.setattr(compose,'run_docker',lambda args,timeout=90,cwd=None:observed.append((args,cwd)) or '')
    assert compose.list_stacks()==[{'name':'demo','project':'df_demo'}]
    assert compose.stack_action('demo','up')['project']=='df_demo'
    assert observed[0][1]==folder
    assert observed[0][0][:3]==['compose','-p','df_demo']
