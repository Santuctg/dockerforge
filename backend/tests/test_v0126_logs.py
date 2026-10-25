from app.stack import container_tools as tools
import pytest
from app.ui import HTML

def test_logs_tail_timestamp_and_size(monkeypatch):
    calls=[]
    def fake_run(args, **kwargs):
        calls.append(args)
        class R:
            returncode=0
            stdout=b'x'*270000
            stderr=b''
        return R()
    monkeypatch.setattr(tools.subprocess,'run',fake_run)
    result=tools.logs('demo',1000,True)
    assert calls[0]==['docker','logs','--tail','1000','--timestamps','demo']
    assert result['truncated'] and len(result['output'])==262144
    result=tools.logs('demo',100,False)
    assert '--timestamps' not in calls[-1]

@pytest.mark.parametrize('tail',[0,1001,-10])
def test_reject_bad_tail(tail):
    with pytest.raises(ValueError):tools.logs('demo',tail)

def test_ui_features():
    for token in ('Previous commands','Download filtered','Follow (5s polling)','Timestamps','1000','v0.9.0'):
        assert token in HTML
