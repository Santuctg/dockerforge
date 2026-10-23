from app.ui import HTML

def test_logs_controls():
    for token in ('setupLogWorkspace', 'Filter fetched logs', 'Download', 'Follow (5s polling)', 'safeFilename', 'saveTextFile'):
        assert token in HTML

def test_console_controls():
    for token in ('setupConsoleWorkspace', 'ArrowUp', 'ArrowDown', 'Clear output', 'Copy output', 'consoleHistory'):
        assert token in HTML
