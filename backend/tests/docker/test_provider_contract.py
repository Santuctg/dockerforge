from app.docker.provider import DockerProvider
from app.docker.local_provider import LocalDockerProvider


def test_provider_contract():
    assert issubclass(LocalDockerProvider, DockerProvider)
    assert {'ping','info','version','list_containers','list_images','list_networks','list_volumes'} <= set(DockerProvider.__abstractmethods__)


def test_provider_transport_is_injected():
    calls=[]
    class FakeTransport:
        def request(self, method, path):
            calls.append((method,path))
            return {'ServerVersion':'29'}
    provider=LocalDockerProvider('/tmp/nonexistent.sock', transport=FakeTransport())
    assert provider.version()=={'ServerVersion':'29'}
    assert calls==[('GET','/version')]
