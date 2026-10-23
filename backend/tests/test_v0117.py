import sqlite3
import time
import pytest
from app.monitoring import collector, history

def test_allowed_intervals():
    for n in (1,2,5,10): assert collector.configured_interval(str(n))==float(n)
    for n in ('0','3','nan','600','bad'):
        with pytest.raises(ValueError): collector.configured_interval(n)

def test_alerts():
    status={'overrun':True,'failed':1,'stopped':2,'container_timings':[{'id':'abc','cpu_percent':95,'memory_percent':96}]}
    assert {x['type'] for x in collector.classify_alerts(status)}=={'collector_overrun','collection_failure','cpu_high','memory_high','container_stopped'}

def test_rollup_and_query(tmp_path):
    path=str(tmp_path/'metrics.db')
    now=int(time.time())
    raw={'cpu_stats':{'cpu_usage':{'total_usage':0}},'precpu_stats':{'cpu_usage':{'total_usage':0}},'memory_stats':{'usage':1024,'limit':2048},'networks':{}}
    history.cached_sample('a'*64,lambda:raw,path,now=now,force=True)
    history.cached_sample('a'*64,lambda:raw,path,now=now+5,force=True)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT SUM(samples) FROM container_metrics_hourly').fetchone()[0]==2
    for window in ('30d','90d'):
        result=history.query_history('a'*64,window,path,now=now+8)
        assert result['sample_count']==2
        assert result['points']
