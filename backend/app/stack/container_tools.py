"""Bounded log retrieval and one-shot container exec; no shell on host."""
import subprocess,os
from pydantic import BaseModel,Field
from app.docker.containers import valid_id

class ExecCommand(BaseModel):
    argv:list[str]=Field(min_length=1,max_length=24)


def docker_cli(args,timeout=15,include_stderr=False,max_bytes=65536):
    try:
        res=subprocess.run(['docker',*args],capture_output=True,timeout=timeout,check=False,env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':os.environ.get('DOCKERFORGE_DOCKER_HOME','/var/lib/dockerforge'),'DOCKER_CONFIG':os.environ.get('DOCKERFORGE_DOCKER_CONFIG','/var/lib/dockerforge/.docker'),'DOCKER_HOST':os.environ.get('DOCKERFORGE_DOCKER_HOST',os.environ.get('DOCKER_HOST','unix:///var/run/docker.sock'))})
    except (FileNotFoundError,subprocess.TimeoutExpired) as e:
        raise RuntimeError('Docker command unavailable or timed out') from e
    if res.returncode:
        # Do not reflect stderr: may contain secrets.
        raise RuntimeError('Docker command failed')
    data = res.stdout + (b'\n' + res.stderr if include_stderr and res.stderr else b'')
    return {'output':data[:max_bytes].decode('utf-8','replace'),'truncated':len(data)>max_bytes}


def logs(ident,tail=100,timestamps=False):
    valid_id(ident)
    if not isinstance(tail,int) or not (1<=tail<=1000):
        raise ValueError('Invalid log tail')
    if not isinstance(timestamps,bool):
        raise ValueError('Invalid timestamp setting')
    args=['logs','--tail',str(tail)]
    if timestamps: args.append('--timestamps')
    args.append(ident)
    return docker_cli(args,timeout=15,include_stderr=True,max_bytes=262144)



def execute(ident,body):
    valid_id(ident)
    if any(not arg or len(arg)>1024 or '\x00' in arg for arg in body.argv):raise ValueError('Invalid command argument')
    return docker_cli(['exec','--',ident,*body.argv],timeout=30)
