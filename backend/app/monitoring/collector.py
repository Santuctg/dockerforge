"""DockerForge single-host continuous collector. Run as dockerforge systemd user."""
import json
import logging
import os
import signal
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from app.docker.local_provider import LocalDockerProvider
from app.monitoring.history import cached_sample
from app.monitoring.alert_rules import reconcile

LOG = logging.getLogger('dockerforge.metrics')
RUNNING = True
ALLOWED_INTERVALS = (1.0, 2.0, 5.0, 10.0)
def configured_interval(value=None):
    try: interval=float(value if value is not None else os.environ.get('DOCKERFORGE_METRICS_INTERVAL','5'))
    except (ValueError,TypeError): raise ValueError('Invalid DockerForge metrics interval')
    if interval not in ALLOWED_INTERVALS: raise ValueError('Allowed sampling intervals: 1, 2, 5, 10 seconds')
    return interval
INTERVAL = 5.0
MAX_WORKERS = 4

def stop(*_):
    global RUNNING
    RUNNING = False

def collect_once(provider, db_path, workers=MAX_WORKERS, fetch=None):
    """Bounded worker pool. Failures do not abort the entire sampling cycle."""
    running = provider.list_containers(all=False)
    ids = [item.get('Id') for item in running if isinstance(item,dict) and item.get('Id')]
    ids = list(dict.fromkeys(ids))
    fetch = fetch or provider.container_stats
    ok, errors = 0, 0
    timings=[]
    if ids:
        with ThreadPoolExecutor(max_workers=min(workers,len(ids))) as pool:
            def sample(ident):
                timing={}
                metrics=cached_sample(ident,lambda: fetch(ident),db_path,force=True,timings=timing)
                timing['cpu_percent']=metrics.get('cpu_percent',0)
                timing['memory_percent']=metrics.get('memory_percent',0)
                return {'id':ident[:12], 'full_id':ident, **timing}
            tasks = [pool.submit(sample, ident) for ident in ids]
            for future in as_completed(tasks):
                try:
                    timings.append(future.result()); ok += 1
                except Exception as exc:
                    errors += 1
                    LOG.warning('container sample failed: %s', type(exc).__name__)
    return {'running':len(ids), 'collected':ok,'failed':errors,
            'fresh_samples':sum(not t['cache_hit'] for t in timings),
            'cache_hits':sum(t['cache_hit'] for t in timings),
            'docker_stats_ms_max':max((t['docker_stats_ms'] for t in timings),default=0.0),
            'sqlite_write_ms_max':max((t['sqlite_write_ms'] for t in timings),default=0.0),
            'container_timings':sorted(timings,key=lambda t:t['id'])}

def publish_status(path, payload):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(payload),encoding='utf-8')
    tmp.chmod(0o600)
    os.replace(tmp,path)

def classify_alerts(status, *, cpu_threshold=90, memory_threshold=90):
    alerts=[]
    if status.get('overrun'): alerts.append({'type':'collector_overrun','severity':'warning'})
    if status.get('failed',0): alerts.append({'type':'collection_failure','severity':'warning','count':status['failed']})
    if status.get('stopped',0): alerts.append({'type':'container_stopped','severity':'info','count':status['stopped']})
    for item in status.get('container_timings',[]):
        if item.get('cpu_percent',0)>=cpu_threshold:
            alerts.append({'type':'cpu_high','severity':'warning','container':item['id']})
        if item.get('memory_percent',0)>=memory_threshold:
            alerts.append({'type':'memory_high','severity':'warning','container':item['id']})
    return alerts

def main():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    db=os.environ.get('DOCKERFORGE_METRICS_DB','/var/lib/dockerforge/metrics.db')
    state=os.environ.get('DOCKERFORGE_METRICS_STATUS','/var/lib/dockerforge/metrics-collector.json')
    provider=LocalDockerProvider(os.environ.get('DOCKERFORGE_DOCKER_SOCKET','/var/run/docker.sock'),timeout=4.0)
    interval=configured_interval()
    next_run=time.monotonic()
    while RUNNING:
        cycle_started=time.monotonic()
        status={'last_attempt':int(time.time()),'last_success':None,'state':'error'}
        try:
            previous={}
            try: previous=json.loads(Path(state).read_text())
            except (OSError,ValueError): pass
            status['last_success']=previous.get('last_success')
            result=collect_once(provider,db)
            status.update(result)
            try:
                status['stopped']=sum(c.get('State') not in ('running',) for c in provider.list_containers(all=True) if isinstance(c,dict))
            except Exception:
                status['stopped']=0
            status['state']='ok' if result['failed']==0 else 'partial'
            if result['collected'] or result['running']==0: status['last_success']=int(time.time())
        except Exception as exc:
            status['error_type']=type(exc).__name__
            LOG.warning('collection cycle failed: %s',type(exc).__name__)
        status['duration_ms']=round((time.monotonic()-cycle_started)*1000,1)
        status['interval_seconds']=interval
        status['overrun']=status['duration_ms']>interval*1000
        status['alerts']=classify_alerts(status)
        try:
            all_containers=provider.list_containers(all=True)
            stopped_ids=[c['Id'] for c in all_containers if isinstance(c,dict) and c.get('State')!='running' and c.get('Id')]
            running_metrics={t['full_id']:t for t in status.get('container_timings',[]) if t.get('full_id')}
            status['rule_alerts']=reconcile(running_metrics,stopped_ids)
            status['rule_alert_count']=len(status['rule_alerts'])
        except Exception as exc:
            status['rule_alert_error']=type(exc).__name__
            LOG.warning('rule evaluation failed: %s',type(exc).__name__)
        status['alert_count']=len(status['alerts'])
        status['sampling_mode']='fresh'
        status['duration_ms']=round((time.monotonic()-cycle_started)*1000,1)
        try: publish_status(state,status)
        except OSError: LOG.exception('collector status file write failed')
        next_run=max(next_run+interval,time.monotonic())
        while RUNNING and time.monotonic()<next_run:
            time.sleep(min(.25,next_run-time.monotonic()))

if __name__=='__main__': main()
