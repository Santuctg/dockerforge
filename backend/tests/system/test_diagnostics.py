from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.system.router import build_system_router
from app.docker.errors import DockerUnavailable

class DownProvider:
    def ping(self): raise DockerUnavailable()
    def version(self): raise DockerUnavailable()
    def info(self): raise DockerUnavailable()


def require_admin():
    raise HTTPException(status_code=401, detail='Authentication required')


def test_diagnostics_are_protected():
    app=FastAPI()
    app.include_router(build_system_router(lambda: DownProvider(),require_admin))
    response=TestClient(app).get('/api/v1/system/diagnostics')
    assert response.status_code==401


def test_diagnostics_docker_down_is_safe():
    app=FastAPI()
    app.include_router(build_system_router(lambda: DownProvider(),lambda: True))
    resp=TestClient(app).get('/api/v1/system/diagnostics')
    assert resp.status_code==200
    assert resp.json()['docker']['status']=='unavailable'
    assert 'traceback' not in str(resp.json()).lower()
