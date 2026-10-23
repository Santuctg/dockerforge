from app.ui import HTML

def test_advanced_create_and_details():
    page = HTML
    for token in ('newRestart', 'newEnvironment', 'newMemory', 'newMounts', 'containerDetailPanel', 'viewContainerDetails'):
        assert token in page
