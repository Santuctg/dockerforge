# Bounded on-demand Docker stats history. No background collection.
# SQLite history contains only numeric metrics, no secrets.
import sqlite3
import time
from pathlib import Path
from threading import RLock
from app.monitoring.metrics import normalize_stats

GUARD=RLock()
CACHE={}
TTL=5.0
RETENTION=7*86400
WINDOWS={'1h':3600,'24h':86400,'7d':604800,'30d':2592000,'90d':7776000}
LAST_PRUNE={}

def _db(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path, timeout=10)
    db.execute('PRAGMA busy_timeout=10000')
    db.execute('''CREATE TABLE IF NOT EXISTS container_metrics (
      container_id TEXT NOT NULL, ts INTEGER NOT NULL,
      cpu REAL NOT NULL, memory_bytes INTEGER NOT NULL, memory_pct REAL NOT NULL,
      rx_bytes INTEGER NOT NULL, tx_bytes INTEGER NOT NULL,
      rx_bps REAL NOT NULL, tx_bps REAL NOT NULL,
      PRIMARY KEY(container_id,ts))''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_metric_time ON container_metrics(ts)')
    db.execute('''CREATE TABLE IF NOT EXISTS container_metrics_hourly (
      container_id TEXT NOT NULL, hour INTEGER NOT NULL, samples INTEGER NOT NULL,
      cpu_sum REAL NOT NULL, memory_sum REAL NOT NULL, memory_pct_sum REAL NOT NULL,
      rx_bps_sum REAL NOT NULL, tx_bps_sum REAL NOT NULL,
      PRIMARY KEY(container_id,hour))''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_metric_hour ON container_metrics_hourly(hour)')
    return db

def _rates(prev, now, elapsed):
    if not prev or elapsed<=0 or elapsed>120:return (0.0,0.0)
    # Counter reset, container restart or network interface recreation cannot create negative bandwidth.
    return tuple(round(max(0, now[key]-prev[key])*8/elapsed,2) if now[key]>=prev[key] else 0.0 for key in ('network_rx_bytes','network_tx_bytes'))

def cached_sample(ident, fetch, path, now=None, *, force=False, timings=None):
    # A process-local lock coalesces concurrent requests from duplicate dashboard intervals.
    now=time.time() if now is None else float(now)
    key=(str(path),ident)
    # Refresh is mandatory for background collection, but UI requests may use cache.
    # Never hold GUARD while calling Docker Engine: stats?stream=false can block
    # for 1-2s, which would otherwise serialize parallel container sampling.
    with GUARD:
        entry=CACHE.get(key)
        if not force and entry and 0 <= now-entry[0] < TTL:
            if timings is not None:
                timings.update(cache_hit=True, docker_stats_ms=0.0, sqlite_write_ms=0.0)
            return dict(entry[1])
    started=time.monotonic()
    data=normalize_stats(fetch())
    stats_ms=round((time.monotonic()-started)*1000,1)
    write_started=time.monotonic()
    with GUARD:
        with _db(path) as db:
            previous=db.execute('SELECT ts,rx_bytes,tx_bytes FROM container_metrics WHERE container_id=? ORDER BY ts DESC LIMIT 1',(ident,)).fetchone()
            prev={'network_rx_bytes':previous[1],'network_tx_bytes':previous[2]} if previous else None
            elapsed=now-previous[0] if previous else 0
            rx,tx=_rates(prev,data,elapsed)
            data.update(network_rx_bps=rx,network_tx_bps=tx)
            stamp=int(now)
            db.execute('''INSERT OR REPLACE INTO container_metrics(container_id,ts,cpu,memory_bytes,memory_pct,rx_bytes,tx_bytes,rx_bps,tx_bps)
              VALUES(?,?,?,?,?,?,?,?,?)''',(ident,stamp,data['cpu_percent'],data['memory_usage_bytes'],data['memory_percent'],data['network_rx_bytes'],data['network_tx_bytes'],rx,tx))
            # Maintain 90-day hourly rollups separately from the 7-day raw store.
            hour=(stamp//3600)*3600
            db.execute('''INSERT INTO container_metrics_hourly
              (container_id,hour,samples,cpu_sum,memory_sum,memory_pct_sum,rx_bps_sum,tx_bps_sum)
              VALUES(?,?,1,?,?,?,?,?) ON CONFLICT(container_id,hour) DO UPDATE SET
              samples=samples+1,cpu_sum=cpu_sum+excluded.cpu_sum,
              memory_sum=memory_sum+excluded.memory_sum,
              memory_pct_sum=memory_pct_sum+excluded.memory_pct_sum,
              rx_bps_sum=rx_bps_sum+excluded.rx_bps_sum,tx_bps_sum=tx_bps_sum+excluded.tx_bps_sum''',
              (ident,hour,data['cpu_percent'],data['memory_usage_bytes'],data['memory_percent'],rx,tx))
            if now-LAST_PRUNE.get(str(path),0)>300:
                db.execute('DELETE FROM container_metrics WHERE ts < ?',(stamp-RETENTION,))
                db.execute('DELETE FROM container_metrics_hourly WHERE hour < ?',(stamp-90*86400,))
                LAST_PRUNE[str(path)]=now
        CACHE[key]=(now,dict(data))
        # Prevent unbounded per-container cache growth.
        if len(CACHE)>500:
            for k,v in list(CACHE.items()):
                if now-v[0]>TTL:CACHE.pop(k,None)
    if timings is not None:
        timings.update(cache_hit=False, docker_stats_ms=stats_ms,
                       sqlite_write_ms=round((time.monotonic()-write_started)*1000,1))
    return data

def query_history(ident, window, path, now=None):
    if window not in WINDOWS:raise ValueError('Unsupported monitoring window')
    now=int(time.time() if now is None else now)
    seconds=WINDOWS[window]
    bucket=max(5,(seconds+359)//360)
    with _db(path) as db:
        if window in ('30d','90d'):
            # Coalesce hourly rollups into <= 360 timeline buckets; weighted by sample counts.
            stride=7200 if window=='30d' else 21600
            rows=db.execute('''SELECT (hour / ?) * ? AS t,
              SUM(cpu_sum)/SUM(samples),SUM(memory_sum)/SUM(samples),
              SUM(memory_pct_sum)/SUM(samples),SUM(rx_bps_sum)/SUM(samples),
              SUM(tx_bps_sum)/SUM(samples),SUM(samples)
              FROM container_metrics_hourly WHERE container_id=? AND hour>=? AND hour<=?
              GROUP BY t ORDER BY t''',(stride,stride,ident,now-seconds,now)).fetchall()
        else:
            rows=db.execute('''SELECT (ts / ?) * ? AS t, AVG(cpu), AVG(memory_bytes), AVG(memory_pct),
          AVG(rx_bps),AVG(tx_bps),COUNT(*) FROM container_metrics WHERE container_id=? AND ts>=? AND ts<=?
          GROUP BY t ORDER BY t LIMIT 400''',(bucket,bucket,ident,now-seconds,now)).fetchall()
    return {'window':window,'sample_count':sum(r[6] for r in rows),'points':[
       {'ts':r[0],'cpu_percent':round(r[1],2),'memory_usage_bytes':round(r[2]),
        'memory_percent':round(r[3],2),'network_rx_bps':round(r[4],2),'network_tx_bps':round(r[5],2)} for r in rows],
        'note':'History uses hourly aggregation for 30d/90d and raw samples for shorter windows; rates are estimates.'}
