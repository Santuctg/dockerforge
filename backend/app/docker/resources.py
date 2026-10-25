"""Input validation for the v0.1.8 Docker resource operations."""
import re
from ipaddress import ip_address
from pydantic import BaseModel, Field, field_validator
from .containers import IMAGE_RE

NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')

def safe_resource_name(name: str) -> str:
    if not NAME_RE.fullmatch(name):
        raise ValueError('Invalid Docker resource name')
    return name

class ImagePull(BaseModel):
    image: str = Field(min_length=1, max_length=255)
    @field_validator('image')
    @classmethod
    def valid_image(cls, value: str) -> str:
        if not IMAGE_RE.fullmatch(value):
            raise ValueError('Invalid image reference')
        return value

class NetworkCreate(BaseModel):
    name: str
    driver: str = 'bridge'
    @field_validator('name')
    @classmethod
    def valid_name(cls, value: str) -> str:
        if value in {'bridge','host','none'}:
            raise ValueError('Built-in network name is reserved')
        return safe_resource_name(value)
    @field_validator('driver')
    @classmethod
    def valid_driver(cls, value: str) -> str:
        if value not in ('bridge', 'overlay', 'macvlan', 'ipvlan'):
            raise ValueError('Unsupported driver')
        return value

class VolumeCreate(BaseModel):
    name: str
    @field_validator('name')
    @classmethod
    def valid_name(cls, value: str) -> str:
        return safe_resource_name(value)

class TypedDelete(BaseModel):
    confirm_name: str

def _wildcard(value: str) -> bool:
    return value in ('', '*', '0.0.0.0', '::')


def _same_address(left: str, right: str) -> bool:
    try:
        return ip_address(left) == ip_address(right)
    except ValueError:
        return left == right


def validate_port_availability(bindings: list[dict], containers: list[dict]) -> None:
    for binding in bindings:
        host_ip = binding['host_ip']; port = int(binding['host_port']); protocol = binding.get('protocol','tcp')
        for item in containers:
            if item.get('State') not in ('running','restarting'):
                continue
            for existing in item.get('Ports') or []:
                if existing.get('PublicPort') != port or existing.get('Type','tcp') != protocol:
                    continue
                ip = existing.get('IP','0.0.0.0')
                # A wildcard on either side covers every address; otherwise compare the
                # parsed addresses so equivalent IPv6 spellings still conflict.
                if _wildcard(ip) or _wildcard(host_ip) or _same_address(ip, host_ip):
                    raise ValueError(f'Host port {port}/{protocol} is already published by a running container')
