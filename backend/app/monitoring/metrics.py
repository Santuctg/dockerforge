"""Bounded, non-streaming Docker container statistics for dashboard use."""

def _num(value):
    return value if isinstance(value,(int,float)) and not isinstance(value,bool) else 0

def normalize_stats(data):
    """Normalize Docker /containers/{id}/stats?stream=false; no container secrets returned."""
    cpu=data.get('cpu_stats') or {}
    previous=data.get('precpu_stats') or {}
    total=_num((cpu.get('cpu_usage') or {}).get('total_usage'))
    old=_num((previous.get('cpu_usage') or {}).get('total_usage'))
    system=_num(cpu.get('system_cpu_usage'))-_num(previous.get('system_cpu_usage'))
    online=_num(cpu.get('online_cpus')) or len((cpu.get('cpu_usage') or {}).get('percpu_usage') or []) or 1
    percent=round(max(0,(total-old)/system*online*100),2) if system>0 and total>=old else 0.0
    memory=data.get('memory_stats') or {}
    raw=_num(memory.get('usage'))
    cache=_num((memory.get('stats') or {}).get('inactive_file', (memory.get('stats') or {}).get('total_inactive_file',0)))
    usage=max(0,raw-cache)
    limit=_num(memory.get('limit'))
    net=data.get('networks') or {}
    rx=sum(_num(n.get('rx_bytes')) for n in net.values() if isinstance(n,dict))
    tx=sum(_num(n.get('tx_bytes')) for n in net.values() if isinstance(n,dict))
    return {'cpu_percent':min(percent,100*max(1,online)), 'memory_usage_bytes':usage,'memory_limit_bytes':limit,'memory_percent':round(usage/limit*100,2) if limit>0 else 0.0,'network_rx_bytes':rx,'network_tx_bytes':tx,'read':data.get('read')}
