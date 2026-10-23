from app.ui import HTML

def test_container_workspace_refinement():
    for token in ('containerSearch','containerStateFilter','filterContainerRows','workload-row','state-pill','More actions','create-panel','form-grid','removePortRow'):
        assert token in HTML

def test_original_action_contract_retained():
    for token in ('createContainer(true)','createContainer(false)','deleteContainer(id,name)','encodeURIComponent(id)','publicPorts','ackRisk','newImage','newName'):
        assert token in HTML
