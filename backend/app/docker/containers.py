"""Validated container-create input; allowlist only Docker API fields we intentionally expose."""
import re
from ipaddress import ip_address
from pydantic import field_validator
from pydantic import BaseModel, Field
from typing import Literal

IDENT_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
IMAGE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/@-]{0,254}$')
LOOPBACK_IPS = frozenset({'127.0.0.1', '::1'})

def valid_id(value: str) -> str:
    if not IDENT_RE.fullmatch(value):raise ValueError('Invalid Docker container identifier')
    return value

def normalize_host_ip(value: str) -> str:
    """Validate a bind address. '' (or '*') means all interfaces, IPv4 and IPv6."""
    value = (value or '').strip()
    if value in ('', '*'):
        return ''
    return str(ip_address(value))

def is_public_host_ip(value: str) -> bool:
    """True unless the address is a loopback address. Wildcards listen everywhere."""
    return normalize_host_ip(value) not in LOOPBACK_IPS

class PortBinding(BaseModel):
    host_ip: str = '127.0.0.1'
    host_port: int = Field(ge=1, le=65535)
    container_port: int = Field(ge=1, le=65535)
    protocol: Literal['tcp', 'udp'] = 'tcp'

    @field_validator('host_ip')
    @classmethod
    def valid_host_ip(cls, value: str) -> str:
        return normalize_host_ip(value)

class CreateContainer(BaseModel):
    name: str = Field(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')
    image: str = Field(min_length=1,max_length=255)
    command: list[str] | None = None
    environment: dict[str,str] = Field(default_factory=dict)
    ports: dict[str,int] = Field(default_factory=dict)
    port_bindings: list[PortBinding] = Field(default_factory=list)
    acknowledge_public_ports: bool = False
    mounts: list[str] = Field(default_factory=list)
    restart: Literal['no','always','unless-stopped','on-failure'] = 'unless-stopped'
    memory_mb: int | None = Field(default=None,ge=16,le=1048576)
    nano_cpus: int | None = Field(default=None,ge=10000000)
    privileged: bool = False
    network_mode: Literal['bridge','host','none'] = 'bridge'
    pid_mode: Literal['','host'] = ''
    devices: list[str] = Field(default_factory=list)
    cap_add: list[str] = Field(default_factory=list)
    acknowledge_high_risk: bool = False

    def high_risk(self) -> bool:
        return self.privileged or self.network_mode=='host' or self.pid_mode=='host' or bool(self.mounts or self.devices or self.cap_add)

    def docker_payload(self) -> dict:
        if not IMAGE_RE.fullmatch(self.image):raise ValueError('Invalid image name')
        ports = {}
        bindings = {}
        for container_port, host_port in self.ports.items():
            if not re.fullmatch(r'[0-9]{1,5}/(tcp|udp)',container_port):raise ValueError('Invalid container port syntax')
            if not (1<=int(container_port.split('/')[0])<=65535 and 1<=host_port<=65535):raise ValueError('Invalid port number')
            ports[container_port]={}
            bindings[container_port]=[{'HostIp':'127.0.0.1','HostPort':str(host_port)}]
        used_bindings = {(entry['HostIp'], entry['HostPort'], port.split('/')[-1]) for port, entries in bindings.items() for entry in entries}
        for binding in self.port_bindings:
            key = f'{binding.container_port}/{binding.protocol}'
            # Wildcard addresses all listen on every interface; treat them as one key so a
            # duplicate is rejected instead of failing later inside Docker.
            host_key = (binding.host_ip or '0.0.0.0', str(binding.host_port), binding.protocol)
            if host_key in used_bindings:
                raise ValueError('Duplicate host address/port/protocol mapping')
            if is_public_host_ip(binding.host_ip) and not self.acknowledge_public_ports:
                raise ValueError('Non-localhost port exposure requires explicit acknowledgement')
            used_bindings.add(host_key)
            ports[key] = {}
            bindings.setdefault(key, []).append({'HostIp':binding.host_ip,'HostPort':str(binding.host_port)})
        binds=[]
        for mount in self.mounts:
            pieces=mount.split(':')
            if len(pieces) not in (2,3) or not pieces[0].startswith('/') or not pieces[1].startswith('/') or (len(pieces)==3 and pieces[2] not in ('ro','rw')):
                raise ValueError('Only absolute source:target[:ro|rw] bind mounts are supported')
            binds.append(mount)
        host={'RestartPolicy':{'Name':self.restart},'Privileged':self.privileged,'NetworkMode':self.network_mode,'PortBindings':bindings,'Binds':binds}
        if self.memory_mb:host['Memory']=self.memory_mb*1024*1024
        if self.nano_cpus:host['NanoCpus']=self.nano_cpus
        if self.pid_mode:host['PidMode']=self.pid_mode
        if self.cap_add:host['CapAdd']=self.cap_add
        if self.devices:
            host['Devices']=[]
            for device in self.devices:
                bits=device.split(':')
                if len(bits) not in (1,2,3) or any(not b.startswith('/') for b in bits[:min(2,len(bits))]):raise ValueError('Invalid device mount')
                host['Devices'].append({'PathOnHost':bits[0],'PathInContainer':bits[1] if len(bits)>1 else bits[0],'CgroupPermissions':bits[2] if len(bits)>2 else 'rwm'})
        result={'Image':self.image,'Env':[f'{k}={v}' for k,v in self.environment.items()], 'ExposedPorts':ports,'HostConfig':host}
        if self.command is not None:result['Cmd']=self.command
        return result
