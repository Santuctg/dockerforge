"""Single-host Compose runner. Only installed Docker CLI is invoked; never a shell."""
import os,re,subprocess
from pathlib import Path
from threading import Lock
from pydantic import BaseModel, Field

STACK_RE=re.compile(r'^[a-z][a-z0-9_-]{0,39}$')
LOCK=Lock()
STACK_ROOT=Path(os.environ.get('DOCKERFORGE_STACK_DIR','/var/lib/dockerforge/stacks'))

class ComposeFailure(RuntimeError):
    """Classified failure. Never expose Docker output, which may contain secrets."""
    def __init__(self, category='operation'):
        self.category=category
        super().__init__('Docker Compose failed: '+category)

def classify_compose_error(value):
    low=value.lower()
    if any(term in low for term in ('port is already allocated', 'address already in use',
                                     'bind for ', 'port has already been allocated')):
        return 'port_conflict'
    if any(term in low for term in ('permission denied', 'access is denied')):
        return 'permission'
    if any(term in low for term in ('no such image', 'manifest unknown', 'pull access denied')):
        return 'image_unavailable'
    return 'operation'

class StackDefinition(BaseModel):
    name:str=Field(min_length=1,max_length=40)
    yaml:str=Field(min_length=10,max_length=131072)
    acknowledge_host_risk:bool=False


def stack_name(name):
    if not STACK_RE.fullmatch(name):raise ValueError('Invalid stack name')
    return name

def run_docker(args, timeout=90, cwd=None):
    # Use stack-specific working directory; do not inherit /root from callers.
    try:
        proc=subprocess.run(['docker', *args], capture_output=True, text=True,
            errors='replace', timeout=timeout, check=False, cwd=str(cwd) if cwd else str(STACK_ROOT),
            env={'PATH':'/usr/local/bin:/usr/bin:/bin',
                 'HOME':os.environ.get('DOCKERFORGE_DOCKER_HOME','/var/lib/dockerforge'), 'DOCKER_CONFIG':os.environ.get('DOCKERFORGE_DOCKER_CONFIG','/var/lib/dockerforge/.docker'), 'DOCKER_HOST':os.environ.get('DOCKERFORGE_DOCKER_HOST',os.environ.get('DOCKER_HOST','unix:///var/run/docker.sock'))})
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError, OSError) as e:
        raise ComposeFailure('unavailable') from e
    if proc.returncode:
        # Classification only; never log, return or persist raw stderr/stdout (secrets).
        raise ComposeFailure(classify_compose_error((proc.stderr or '')[-8192:]))
    return (proc.stdout or '')[:262144]

def _file(name):return STACK_ROOT/stack_name(name)/'compose.yaml'

def create_stack(body:StackDefinition):
    if not body.acknowledge_host_risk:raise PermissionError('Compose deployments require host-risk acknowledgement')
    name=stack_name(body.name)
    with LOCK:
        folder=STACK_ROOT/name
        if folder.exists():raise FileExistsError('Stack already exists')
        folder.mkdir(mode=0o700,parents=True,exist_ok=False)
        try:
            target=folder/'compose.yaml'
            target.write_text(body.yaml,encoding='utf-8')
            target.chmod(0o600)
            run_docker(['compose','-p','df_'+name,'-f',str(target),'config','-q'],timeout=20,cwd=folder)
        except BaseException:
            try:target.unlink(missing_ok=True)
            finally:folder.rmdir()
            raise
    return {'name':name,'project':'df_'+name,'status':'saved'}

def stack_action(name,action):
    name=stack_name(name)
    if action not in ('up','stop','start','down','ps'):raise ValueError('Unsupported stack action')
    path=_file(name)
    if not path.is_file() or path.is_symlink():raise FileNotFoundError('Unknown stack')
    base=['compose','-p','df_'+name,'-f',str(path)]
    args={'up':['up','-d','--remove-orphans'], 'stop':['stop'], 'start':['start'], 'down':['down','--remove-orphans'], 'ps':['ps','--format','json']}[action]
    result=run_docker(base+args,timeout=180 if action=='up' else 90,cwd=path.parent)
    return {'name':name,'project':'df_'+name,'action':action,'output':result[:10000] if action=='ps' else 'Operation completed'}

def list_stacks():
    if not STACK_ROOT.is_dir():return []
    return [{'name':p.name,'project':'df_'+p.name} for p in sorted(STACK_ROOT.iterdir()) if p.is_dir() and not p.is_symlink() and STACK_RE.fullmatch(p.name) and (p/'compose.yaml').is_file()]


def read_stack(name):
    """Return the exact YAML for an existing stack (may contain secrets)."""
    path=_file(name)
    if not path.is_file() or path.is_symlink(): raise FileNotFoundError('Unknown stack')
    return {'name':stack_name(name),'project':'df_'+name,'yaml':path.read_text(encoding='utf-8')}


def update_stack(name, yaml, acknowledged=False):
    """Validate candidate before atomic swap. Does not deploy or modify running containers."""
    if not acknowledged: raise PermissionError('Explicit host-risk acknowledgement required')
    if not isinstance(yaml,str) or not 10<=len(yaml)<=131072:raise ValueError('Invalid YAML size')
    name=stack_name(name)
    path=_file(name)
    if not path.is_file() or path.is_symlink():raise FileNotFoundError('Unknown stack')
    with LOCK:
        tmp=path.parent/'compose.pending.yaml'
        if tmp.exists() or tmp.is_symlink():raise ComposeFailure('pending_update')
        try:
            with tmp.open('x',encoding='utf-8') as f:f.write(yaml)
            tmp.chmod(0o600)
            run_docker(['compose','-p','df_'+name,'-f',str(tmp),'config','-q'],timeout=20,cwd=path.parent)
            # No replace until Docker Compose has validated the proposed document.
            os.replace(tmp,path)
        finally:
            tmp.unlink(missing_ok=True)
    return {'name':name,'project':'df_'+name,'status':'updated','deployed':False}
