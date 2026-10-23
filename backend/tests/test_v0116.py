import time
from concurrent.futures import ThreadPoolExecutor
from app.monitoring.history import cached_sample, _db
from app.monitoring.collector import collect_once

ID='c'*64

def stat():
    return {'cpu_stats':{},'precpu_stats':{},'memory_stats':{'usage':1024,'limit':4096},'networks':{}}

def test_force_bypasses_cache(tmp_path):
    path=str(tmp_path/'metrics.db');calls=[]
    def fetch():calls.append(1);return stat()
    first={};second={}
    cached_sample(ID,fetch,path,now=1000,force=True,timings=first)
    cached_sample(ID,fetch,path,now=1001,force=True,timings=second)
    assert len(calls)==2 and not second['cache_hit']
    third={}
    cached_sample(ID,fetch,path,now=1002,timings=third)
    assert len(calls)==2 and third['cache_hit']

def test_parallel_fetch_outside_database_lock(tmp_path):
    from threading import Barrier
    barrier=Barrier(2,timeout=1.5)
    def fetch():barrier.wait();return stat()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(cached_sample,'a'*64,fetch,str(tmp_path/'m.db'),force=True)
        b=pool.submit(cached_sample,'b'*64,fetch,str(tmp_path/'m.db'),force=True)
        a.result();b.result()

def test_collector_reports_per_container_timings(tmp_path):
    class P:
        def list_containers(self,all=False):return [{'Id':'a'*64}]
    result=collect_once(P(),str(tmp_path/'m.db'),fetch=lambda _:stat())
    assert result['fresh_samples']==1
    assert result['cache_hits']==0
    assert result['docker_stats_ms_max']>=0
    assert len(result['container_timings'])==1
    assert len(result['container_timings'][0]['id'])==12
