from app.ui import HTML

def test_structured_detail_tabs():
    for key in ("overview", "configuration", "network", "mounts", "logs", "stats", "console", "raw"):
        assert "'"+key+"'" in HTML
    assert "renderInspectDetails" in HTML
    assert "Reveal raw inspection JSON" in HTML
    assert "Environment values may contain secrets" in HTML
