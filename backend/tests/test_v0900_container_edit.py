import pytest
from app.docker.local_provider import LocalDockerProvider


class Transport:
    def __init__(self, response=None):
        self.calls = []
        self.response = response
    def request(self, method, path, **kw):
        self.calls.append((method, path, kw))
        return self.response


def test_provider_edit_operations_are_encoded():
    t = Transport()
    p = LocalDockerProvider(transport=t)
    p.update_container('abc', {'Memory': 1})
    p.rename_container('abc', 'new-name')
    p.connect_network('net1', 'abc')
    p.disconnect_network('net1', 'abc')
    p.inspect_image('nginx:1.27')
    assert t.calls == [
        ('POST', '/containers/abc/update', {'body': {'Memory': 1}}),
        ('POST', '/containers/abc/rename?name=new-name', {}),
        ('POST', '/networks/net1/connect', {'body': {'Container': 'abc'}}),
        ('POST', '/networks/net1/disconnect', {'body': {'Container': 'abc', 'Force': False}}),
        ('GET', '/images/nginx%3A1.27/json', {}),
    ]


def test_provider_edit_operations_validate_ids():
    p = LocalDockerProvider(transport=Transport())
    for call in (lambda: p.update_container('../x', {}), lambda: p.rename_container('abc', 'bad name'),
                 lambda: p.connect_network('net/1', 'abc'), lambda: p.disconnect_network('net1', '../x')):
        with pytest.raises(ValueError):
            call()
