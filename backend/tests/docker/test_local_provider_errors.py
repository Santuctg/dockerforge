import pytest
from app.docker.local_provider import LocalDockerProvider
from app.docker.errors import DockerUnavailable, DockerPermissionDenied, DockerOperationError


def test_missing_socket_normalized(tmp_path):
    p=LocalDockerProvider(str(tmp_path/'missing.sock'))
    with pytest.raises(DockerUnavailable): p.ping()


def test_socket_permission_denied_normalized():
    class FakeTransport:
        def request(self,*args): raise PermissionError('private path')
    p=LocalDockerProvider('/tmp/hidden',transport=FakeTransport())
    with pytest.raises(DockerPermissionDenied,match='Docker socket access denied'): p.info()


def test_other_errors_do_not_leak_paths():
    class FakeTransport:
        def request(self,*args): raise RuntimeError('secret private path')
    p=LocalDockerProvider('/tmp/hidden',transport=FakeTransport())
    with pytest.raises(DockerOperationError) as exc: p.info()
    assert 'secret' not in str(exc.value)
