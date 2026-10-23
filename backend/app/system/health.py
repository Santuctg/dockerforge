"""Do not expose Docker exception bodies or host file paths in diagnostics."""
from app.docker.errors import DockerOperationError
from app.docker.provider import DockerProvider

def get_docker_diagnostics(provider: DockerProvider) -> dict:
    try:
        online = provider.ping()
        if not online:
            return {'status': 'unavailable', 'message': 'Docker Engine did not respond'}
        version = provider.version()
        info = provider.info()
        return {'status': 'healthy', 'version': version.get('Version'), 'containers': info.get('Containers')}
    except DockerOperationError as exc:
        return {'status': 'unavailable', 'message': str(exc)}
