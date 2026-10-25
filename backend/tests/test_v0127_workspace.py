from app.ui import HTML

def test_single_logs_workspace():
    assert "viewLogs=function(id){return openDetailsFor(id,'logs')}" in HTML
    assert "commandPanel=function(id){return openDetailsFor(id,'console')}" in HTML
    assert 'return originalViewLogs' not in HTML

def test_fullscreen_and_follow_controls():
    for token in ('fullscreen-details', 'Exit fullscreen', "event.key==='Escape'", "makeToolButton('Pause'", "'Resume'", 'Auto-scroll'):
        assert token in HTML

def test_version():
    assert 'DockerForge R1 v0.9.0' in HTML
