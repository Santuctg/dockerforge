"""Docker Engine HTTP API over a local Unix-domain socket only."""
import errno
import http.client
import json
import socket
from typing import Any
from urllib.parse import urlencode, quote
from .containers import valid_id
from .errors import DockerOperationError, DockerPermissionDenied, DockerUnavailable
from .provider import DockerProvider

class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float):
        super().__init__('localhost', timeout=timeout)
        self.socket_path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        try:
            self.sock.connect(self.socket_path)
        except BaseException:
            self.sock.close()
            raise

class UnixDockerTransport:
    def __init__(self, socket_path: str, timeout: float = 8.0):
        if not socket_path.startswith('/') or '\x00' in socket_path:
            raise ValueError('Docker socket path must be absolute')
        if timeout <= 0:
            raise ValueError('timeout must be positive')
        self.socket_path = socket_path
        self.timeout = timeout

    def request(self, method: str, path: str, *, body=None):
        conn = _UnixConnection(self.socket_path, self.timeout)
        try:
            payload = json.dumps(body).encode('utf-8') if body is not None else None
            conn.request(method, path, body=payload, headers={'Accept': 'application/json', **({'Content-Type':'application/json'} if payload is not None else {})})
            response = conn.getresponse()
            data = response.read(8 * 1024 * 1024 + 1)
            if len(data) > 8 * 1024 * 1024:
                raise DockerOperationError('Docker Engine response too large')
            if response.status >= 400:
                # Docker errors may contain filesystem paths, command lines or secrets.
                # Show a stable error code; log only the HTTP status here.
                raise DockerOperationError('Docker Engine rejected the operation (HTTP ' + str(response.status) + ')')
            if not data:
                return None
            if response.getheader('Content-Type', '').startswith('application/json'):
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    return data.decode('utf-8', errors='replace')
            return data.decode('utf-8', errors='replace')
        finally:
            conn.close()

class LocalDockerProvider(DockerProvider):
    def __init__(self, socket_path: str = '/var/run/docker.sock', *, timeout: float = 8.0, transport=None):
        self.socket_path = socket_path
        self.transport = transport if transport is not None else UnixDockerTransport(socket_path, timeout)

    def _get(self, path: str):
        try:
            return self.transport.request('GET', path)
        except DockerOperationError:
            raise
        except PermissionError as exc:
            raise DockerPermissionDenied() from exc
        except (FileNotFoundError, ConnectionRefusedError, ConnectionResetError, BrokenPipeError, socket.timeout, TimeoutError) as exc:
            raise DockerUnavailable() from exc
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EPERM):
                raise DockerPermissionDenied() from exc
            raise DockerUnavailable() from exc
        except (ValueError, RuntimeError, http.client.HTTPException) as exc:
            raise DockerOperationError() from exc

    def ping(self) -> bool:
        return self._get('/_ping') == 'OK'

    def info(self) -> dict[str, Any]:
        return self._get('/info')

    def version(self) -> dict[str, Any]:
        return self._get('/version')

    def list_containers(self, all: bool = True) -> list[dict[str, Any]]:
        return self._get('/containers/json?' + urlencode({'all': int(all)}))

    def list_images(self) -> list[dict[str, Any]]:
        return self._get('/images/json')

    def list_networks(self) -> list[dict[str, Any]]:
        return self._get('/networks')

    def list_volumes(self) -> list[dict[str, Any]]:
        return self._get('/volumes').get('Volumes') or []


    def _call(self, method: str, path: str, *, body=None):
        try:
            return self.transport.request(method,path, **({'body':body} if body is not None else {}))
        except DockerOperationError:raise
        except PermissionError as exc:raise DockerPermissionDenied() from exc
        except (OSError, TimeoutError, socket.timeout) as exc:raise DockerUnavailable() from exc

    def inspect_container(self, ident: str):
        return self._get('/containers/' + valid_id(ident) + '/json')

    def container_stats(self, ident: str):
        return self._get('/containers/' + valid_id(ident) + '/stats?stream=false')

    def create_container(self, name: str, body: dict):
        return self._call('POST','/containers/create?' + urlencode({'name':valid_id(name)}),body=body)

    def start_container(self, ident: str):
        return self._call('POST','/containers/' + valid_id(ident) + '/start')

    def stop_container(self, ident: str):
        return self._call('POST','/containers/' + valid_id(ident) + '/stop')

    def restart_container(self, ident: str):
        return self._call('POST','/containers/' + valid_id(ident) + '/restart')

    def pause_container(self, ident: str):
        return self._call('POST','/containers/' + valid_id(ident) + '/pause')

    def unpause_container(self, ident: str):
        return self._call('POST','/containers/' + valid_id(ident) + '/unpause')

    def delete_container(self, ident: str, *, force: bool = False, remove_volumes: bool = False):
        return self._call('DELETE','/containers/' + valid_id(ident) + '?' + urlencode({'force':str(force).lower(),'v':str(remove_volumes).lower()}))


    def update_container(self, ident: str, body: dict):
        return self._call('POST', '/containers/' + valid_id(ident) + '/update', body=body)

    def rename_container(self, ident: str, new_name: str):
        return self._call('POST', '/containers/' + valid_id(ident) + '/rename?' + urlencode({'name': valid_id(new_name)}))

    def connect_network(self, network: str, ident: str):
        return self._call('POST', '/networks/' + valid_id(network) + '/connect', body={'Container': valid_id(ident)})

    def disconnect_network(self, network: str, ident: str):
        return self._call('POST', '/networks/' + valid_id(network) + '/disconnect', body={'Container': valid_id(ident), 'Force': False})

    def inspect_image(self, ref: str):
        return self._get('/images/' + quote(ref, safe='') + '/json')

    def pull_image(self, image: str):
        # Docker pull endpoint expects fromImage as a query parameter.
        return self._call('POST', '/images/create?' + urlencode({'fromImage':image}))

    def delete_image(self, ident: str):
        return self._call('DELETE', '/images/' + quote(ident, safe=''))

    def create_network(self, name: str, driver: str = 'bridge'):
        return self._call('POST', '/networks/create', body={'Name':name, 'Driver':driver, 'CheckDuplicate':True})

    def delete_network(self, ident: str):
        return self._call('DELETE', '/networks/' + quote(ident, safe=''))

    def create_volume(self, name: str):
        return self._call('POST', '/volumes/create', body={'Name':name})

    def delete_volume(self, name: str):
        return self._call('DELETE', '/volumes/' + quote(name, safe=''))

def get_docker_provider(socket_path: str | None = None) -> DockerProvider:
    import os
    return LocalDockerProvider(socket_path or os.environ.get('DOCKERFORGE_DOCKER_SOCKET', '/var/run/docker.sock'))
