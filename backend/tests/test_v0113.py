import json
from app.monitoring.collector import collect_once,publish_status
from app.monitoring import history

class Provider:
    def __init__(self): self.calls=[]
    def list_containers(self,all=False):
        assert all is False
        return [{'Id':'a'*64},{'Id':'b'*64},{'Id':'a'*64}]

def stat():
    return {'cpu_stats':{},'precpu_stats':{},'memory_stats':{'usage':1024,'limit':4096},'networks':{}}

def test_collect_once_two_containers(tmp_path):
    provider=Provider();db=str(tmp_path/'metrics.db');calls=[]
    def fetch(ident):calls.append(ident);return stat()
    res=collect_once(provider,db,workers=2,fetch=fetch)
    assert (res['running'],res['collected'],res['failed'])==(2,2,0)
    assert res['fresh_samples']==2 and res['cache_hits']==0
    assert sorted(calls)==['a'*64,'b'*64]
    with history._db(db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM container_metrics').fetchone()[0]==2

def test_partial_failure_does_not_discard_success(tmp_path):
    def fetch(ident):
        if ident.startswith('b'):raise RuntimeError('secret: should not leak')
        return stat()
    res=collect_once(Provider(),str(tmp_path/'m.db'),fetch=fetch)
    assert res['collected']==1 and res['failed']==1

def test_atomic_status_permissions(tmp_path):
    state=tmp_path/'state.json'
    publish_status(state,{'state':'ok','last_attempt':123})
    assert json.loads(state.read_text())['last_attempt']==123
    assert state.stat().st_mode & 0o777 == 0o600
    assert not (tmp_path/'state.json.tmp').exists()
