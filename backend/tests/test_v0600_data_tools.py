import importlib.util
import json
from pathlib import Path
import pytest

SCRIPTS=Path(__file__).resolve().parents[2]/'scripts'

def module(name,file):
    spec=importlib.util.spec_from_file_location(name,SCRIPTS/file)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def test_bind_requires_allow_root(tmp_path,monkeypatch):
    bind=module('bind_test','bind-backup.py')
    monkeypatch.setattr(bind.os,'geteuid',lambda:0)
    approved=tmp_path/'approved'; approved.mkdir()
    good=approved/'data';good.mkdir()
    class R:returncode=0;stdout=''
    monkeypatch.setattr(bind.subprocess,'run',lambda *args,**kwargs:R())
    assert bind.check_source(good,approved)==good
    other=tmp_path/'outside';other.mkdir()
    with pytest.raises(bind.Failure):bind.check_source(other,approved)

def test_bind_refuses_attached_mount(tmp_path,monkeypatch):
    bind=module('bind_test_2','bind-backup.py')
    monkeypatch.setattr(bind.os,'geteuid',lambda:0)
    approved=tmp_path/'approved';approved.mkdir()
    good=approved/'data';good.mkdir()
    class P:
        returncode=0
        stdout='abc' if False else 'abc\n'
    def fake(args,**kw):
        if args[1]=='ps':return P()
        class I:returncode=0;stdout=json.dumps([{'Mounts':[{'Type':'bind','Source':str(good)}]}])
        return I()
    monkeypatch.setattr(bind.subprocess,'run',fake)
    with pytest.raises(bind.Failure,match='overlaps'):bind.check_source(good,approved)

def test_job_disabled_by_default(tmp_path,monkeypatch):
    job=module('job_test','data-backup-job.py')
    config=tmp_path/'job.json';config.write_text('{"enabled": false, "volumes": ["sample"]}')
    config.chmod(0o600)
    monkeypatch.setattr(job.os,'geteuid',lambda:0)
    monkeypatch.setattr('sys.argv',['backup','--config',str(config)])
    with pytest.raises(RuntimeError,match='disabled'):job.main()
