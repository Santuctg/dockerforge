import pytest
from pydantic import ValidationError
from app.docker.containers import CreateContainer

def test_single_mapping_localhost():
    data=CreateContainer(name='web',image='nginx:alpine',port_bindings=[{'host_ip':'127.0.0.1','host_port':8088,'container_port':80,'protocol':'tcp'}]).docker_payload()
    assert data['ExposedPorts']=={'80/tcp':{}}
    assert data['HostConfig']['PortBindings']=={'80/tcp':[{'HostIp':'127.0.0.1','HostPort':'8088'}]}

def test_multi_mapping_and_udp():
    data=CreateContainer(name='web',image='nginx:alpine',port_bindings=[{'host_port':8088,'container_port':80},{'host_port':5353,'container_port':53,'protocol':'udp'}]).docker_payload()
    assert set(data['HostConfig']['PortBindings'])=={'80/tcp','53/udp'}

def test_reject_bad_ip_and_duplicate_bind():
    with pytest.raises(ValidationError):CreateContainer(name='web',image='alpine',port_bindings=[{'host_ip':'localhost','host_port':80,'container_port':80}])
    with pytest.raises(ValueError):CreateContainer(name='web',image='alpine',port_bindings=[{'host_port':8088,'container_port':80},{'host_port':8088,'container_port':81}]).docker_payload()

def test_public_bind_explicit_ack():
    with pytest.raises(ValueError):CreateContainer(name='web',image='alpine',port_bindings=[{'host_ip':'0.0.0.0','host_port':8088,'container_port':80}]).docker_payload()
    body=CreateContainer(name='web',image='alpine',port_bindings=[{'host_ip':'0.0.0.0','host_port':8088,'container_port':80}],acknowledge_public_ports=True).docker_payload()
    assert body['HostConfig']['PortBindings']['80/tcp'][0]['HostIp']=='0.0.0.0'

def test_legacy_ports_still_work():
    body=CreateContainer(name='web',image='alpine',ports={'80/tcp':8088}).docker_payload()
    assert body['HostConfig']['PortBindings']['80/tcp'][0]['HostPort']=='8088'
