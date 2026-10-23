from app.monitoring.metrics import normalize_stats

def test_stats_normalization():
    value=normalize_stats({'cpu_stats':{'cpu_usage':{'total_usage':200},'system_cpu_usage':2000,'online_cpus':2},'precpu_stats':{'cpu_usage':{'total_usage':100},'system_cpu_usage':1000},'memory_stats':{'usage':1100,'limit':2000,'stats':{'inactive_file':100}},'networks':{'eth0':{'rx_bytes':22,'tx_bytes':44},'eth1':{'rx_bytes':3,'tx_bytes':6}}})
    assert value['cpu_percent']==20
    assert value['memory_usage_bytes']==1000
    assert value['memory_percent']==50
    assert value['network_rx_bytes']==25
    assert value['network_tx_bytes']==50

def test_empty_stats():
    value=normalize_stats({})
    assert value['cpu_percent']==0
    assert value['memory_percent']==0
    assert value['network_rx_bytes']==0

def test_host_does_not_expose_raw_details():
    value=normalize_stats({'token':'secret','networks':{'eth0':{'rx_bytes':5,'sensitive':'private'}}})
    assert 'token' not in value
    assert 'networks' not in value
