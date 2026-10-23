from app.ui import HTML

def test_details_copy_and_readable_time():
    for token in ('friendlyTime(value)', 'copy-field', 'navigator.clipboard.writeText', "['ID',data.Id,true]", 'DNS aliases', 'Subnet prefix'):
        assert token in HTML

def test_expanded_log_and_console_workspace():
    for token in ('log-workspace', 'console-workspace', 'console-controls', 'Raw JSON', 'details-json'):
        assert token in HTML
