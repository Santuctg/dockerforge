"""Create diagnostics routes with an explicit auth dependency.

Integrate with the actual project's RBAC via require_permission('settings.read')
or another approved admin diagnostic permission. No anonymous default.
"""
from collections.abc import Callable
from fastapi import APIRouter, Depends
from app.docker.provider import DockerProvider
from .health import get_docker_diagnostics

def build_system_router(provider_factory: Callable[[], DockerProvider], authorization: Callable):
    router = APIRouter(prefix='/api/v1/system', tags=['system'])

    @router.get('/diagnostics', dependencies=[Depends(authorization)])
    def diagnostics():
        return {'docker': get_docker_diagnostics(provider_factory())}

    return router
