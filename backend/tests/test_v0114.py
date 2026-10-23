from app.monitoring.collector import INTERVAL, publish_status
from app.monitoring import history
from pathlib import Path
import json

def test_collector_interval():
    assert INTERVAL == 5.0

def test_health_status_fields_roundtrip(tmp_path):
    path=tmp_path/'status.json'
    publish_status(path, {'last_attempt':100,'last_success':100,'duration_ms':123.4,'interval_seconds':5,'state':'ok'})
    result=json.loads(path.read_text())
    assert result['duration_ms']==123.4
    assert result['interval_seconds']==5
    assert path.stat().st_mode & 0o777 == 0o600

def test_history_retention_unchanged():
    assert history.RETENTION == 7*86400
    assert {'1h','24h','7d'}.issubset(history.WINDOWS)
