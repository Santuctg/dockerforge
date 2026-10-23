import pytest
from app.monitoring import history


def stat(rx=0,tx=0,cpu=0):
    return {'cpu_stats':{'cpu_usage':{'total_usage':cpu},'system_cpu_usage':1000,'online_cpus':2},
            'precpu_stats':{'cpu_usage':{'total_usage':0},'system_cpu_usage':100},
            'memory_stats':{'usage':1024,'limit':8192,'stats':{}},
            'networks':{'eth0':{'rx_bytes':rx,'tx_bytes':tx}}}

def test_cache_deduplicates_docker_calls(tmp_path):
    db=str(tmp_path/'stats.db'); calls=[]
    def fetch():calls.append(1);return stat(rx=1000)
    assert history.cached_sample('a'*64,fetch,db,now=1000)['network_rx_bps']==0
    assert history.cached_sample('a'*64,fetch,db,now=1002)['network_rx_bps']==0
    assert len(calls)==1
    assert history.query_history('a'*64,'1h',db,now=1002)['sample_count']==1

def test_network_rate_and_counter_reset(tmp_path):
    db=str(tmp_path/'stats.db'); ident='b'*64
    history.cached_sample(ident,lambda:stat(rx=100,tx=50),db,now=2000)
    value=history.cached_sample(ident,lambda:stat(rx=10100,tx=5050),db,now=2010)
    assert value['network_rx_bps']==8000
    assert value['network_tx_bps']==4000
    value=history.cached_sample(ident,lambda:stat(rx=1,tx=1),db,now=2020)
    assert value['network_rx_bps']==0 and value['network_tx_bps']==0

def test_history_aggregates_and_rejects_invalid_window(tmp_path):
    db=str(tmp_path/'stats.db'); ident='c'*64
    for t in (3000,3010,3020):history.cached_sample(ident,lambda:stat(rx=t),db,now=t)
    result=history.query_history(ident,'1h',db,now=3100)
    assert result['sample_count']==3
    assert result['points']
    for item in result['points']:
        assert 'network_rx_bps' in item and 'memory_usage_bytes' in item
    with pytest.raises(ValueError):history.query_history(ident,'ALL',db,now=3100)

def test_seven_day_retention(tmp_path):
    db=str(tmp_path/'stats.db'); ident='d'*64
    history.cached_sample(ident,lambda:stat(),db,now=1000000)
    history.cached_sample(ident,lambda:stat(),db,now=1700000)
    with history._db(db) as con:
        n=con.execute('SELECT count(*) FROM container_metrics WHERE container_id=?',(ident,)).fetchone()[0]
    assert n==1
