import hashlib, json, os, secrets, sqlite3, time, uuid
from pathlib import Path
from threading import Lock
from argon2 import PasswordHasher
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from typing import Literal
from pydantic import BaseModel, Field
from app.stack.compose import StackDefinition, ComposeFailure, create_stack, list_stacks, stack_action, stack_name, read_stack, update_stack
from app.stack.container_tools import ExecCommand, logs as fetch_logs, execute as exec_container
from app.docker.local_provider import LocalDockerProvider
from app.docker.containers import CreateContainer, valid_id
from app.docker.errors import DockerOperationError
from app.docker import edit as container_edit
from app.docker.resources import ImagePull, NetworkCreate, VolumeCreate, TypedDelete, safe_resource_name, validate_port_availability

DB = os.environ.get('DOCKERFORGE_DB','/var/lib/dockerforge/dockerforge.db')
COOKIE = 'dockerforge_session'
CSRF_COOKIE = 'dockerforge_csrf'
ROLES = ('super_admin','admin','operator','viewer')
READ = {'super_admin','admin','operator','viewer'}
OPS = {'super_admin','admin','operator'}
ADMINS = {'super_admin','admin'}
_ph = PasswordHasher()
_init_lock = Lock()
_failed = {}
RECREATE_SETTLE = 3.0
# Stop waits for the container's stop timeout and pulls can take minutes.
RECREATE_TIMEOUT = 600.0
_failed_ip = {}
_failed_lock = Lock()
FAILED_CAP = 10000
# Failures per client IP across all usernames; also stops key floods from evicting a lockout.
IP_FAILURE_LIMIT = 30

def conn():
    Path(os.environ.get('DOCKERFORGE_DB',DB)).parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(os.environ.get('DOCKERFORGE_DB',DB), timeout=15)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA busy_timeout=15000')
    c.execute('PRAGMA foreign_keys=ON')
    return c

def initialize():
    with conn() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('super_admin','admin','operator','viewer')), created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(id_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), csrf_hash TEXT NOT NULL, created_at INTEGER NOT NULL, last_seen INTEGER NOT NULL, expires_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts INTEGER NOT NULL, actor TEXT, action TEXT NOT NULL, resource TEXT, ip TEXT, result TEXT NOT NULL, request_id TEXT, metadata TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts DESC);
        CREATE TABLE IF NOT EXISTS container_backups(name TEXT PRIMARY KEY, new_id TEXT NOT NULL, old_id TEXT NOT NULL, old_name TEXT NOT NULL, created_at INTEGER NOT NULL, restart_policy TEXT NOT NULL DEFAULT '{}');''')

def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def client_ip(req):return req.client.host if req.client else 'unknown'

def redact(value):
    if isinstance(value,dict):return {k:('[REDACTED]' if any(w in k.lower() for w in ('password','token','secret','key','stdin','keystroke','credential','env')) else redact(v)) for k,v in value.items()}
    if isinstance(value,list):return [redact(v) for v in value]
    return value

def audit(req, action, result='success', user=None, resource=None, metadata=None):
    with conn() as db:
        db.execute('INSERT INTO audit(ts,actor,action,resource,ip,result,request_id,metadata) VALUES(?,?,?,?,?,?,?,?)',(int(time.time()),user,action,resource,client_ip(req),result,getattr(req.state,'request_id',''),json.dumps(redact(metadata or {}))))

def prune_failed(now,cap=None):
    cap=FAILED_CAP if cap is None else cap
    # Keep login rate-limit state bounded: forget expired keys, then cap by most recent attempt.
    # Caller holds _failed_lock.
    for store in (_failed,_failed_ip):
        for key in [k for k,v in store.items() if not any(t>now-300 for t in v)]:store.pop(key,None)
    if len(_failed)>cap:
        # Evict keys with the fewest recent failures first, so a flood of junk usernames cannot clear a real lockout.
        for key in sorted(_failed,key=lambda k:(len(_failed[k]),max(_failed[k])))[:len(_failed)-cap]:_failed.pop(key,None)

def fail(code,message,status):raise HTTPException(status_code=status,detail={'code':code,'message':message})
def user_from_session(req):
    token=req.cookies.get(COOKIE,'')
    if not token:return None
    now=int(time.time())
    with conn() as db:
        r=db.execute('SELECT u.*, s.id_hash,s.last_seen,s.expires_at,s.csrf_hash FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id_hash=?',(digest(token),)).fetchone()
        if not r:return None
        if r['expires_at'] <= now or r['last_seen']+1800 <= now:
            db.execute('DELETE FROM sessions WHERE id_hash=?',(r['id_hash'],));return None
        db.execute('UPDATE sessions SET last_seen=? WHERE id_hash=?',(now,r['id_hash']))
        return dict(r)

def require_user(req:Request):
    user=user_from_session(req)
    if not user:fail('AUTH_REQUIRED','Sign in required',401)
    return user

def require_role(roles):
    def check(user=Depends(require_user)):
        if user['role'] not in roles:fail('FORBIDDEN','Insufficient permission',403)
        return user
    return check

def require_csrf(req:Request):
    user=require_user(req)
    cookie=req.cookies.get(CSRF_COOKIE,'')
    supplied=req.headers.get('X-CSRF-Token','')
    if not cookie or not secrets.compare_digest(cookie,supplied) or not secrets.compare_digest(user['csrf_hash'],digest(cookie)):
        fail('CSRF_INVALID','Invalid CSRF token',403)
    return user

class SqliteBackupStore:
    """One recreate backup per container name, kept in the application database."""
    def get(self,name):
        with conn() as db:r=db.execute('SELECT new_id,old_id,old_name,created_at,restart_policy FROM container_backups WHERE name=?',(name,)).fetchone()
        return {**dict(r),'restart_policy':json.loads(r['restart_policy'])} if r else None
    def put(self,name,new_id,old_id,old_name,ts,restart_policy):
        with conn() as db:db.execute('INSERT OR REPLACE INTO container_backups VALUES(?,?,?,?,?,?)',(name,new_id,old_id,old_name,ts,json.dumps(restart_policy)))
    def delete(self,name):
        with conn() as db:db.execute('DELETE FROM container_backups WHERE name=?',(name,))
    def rename(self,old,new):
        with conn() as db:db.execute('UPDATE container_backups SET name=? WHERE name=?',(new,old))

class ResourceUpdate(BaseModel):
    memory_mb:int|None=Field(default=None,ge=16,le=1048576)
    nano_cpus:int|None=Field(default=None,ge=0)
    restart:Literal['no','always','unless-stopped','on-failure']='unless-stopped'

class RenameRequest(BaseModel):
    name:str=Field(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')

class Credentials(BaseModel):
    username:str=Field(min_length=3,max_length=64)
    password:str=Field(min_length=12,max_length=256)
class ManagedUser(BaseModel):
    username:str=Field(min_length=3,max_length=64,pattern=r'^[A-Za-z0-9_.-]+$')
    password:str=Field(min_length=12,max_length=256)
    role:str

class RoleUpdate(BaseModel):
    role:str

class PasswordReset(BaseModel):
    password:str=Field(min_length=12,max_length=256)

class Login(BaseModel):
    username:str
    password:str

class DeleteConfirmation(BaseModel):
    confirm_name:str
    force:bool=False
    remove_volumes:bool=False

def redact_env(details):
    # Env values often hold passwords/tokens; keep only variable names for non-admins.
    config=details.get('Config') if isinstance(details,dict) else None
    if not isinstance(config,dict) or not isinstance(config.get('Env'),list):return details
    env=[e.split('=',1)[0]+'=[REDACTED]' if isinstance(e,str) and '=' in e else e for e in config['Env']]
    return {**details,'Config':{**config,'Env':env}}

def provider(timeout=8.0):return LocalDockerProvider(os.environ.get('DOCKERFORGE_DOCKER_SOCKET','/var/run/docker.sock'),timeout=timeout)

def create_app():
    initialize()
    app=FastAPI(title='DockerForge R1 Integrated Foundation',version='0.7.0')
    @app.middleware('http')
    async def request_id(req,call_next):
        v=req.headers.get('X-Request-ID','')
        try: rid=str(uuid.UUID(v)) if str(uuid.UUID(v))==v else str(uuid.uuid4())
        except ValueError:rid=str(uuid.uuid4())
        req.state.request_id=rid
        try: res=await call_next(req)
        except Exception: raise
        res.headers['X-Request-ID']=rid
        res.headers['Cache-Control']='no-store'
        res.headers['X-Content-Type-Options']='nosniff'
        res.headers['X-Frame-Options']='DENY'
        res.headers['Referrer-Policy']='no-referrer'
        res.headers['Strict-Transport-Security']='max-age=31536000'
        return res
    @app.exception_handler(HTTPException)
    async def http_error(req,exc):
        d=exc.detail if isinstance(exc.detail,dict) else {'code':'HTTP_ERROR','message':str(exc.detail)}
        return JSONResponse(status_code=exc.status_code,content={'error':{**d,'request_id':getattr(req.state,'request_id','')}},headers={'X-Request-ID':getattr(req.state,'request_id','')})
    @app.get('/',response_class=HTMLResponse)
    def home():
        from app.ui import HTML
        return HTML
    @app.get('/health')
    def health():return {'status':'ok','database':'ok'}
    @app.get('/api/v1/auth/setup/status')
    def status():
        with conn() as db:return {'setup_required':db.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0}
    @app.post('/api/v1/auth/setup',status_code=201)
    def setup(body:Credentials, req:Request):
        with _init_lock:
            expected=os.environ.get('DOCKERFORGE_SETUP_TOKEN','')
            provided=req.headers.get('X-Setup-Token','')
            if not expected or not secrets.compare_digest(expected,provided): fail('SETUP_TOKEN_REQUIRED','Local bootstrap token required',403)
            with conn() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT COUNT(*) FROM users').fetchone()[0]:fail('SETUP_CLOSED','Initial setup already complete',403)
                db.execute('INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)',(body.username,_ph.hash(body.password),'super_admin',int(time.time())))
            audit(req,'auth.setup',user=body.username)
        return {'username':body.username,'role':'super_admin'}
    @app.get('/api/v1/auth/csrf')
    def csrf(req:Request):
        val=secrets.token_urlsafe(32)
        user=user_from_session(req)
        if user:
            with conn() as db:db.execute('UPDATE sessions SET csrf_hash=? WHERE id_hash=?',(digest(val),user['id_hash']))
        res=JSONResponse({'csrf_token':val})
        res.set_cookie(CSRF_COOKIE,val,secure=True,httponly=True,samesite='lax',path='/')
        return res
    @app.post('/api/v1/auth/login')
    def login(body:Login,req:Request):
        if not req.cookies.get(CSRF_COOKIE) or not secrets.compare_digest(req.cookies.get(CSRF_COOKIE,''), req.headers.get('X-CSRF-Token','')):
            fail('CSRF_INVALID','CSRF token required',403)
        now=int(time.time());ip=client_ip(req);key=(ip,body.username.lower().strip())
        with _failed_lock:
            prune_failed(now)
            attempts=[t for t in _failed.get(key,[]) if t>now-300]
            ip_attempts=[t for t in _failed_ip.get(ip,[]) if t>now-300]
        if len(attempts)>=5 or len(ip_attempts)>=IP_FAILURE_LIMIT:
            audit(req,'auth.login','rate_limited',user=body.username);fail('RATE_LIMITED','Too many login attempts',429)
        with conn() as db:r=db.execute('SELECT * FROM users WHERE username=?',(body.username,)).fetchone()
        good=False
        if r:
            try:good=_ph.verify(r['password_hash'],body.password)
            except Exception:pass
        if not good:
            with _failed_lock:
                _failed.setdefault(key,[]).append(now);_failed_ip.setdefault(ip,[]).append(now)
            audit(req,'auth.login','denied',user=body.username);fail('LOGIN_FAILED','Invalid credentials',401)
        with _failed_lock:_failed.pop(key,None)
        token=secrets.token_urlsafe(48);csrf=secrets.token_urlsafe(32)
        with conn() as db:db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(digest(token),r['id'],digest(csrf),now,now,now+86400))
        res=JSONResponse({'username':r['username'],'role':r['role'],'csrf_token':csrf})
        res.set_cookie(COOKIE,token,httponly=True,secure=True,samesite='lax',path='/')
        res.set_cookie(CSRF_COOKIE,csrf,httponly=True,secure=True,samesite='lax',path='/')
        audit(req,'auth.login',user=r['username'])
        return res
    @app.get('/api/v1/auth/session')
    def session(user=Depends(require_user)):return {'username':user['username'],'role':user['role']}
    @app.post('/api/v1/auth/logout')
    def logout(req:Request,user=Depends(require_csrf)):
        with conn() as db:db.execute('DELETE FROM sessions WHERE id_hash=?',(user['id_hash'],))
        audit(req,'auth.logout',user=user['username'])
        res=JSONResponse({'ok':True});res.delete_cookie(COOKIE);res.delete_cookie(CSRF_COOKIE);return res
    # User administration is Super Admin only, protected by session-bound CSRF.
    # Never return password hashes or session tokens to clients.
    @app.get('/api/v1/backups/overview')
    def backup_overview(user=Depends(require_role({'super_admin','admin'}))):
        # Read-only inventory; never open or serve the archive, its contents or private configs.
        root=Path(os.environ.get('DOCKERFORGE_BACKUP_ROOT','/var/backups/dockerforge'))
        conf=Path(os.environ.get('DOCKERFORGE_DATA_BACKUP_CONFIG','/etc/dockerforge/data-backup.json'))
        config={'enabled':False,'keep':None,'volumes':[],'binds':[],'available':False}
        try:
            if conf.is_file() and not conf.is_symlink():
                raw=json.loads(conf.read_text())
                config={'enabled':raw.get('enabled') is True,'keep':raw.get('keep'),
                        'volumes':raw.get('volumes',[]),'binds':raw.get('binds',[]),'available':True}
        except (OSError,ValueError,TypeError,PermissionError):pass
        archives=[]
        for kind,folder in [('application',root),('volume',root/'volumes'),('bind',root/'binds')]:
            try:
                if folder.is_symlink():continue
                for f in folder.iterdir():
                    if f.is_symlink() or not f.is_file() or not f.name.endswith('.tar.gz'):continue
                    if not f.name.startswith('dockerforge-'):continue
                    st=f.stat()
                    archives.append({'name':f.name,'kind':kind,'bytes':st.st_size,'modified':int(st.st_mtime)})
            except (OSError,PermissionError):pass
        archives.sort(key=lambda x:x['modified'],reverse=True)
        return {'configuration':config,'archives':archives[:100],
                'archive_count':len(archives),
                'note':'Read-only inventory. A listed archive is not proof of verification. Systemd timers are managed separately.'}

    @app.get('/api/v1/users')
    def users_list(user=Depends(require_role({'super_admin'}))):
        with conn() as db:
            rows=db.execute('SELECT id,username,role,created_at FROM users ORDER BY username').fetchall()
        return {'items':[dict(r) for r in rows]}

    @app.post('/api/v1/users',status_code=201)
    def users_create(body:ManagedUser,req:Request,user=Depends(require_csrf)):
        if user['role']!='super_admin':fail('FORBIDDEN','Super Admin required',403)
        if body.role not in ROLES:fail('INVALID_ROLE','Unknown role',422)
        try:
            with conn() as db:
                row=db.execute('INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)',
                    (body.username,_ph.hash(body.password),body.role,int(time.time())))
                created_id=row.lastrowid
        except sqlite3.IntegrityError:fail('USER_EXISTS','Username already exists',409)
        audit(req,'user.create',user=user['username'],resource=body.username,metadata={'role':body.role})
        return {'id':created_id,'username':body.username,'role':body.role}

    @app.put('/api/v1/users/{ident}/role')
    def users_role(ident:int,body:RoleUpdate,req:Request,user=Depends(require_csrf)):
        if user['role']!='super_admin':fail('FORBIDDEN','Super Admin required',403)
        if body.role not in ROLES:fail('INVALID_ROLE','Unknown role',422)
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            target=db.execute('SELECT id,username,role FROM users WHERE id=?',(ident,)).fetchone()
            if not target:fail('USER_NOT_FOUND','Unknown user',404)
            if target['id']==user['id'] and body.role!='super_admin':fail('SELF_DEMOTION','Cannot demote your own Super Admin account',409)
            if target['role']=='super_admin' and body.role!='super_admin' and db.execute("SELECT COUNT(*) FROM users WHERE role='super_admin'").fetchone()[0]<=1:
                fail('LAST_SUPER_ADMIN','At least one Super Admin is required',409)
            db.execute('UPDATE users SET role=? WHERE id=?',(body.role,ident))
            if body.role!=target['role']:db.execute('DELETE FROM sessions WHERE user_id=?',(ident,))
        audit(req,'user.role_change',user=user['username'],resource=target['username'],metadata={'role':body.role})
        return {'ok':True,'username':target['username'],'role':body.role}

    @app.put('/api/v1/users/{ident}/password')
    def users_password(ident:int,body:PasswordReset,req:Request,user=Depends(require_csrf)):
        if user['role']!='super_admin':fail('FORBIDDEN','Super Admin required',403)
        with conn() as db:
            target=db.execute('SELECT username FROM users WHERE id=?',(ident,)).fetchone()
            if not target:fail('USER_NOT_FOUND','Unknown user',404)
            db.execute('UPDATE users SET password_hash=? WHERE id=?',(_ph.hash(body.password),ident))
            db.execute('DELETE FROM sessions WHERE user_id=?',(ident,))
        audit(req,'user.password_reset',user=user['username'],resource=target['username'])
        return {'ok':True}

    @app.delete('/api/v1/users/{ident}')
    def users_delete(ident:int,req:Request,user=Depends(require_csrf)):
        if user['role']!='super_admin':fail('FORBIDDEN','Super Admin required',403)
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            target=db.execute('SELECT username,role FROM users WHERE id=?',(ident,)).fetchone()
            if not target:fail('USER_NOT_FOUND','Unknown user',404)
            if ident==user['id']:fail('SELF_DELETE','Cannot delete your own user',409)
            if target['role']=='super_admin' and db.execute("SELECT COUNT(*) FROM users WHERE role='super_admin'").fetchone()[0]<=1:
                fail('LAST_SUPER_ADMIN','At least one Super Admin is required',409)
            db.execute('DELETE FROM sessions WHERE user_id=?',(ident,))
            db.execute('DELETE FROM users WHERE id=?',(ident,))
        audit(req,'user.delete',user=user['username'],resource=target['username'])
        return {'deleted':True}

    @app.get('/api/v1/users/{ident}/sessions')
    def user_sessions(ident:int,user=Depends(require_role({'super_admin'}))):
        with conn() as db:
            target=db.execute('SELECT id FROM users WHERE id=?',(ident,)).fetchone()
            if not target:fail('USER_NOT_FOUND','Unknown user',404)
            rows=db.execute('SELECT created_at,last_seen,expires_at,id_hash FROM sessions WHERE user_id=? ORDER BY created_at DESC',(ident,)).fetchall()
        # Never disclose hashes or raw session tokens.
        return {'items':[{'created_at':r['created_at'],'last_seen':r['last_seen'],'expires_at':r['expires_at']} for r in rows], 'count':len(rows)}

    @app.post('/api/v1/users/{ident}/revoke-sessions')
    def revoke_user_sessions(ident:int,req:Request,user=Depends(require_csrf)):
        if user['role']!='super_admin':fail('FORBIDDEN','Super Admin required',403)
        with conn() as db:
            target=db.execute('SELECT username FROM users WHERE id=?',(ident,)).fetchone()
            if not target:fail('USER_NOT_FOUND','Unknown user',404)
            result=db.execute('DELETE FROM sessions WHERE user_id=?',(ident,))
            count=result.rowcount
        audit(req,'user.sessions_revoke',user=user['username'],resource=target['username'],metadata={'count':count})
        return {'ok':True,'revoked':count}

    @app.get('/api/v1/audit')
    def audit_list(limit:int=50,user=Depends(require_role(ADMINS))):
        with conn() as db:rows=db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT ?', (max(1,min(limit,200)),)).fetchall()
        return {'items':[dict(r) for r in rows]}
    @app.get('/api/v1/system/diagnostics')
    def diag(user=Depends(require_role(ADMINS))):
        from app.system.health import get_docker_diagnostics
        return {'docker':get_docker_diagnostics(provider())}
    @app.get('/api/v1/docker/{kind}')
    def resources(kind:str,user=Depends(require_role(READ))):
        methods={'containers':'list_containers','images':'list_images','networks':'list_networks','volumes':'list_volumes'}
        if kind not in methods:fail('NOT_FOUND','Unsupported resource',404)
        try:return {'items':getattr(provider(),methods[kind])()}
        except Exception:fail('DOCKER_UNAVAILABLE','Docker resource listing unavailable',503)
    def _mutate(req, user, action, ident, operation):
        try:
            result=operation()
            audit(req,(action if '.' in action else 'container.'+action),user=user['username'],resource=ident)
            return {'ok':True,'result':result}
        except DockerOperationError as exc:
            audit(req,(action if '.' in action else 'container.'+action),'denied',user=user['username'],resource=ident,metadata={'code':exc.code})
            fail(exc.code,str(exc),exc.status_code)
        except (ValueError,TypeError):
            fail('INVALID_CONTAINER','Invalid container identifier or configuration',422)

    @app.get('/api/v1/system/host')
    def host_metrics(user=Depends(require_role(READ))):
        from app.system.host_stats import host_snapshot
        try:return host_snapshot()
        except (OSError, ValueError):fail('HOST_UNAVAILABLE','Host metrics are unavailable',503)

    @app.get('/api/v1/stacks/{name}/definition')
    def stack_definition(name:str,user=Depends(require_role(ADMINS))):
        try:return read_stack(name)
        except (ValueError,FileNotFoundError):fail('STACK_NOT_FOUND','Invalid or unknown stack',404)

    @app.get('/api/v1/stacks')
    def stacks(user=Depends(require_role(READ))):return {'items':list_stacks()}

    @app.post('/api/v1/stacks',status_code=201)
    def stack_create(body:StackDefinition,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        try:result=create_stack(body)
        except PermissionError:fail('ACK_REQUIRED','Explicit host-risk acknowledgement required',403)
        except FileExistsError:fail('STACK_EXISTS','Stack already exists',409)
        except ValueError:fail('INVALID_STACK','Invalid stack name or definition',422)
        except ComposeFailure:fail('COMPOSE_INVALID','Compose validation failed or Docker Compose unavailable',422)
        audit(req,'stack.create',user=user['username'],resource=body.name)
        return result

    @app.put('/api/v1/stacks/{name}/definition')
    def stack_update(name:str,body:StackDefinition,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        if body.name!=name:fail('INVALID_STACK','Stack name cannot be changed',422)
        try:result=update_stack(name,body.yaml,body.acknowledge_host_risk)
        except PermissionError:fail('ACK_REQUIRED','Explicit host-risk acknowledgement required',403)
        except (ValueError,FileNotFoundError):fail('INVALID_STACK','Invalid or unknown stack',422)
        except ComposeFailure:fail('COMPOSE_INVALID','Compose configuration validation failed',422)
        audit(req,'stack.update',user=user['username'],resource=name)
        return result

    @app.post('/api/v1/stacks/{name}/{action}')
    def stack_control(name:str,action:str,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        if action not in ('up','stop','start','down'):fail('NOT_FOUND','Unsupported stack action',404)
        try:result=stack_action(name,action)
        except (ValueError,FileNotFoundError):fail('STACK_NOT_FOUND','Invalid or unknown stack',404)
        except ComposeFailure as exc:
            audit(req,'stack.'+action,'denied',user=user['username'],resource=name,metadata={'category':exc.category})
            if exc.category == 'port_conflict':
                fail('COMPOSE_PORT_CONFLICT','A required host port is already in use. Stop the conflicting service or change the published port.',409)
            if exc.category == 'permission':
                fail('COMPOSE_PERMISSION_DENIED','Docker Compose cannot access a required resource',503)
            if exc.category == 'image_unavailable':
                fail('COMPOSE_IMAGE_UNAVAILABLE','Compose image could not be obtained',422)
            fail('COMPOSE_FAILED','Docker Compose operation failed; check project configuration and host resources',502)
        audit(req,'stack.'+action,user=user['username'],resource=name)
        return result

    @app.get('/api/v1/containers/{ident}/logs')
    def container_logs(ident:str,tail:int=100,timestamps:bool=False,user=Depends(require_role(OPS))):
        # Logs routinely contain credentials; viewers get status and metrics only.
        try:return fetch_logs(ident,tail,timestamps)
        except ValueError:fail('INVALID_REQUEST','Invalid container or tail count',422)
        except RuntimeError:fail('DOCKER_LOGS_FAILED','Unable to retrieve container logs',502)

    def _container_name(ident):
        try:return (provider().inspect_container(valid_id(ident)).get('Name') or '').lstrip('/') or ident
        except DockerOperationError:return ident

    def _edit_call(req,user,action,ident,operation):
        try:result=operation()
        except container_edit.EditError as exc:
            audit(req,action,'denied',user=user['username'],resource=ident,metadata={'code':exc.code})
            fail(exc.code,exc.message,exc.status)
        except DockerOperationError as exc:
            audit(req,action,'denied',user=user['username'],resource=ident,metadata={'code':exc.code})
            fail(exc.code,str(exc),exc.status_code)
        except ValueError:fail('INVALID_CONTAINER','Invalid container identifier',422)
        audit(req,action,user=user['username'],resource=ident,metadata=result)
        return result

    @app.get('/api/v1/containers/{ident}/edit')
    def container_edit_spec(ident:str,user=Depends(require_role(ADMINS))):
        try:
            p=provider();details=p.inspect_container(valid_id(ident))
            try:image=p.inspect_image(details.get('Image') or (details.get('Config') or {}).get('Image'))
            except DockerOperationError:image={}
        except DockerOperationError as exc:fail(exc.code,str(exc),exc.status_code)
        except ValueError:fail('INVALID_CONTAINER','Invalid container identifier',422)
        try:spec=container_edit.edit_spec(details,image)
        except (ValueError,TypeError,KeyError):fail('INVALID_CONTAINER','Container settings could not be read for editing',422)
        backup=SqliteBackupStore().get(spec['name'])
        return {**spec,'backup':{'old_name':backup['old_name'],'created_at':backup['created_at']} if backup else None}

    @app.post('/api/v1/containers/{ident}/resources')
    def container_resources(ident:str,body:ResourceUpdate,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        update={'RestartPolicy':{'Name':body.restart}}
        # Removing a memory limit needs a recreate; Docker refuses Memory=0 on update.
        # Swap at twice the memory matches Docker's default for a new limit.
        if body.memory_mb:update.update(Memory=body.memory_mb*1024*1024,MemorySwap=2*body.memory_mb*1024*1024)
        if body.nano_cpus is not None:
            update['NanoCpus']=body.nano_cpus
            if body.nano_cpus:update.update(CpuQuota=0,CpuPeriod=0)
        return _edit_call(req,user,'container.resources',ident,lambda:provider().update_container(valid_id(ident),update) or {'updated':True})

    @app.post('/api/v1/containers/{ident}/rename')
    def container_rename(ident:str,body:RenameRequest,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        old=_container_name(ident)
        def run():
            provider().rename_container(valid_id(ident),body.name);SqliteBackupStore().rename(old,body.name)
            return {'name':body.name}
        return _edit_call(req,user,'container.rename',ident,run)

    @app.post('/api/v1/containers/{ident}/networks/{network}/{op}')
    def container_network(ident:str,network:str,op:str,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        if op not in ('connect','disconnect'):fail('NOT_FOUND','Unknown network operation',404)
        if network in ('host','none'):fail('INVALID_NETWORK','Built-in host/none networks cannot be attached this way',422)
        call=provider().connect_network if op=='connect' else provider().disconnect_network
        return _edit_call(req,user,'container.network_'+op,ident,lambda:call(valid_id(network),valid_id(ident)) or {'network':network})

    @app.post('/api/v1/containers/{ident}/recreate')
    def container_recreate(ident:str,body:container_edit.ContainerEdit,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        return _edit_call(req,user,'container.recreate',ident,lambda:container_edit.recreate(provider(timeout=RECREATE_TIMEOUT),valid_id(ident),body,SqliteBackupStore(),int(time.time()),settle=RECREATE_SETTLE))

    @app.post('/api/v1/containers/{ident}/rollback')
    def container_rollback(ident:str,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        return _edit_call(req,user,'container.rollback',ident,lambda:container_edit.rollback(provider(),_container_name(ident),SqliteBackupStore()))

    @app.delete('/api/v1/containers/{ident}/backup')
    def container_backup_remove(ident:str,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        return _edit_call(req,user,'container.backup_remove',ident,lambda:container_edit.remove_backup(provider(),_container_name(ident),SqliteBackupStore()))

    @app.post('/api/v1/containers/{ident}/exec')
    def container_exec(ident:str,body:ExecCommand,req:Request,user=Depends(require_csrf)):
        if user['role'] not in OPS:fail('FORBIDDEN','Operator permission required',403)
        # High-risk containers require Admin. A bind mount, host namespace or
        # privilege elevation can make operator exec equivalent to host root.
        try:details=provider().inspect_container(valid_id(ident))
        except (DockerOperationError,ValueError):fail('CONTAINER_UNAVAILABLE','Container unavailable',404)
        host=details.get('HostConfig') or {}
        high=bool(host.get('Privileged') or host.get('PidMode')=='host' or
                  host.get('NetworkMode')=='host' or host.get('Binds') or
                  host.get('Devices') or host.get('CapAdd') or
                  any(m.get('Type')=='bind' for m in details.get('Mounts',[])))
        if high and user['role'] not in ADMINS:fail('FORBIDDEN','High-risk container exec requires Admin',403)
        # Audit only command invocation, never argv or output (may contain secrets).
        audit(req,'container.exec',user=user['username'],resource=ident,metadata={'high_risk':high})
        try:return exec_container(ident,body)
        except ValueError:fail('INVALID_EXEC','Invalid exec command',422)
        except RuntimeError:fail('EXEC_FAILED','Container command failed or timed out',502)

    @app.get('/api/v1/containers/{ident}')
    def inspect_container(ident:str,user=Depends(require_role(READ))):
        try:
            details=provider().inspect_container(valid_id(ident))
            return details if user['role'] in ADMINS else redact_env(details)
        except DockerOperationError as exc:fail(exc.code,str(exc),exc.status_code)
        except ValueError:fail('INVALID_CONTAINER','Invalid container identifier',422)

    @app.get('/api/v1/containers/{ident}/stats')
    def container_stats(ident:str,user=Depends(require_role(READ))):
        try:return provider().container_stats(valid_id(ident))
        except DockerOperationError as exc:fail(exc.code,str(exc),exc.status_code)
        except ValueError:fail('INVALID_CONTAINER','Invalid container identifier',422)

    @app.get('/api/v1/monitoring/collector')
    def monitoring_collector(user=Depends(require_role(READ))):
        status_path=Path(os.environ.get('DOCKERFORGE_METRICS_STATUS','/var/lib/dockerforge/metrics-collector.json'))
        try:
            state=json.loads(status_path.read_text(encoding='utf-8'))
            age=max(0,int(time.time())-int(state.get('last_attempt',0)))
            return {'active':age<=20,'age_seconds':age,'state':state.get('state','unknown'),
                    'running':state.get('running',0),'collected':state.get('collected',0),
                    'failed':state.get('failed',0),'last_success':state.get('last_success'),
                    'duration_ms':state.get('duration_ms'),'interval_seconds':state.get('interval_seconds',5),
                    'overrun':state.get('overrun',False),'alerts':state.get('alerts',[]),
                    'alert_count':state.get('alert_count',0),
                    'last_success_age_seconds': (max(0,int(time.time())-int(state['last_success'])) if state.get('last_success') else None)}
        except (OSError,ValueError,TypeError):
            return {'active':False,'state':'unavailable','age_seconds':None}

    @app.get('/api/v1/monitoring/alert-rules')
    def get_alert_rules(user=Depends(require_role(READ))):
        from app.monitoring.alert_rules import list_rules
        return {'items':list(list_rules().values())}

    @app.put('/api/v1/monitoring/alert-rules/{ident}')
    def put_alert_rule(ident:str,body:dict,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        from app.monitoring.alert_rules import AlertRule,set_rule
        try:
            rule=AlertRule(**{**body,'container_id':ident}).valid()
            value=set_rule(rule)
        except (ValueError,TypeError):fail('INVALID_RULE','Invalid alert rule',422)
        audit(req,'monitoring.alert_rule.update',user=user['username'],resource=ident)
        return value

    @app.delete('/api/v1/monitoring/alert-rules/{ident}')
    def remove_alert_rule(ident:str,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        from app.monitoring.alert_rules import delete_rule
        try: existed=delete_rule(ident)
        except ValueError:fail('INVALID_RULE','Invalid container ID',422)
        audit(req,'monitoring.alert_rule.delete',user=user['username'],resource=ident)
        return {'deleted':existed}

    @app.get('/api/v1/monitoring/notifications/config')
    def get_notification_config(user=Depends(require_role(READ))):
        from app.monitoring.alert_rules import smtp_configuration
        return smtp_configuration()

    @app.post('/api/v1/monitoring/notifications/test')
    def send_test_notification(req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        from app.monitoring.alert_rules import test_notification
        status=test_notification()
        audit(req,'monitoring.notification.test',user=user['username'],metadata={'result':status})
        return {'delivery':status}

    @app.get('/api/v1/monitoring/alerts')
    def get_alerts(user=Depends(require_role(READ))):
        from app.monitoring.alert_rules import list_alerts
        return list_alerts()

    @app.post('/api/v1/monitoring/alerts/ack')
    def ack_alert(body:dict,req:Request,user=Depends(require_csrf)):
        if user['role'] not in OPS:fail('FORBIDDEN','Operator required',403)
        from app.monitoring.alert_rules import acknowledge
        key=body.get('key','')
        if not isinstance(key,str) or len(key)>100:fail('INVALID_ALERT','Invalid alert key',422)
        if not acknowledge(key,user['username']):fail('ALERT_NOT_FOUND','Alert not active',404)
        audit(req,'monitoring.alert.ack',user=user['username'],resource=key)
        return {'acknowledged':True}

    @app.get('/api/v1/containers/{ident}/metrics')
    def container_metrics(ident:str,user=Depends(require_role(READ))):
        from app.monitoring.history import cached_sample
        try:
            ident = valid_id(ident)
            return cached_sample(ident, lambda: provider().container_stats(ident), os.environ.get('DOCKERFORGE_METRICS_DB', '/var/lib/dockerforge/metrics.db'))
        except DockerOperationError as exc:fail(exc.code,str(exc),exc.status_code)
        except ValueError:fail('INVALID_CONTAINER','Invalid container identifier',422)

    @app.get('/api/v1/containers/{ident}/metrics/history')
    def container_metrics_history(ident:str,window:str='1h',user=Depends(require_role(READ))):
        from app.monitoring.history import query_history
        try:return query_history(valid_id(ident),window,os.environ.get('DOCKERFORGE_METRICS_DB','/var/lib/dockerforge/metrics.db'))
        except ValueError:fail('INVALID_REQUEST','Invalid container identifier or window',422)

    @app.post('/api/v1/containers',status_code=201)
    def create_container(body:CreateContainer,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Container creation requires Admin',403)
        if body.high_risk() and not body.acknowledge_high_risk:fail('HIGH_RISK_CONFIRMATION_REQUIRED','Explicit acknowledgement required for host-level Docker options',403)
        try: payload=body.docker_payload()
        except ValueError:fail('INVALID_CONTAINER','Invalid container configuration',422)
        try:
            if body.port_bindings:
                validate_port_availability([b.model_dump() for b in body.port_bindings], provider().list_containers())
        except ValueError as exc:
            fail('PORT_CONFLICT',str(exc),409)
        result = _mutate(req,user,'create',body.name,lambda:provider().create_container(body.name,payload))
        return result

    @app.post('/api/v1/containers/create-and-start',status_code=201)
    def create_and_start(body:CreateContainer,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        if body.high_risk() and not body.acknowledge_high_risk:fail('HIGH_RISK_CONFIRMATION_REQUIRED','Explicit acknowledgement required',403)
        try:
            payload=body.docker_payload()
            validate_port_availability([b.model_dump() for b in body.port_bindings],provider().list_containers())
        except ValueError as exc:fail('INVALID_CONTAINER',str(exc),409)
        p=provider()
        created=_mutate(req,user,'create',body.name,lambda:p.create_container(body.name,payload))
        ident=created['result']['Id']
        try:
            started=_mutate(req,user,'start',ident,lambda:p.start_container(ident))
            return {'created':created['result'],'started':True}
        except HTTPException:
            # Keep the created container for inspection; do not destroy possible volumes.
            raise

    @app.post('/api/v1/images/pull')
    def pull_image(body:ImagePull,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        return _mutate(req,user,'image.pull',body.image,lambda:provider().pull_image(body.image))

    @app.delete('/api/v1/images/{ident:path}')
    def delete_image(ident:str,body:TypedDelete,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        if body.confirm_name != ident:fail('CONFIRMATION_MISMATCH','Type exact image ID or reference',409)
        return _mutate(req,user,'image.delete',ident,lambda:provider().delete_image(ident))

    @app.post('/api/v1/networks',status_code=201)
    def create_network(body:NetworkCreate,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        return _mutate(req,user,'network.create',body.name,lambda:provider().create_network(body.name,body.driver))

    @app.delete('/api/v1/networks/{ident}')
    def delete_network(ident:str,body:TypedDelete,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        if body.confirm_name != ident:fail('CONFIRMATION_MISMATCH','Type exact network name or ID',409)
        if ident in ('bridge','host','none'):fail('PROTECTED_NETWORK','Built-in network cannot be deleted',403)
        return _mutate(req,user,'network.delete',ident,lambda:provider().delete_network(valid_id(ident)))

    @app.post('/api/v1/volumes',status_code=201)
    def create_volume(body:VolumeCreate,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        return _mutate(req,user,'volume.create',body.name,lambda:provider().create_volume(body.name))

    @app.delete('/api/v1/volumes/{ident}')
    def delete_volume(ident:str,body:TypedDelete,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Admin required',403)
        if body.confirm_name != ident:fail('CONFIRMATION_MISMATCH','Type exact volume name',409)
        return _mutate(req,user,'volume.delete',ident,lambda:provider().delete_volume(safe_resource_name(ident)))

    @app.post('/api/v1/containers/{ident}/{action}')
    def control_container(ident:str,action:str,req:Request,user=Depends(require_csrf)):
        allowed={'start','stop','restart','pause','unpause'}
        if action not in allowed:fail('NOT_FOUND','Unknown container operation',404)
        if user['role'] not in OPS:fail('FORBIDDEN','Insufficient permission',403)
        return _mutate(req,user,action,ident,lambda:getattr(provider(),action+'_container')(ident))

    @app.delete('/api/v1/containers/{ident}')
    def delete_container(ident:str, body:DeleteConfirmation,req:Request,user=Depends(require_csrf)):
        if user['role'] not in ADMINS:fail('FORBIDDEN','Deletion requires Admin',403)
        if body.confirm_name != ident:fail('CONFIRMATION_MISMATCH','Type the exact container ID or name to delete',409)
        if body.remove_volumes:fail('VOLUME_DELETE_BLOCKED','Container deletion with volume removal is disabled in Task 6',403)
        return _mutate(req,user,'delete',ident,lambda:provider().delete_container(ident,force=body.force))

    @app.get('/api/v1/dashboard')
    def dashboard(user=Depends(require_role(READ))):
        import os
        result={'docker_available':False,'containers':None,'running':None,'stopped':None,'paused':None,'images':None,'networks':None,'volumes':None,'load_average':list(os.getloadavg())}
        try:
            p=provider(); containers=p.list_containers(); running=sum(c.get('State')=='running' for c in containers); paused=sum(c.get('State')=='paused' for c in containers); result.update(docker_available=p.ping(),containers=len(containers),running=running,paused=paused,stopped=len(containers)-running-paused,images=len(p.list_images()),networks=len(p.list_networks()),volumes=len(p.list_volumes()))
        except Exception:pass
        return result
    return app
