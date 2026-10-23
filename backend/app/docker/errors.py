"""Safe, stable errors at the Docker Engine boundary."""

class DockerOperationError(Exception):
    code = 'DOCKER_OPERATION_FAILED'
    status_code = 502
    def __init__(self, message='Docker operation failed'):
        super().__init__(message)

class DockerUnavailable(DockerOperationError):
    code = 'DOCKER_UNAVAILABLE'
    status_code = 503
    def __init__(self): super().__init__('Docker Engine is unavailable')

class DockerPermissionDenied(DockerOperationError):
    code = 'DOCKER_PERMISSION_DENIED'
    status_code = 503
    def __init__(self): super().__init__('Docker socket access denied')
