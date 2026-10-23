from app.monitoring import alert_rules as ar
from app.ui import HTML

def test_acknowledgement_preserved_in_event_history(tmp_path,monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_ALERT_RULES',str(tmp_path/'rules.json'))
    monkeypatch.setenv('DOCKERFORGE_ALERT_STATE',str(tmp_path/'state.json'))
    ident='b'*64
    ar.set_rule(ar.AlertRule(container_id=ident,alert_on_stopped=True))
    ar.reconcile({},[ident],100,lambda _: 'disabled')
    assert ar.acknowledge(ident+':container_stopped','operator')
    ar.reconcile({ident:{'cpu_percent':0,'memory_percent':1}},[],200,lambda _: 'disabled')
    events=ar.list_alerts()['events']
    assert [e['event'] for e in events]==['firing','acknowledged','resolved']
    assert events[1]['actor']=='operator'

def test_smtp_test_disabled_by_default(monkeypatch):
    monkeypatch.delenv('DOCKERFORGE_ALERT_SMTP_ENABLED',raising=False)
    assert ar.smtp_configuration()['enabled'] is False
    assert ar.test_notification()=='disabled'

def test_ui_rule_controls():
    for label in ('Select a container','Save / update rule','Delete rule','Send test email','Alert event history'):
        assert label in HTML
