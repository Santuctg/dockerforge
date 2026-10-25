from app.ui import HTML

def test_ui_version():
    assert 'R1 v0.9.0' in HTML

def test_metrics_cards():
    assert 'metric-card' in HTML
    assert 'container-card' in HTML

def test_chart_inspection():
    assert 'pointermove' in HTML
    assert 'chart-grid' in HTML

def test_history_refresh_throttled():
    assert 'Date.now()-historyLastFetch>=10000' in HTML
    assert 'historyInFlight' in HTML
