from app.ui import HTML

def test_workspace_navigation_and_features():
    for token in ('app-sidebar','workspace-header','workspace-content','navigate(view)','data-view="containers"','data-view="alerts"','Advanced diagnostics','aria-current','v0.7.0'):
        assert token in HTML

def test_existing_features_preserved():
    for token in ('createContainer(true)','stackPage()','showHistory()','alertRulesPage()','commandPanel(id)','viewLogs(id)','toggleMetricsRefresh()'):
        assert token in HTML
