from app.monitoring import alert_rules as a

def test_rule_lifecycle_and_ack(tmp_path,monkeypatch):
    monkeypatch.setenv('DOCKERFORGE_ALERT_RULES',str(tmp_path/'rules.json'))
    monkeypatch.setenv('DOCKERFORGE_ALERT_STATE',str(tmp_path/'state.json'))
    ident='a'*64
    rule=a.AlertRule(container_id=ident,cpu_threshold=80,memory_threshold=85,alert_on_stopped=True)
    a.set_rule(rule)
    assert a.list_rules()[ident]['cpu_threshold']==80
    delivered=[]
    x=a.reconcile({ident:{'cpu_percent':95,'memory_percent':90}},[],100,lambda v:delivered.append(v['key']) or 'sent')
    assert len(x)==2 and len(delivered)==2
    assert a.acknowledge(ident+':cpu_high','operator')
    a.reconcile({ident:{'cpu_percent':95,'memory_percent':90}},[],110,lambda v:delivered.append(v['key']) or 'sent')
    assert len(delivered)==2
    assert a.list_alerts()['active'][ident+':cpu_high']['acknowledged_by']=='operator'
    a.reconcile({ident:{'cpu_percent':1,'memory_percent':1}},[],120,lambda _: 'sent')
    assert not a.list_alerts()['active']
    a.reconcile({},[ident],130,lambda _: 'sent')
    assert ident+':container_stopped' in a.list_alerts()['active']
    assert a.delete_rule(ident)

def test_disabled_and_validation(tmp_path,monkeypatch):
    import pytest
    monkeypatch.setenv('DOCKERFORGE_ALERT_RULES',str(tmp_path/'rules.json'))
    monkeypatch.setenv('DOCKERFORGE_ALERT_STATE',str(tmp_path/'state.json'))
    with pytest.raises(ValueError):a.set_rule(a.AlertRule(container_id='bad'))
    ident='b'*64
    a.set_rule(a.AlertRule(container_id=ident,enabled=False))
    assert not a.reconcile({ident:{'cpu_percent':1000,'memory_percent':100}},[],100,lambda _: 'sent')
    assert a.send_notification({'key':'x','type':'cpu_high','container_id':'b'})=='disabled'
