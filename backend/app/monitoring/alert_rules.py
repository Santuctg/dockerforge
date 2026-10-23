"""Opt-in, local persistent alert rules and lifecycle. No secret-bearing telemetry."""
import json
import os
import re
import smtplib
import ssl
import time
from email.message import EmailMessage
from pathlib import Path
from threading import RLock
from pydantic import BaseModel, Field

LOCK = RLock()
ROOT = '/var/lib/dockerforge'
ID_RE = re.compile(r'^[a-f0-9]{12,64}$')

class AlertRule(BaseModel):
    container_id: str = Field(min_length=12,max_length=64)
    enabled: bool = True
    cpu_threshold: float = Field(default=90,gt=0,le=10000)
    memory_threshold: float = Field(default=90,gt=0,le=100)
    alert_on_stopped: bool = False

    def valid(self):
        if not ID_RE.fullmatch(self.container_id):
            raise ValueError('Container ID must be hexadecimal (12 to 64 characters)')
        return self

def _path():return Path(os.environ.get('DOCKERFORGE_ALERT_RULES', ROOT+'/alert-rules.json'))
def _state_path():return Path(os.environ.get('DOCKERFORGE_ALERT_STATE', ROOT+'/alert-state.json'))

def _read(path, default):
    try:
        obj=json.loads(path.read_text(encoding='utf-8'))
        return obj if isinstance(obj,dict) else default
    except (OSError,ValueError,TypeError):return default

def _write(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    try:
        temp.write_text(json.dumps(data,sort_keys=True),encoding='utf-8')
        temp.chmod(0o600)
        os.replace(temp,path)
    finally:
        try:temp.unlink(missing_ok=True)
        except OSError:pass

def list_rules():
    with LOCK:return _read(_path(),{})

def set_rule(rule:AlertRule):
    rule.valid()
    with LOCK:
        rules=_read(_path(),{})
        rules[rule.container_id]=rule.model_dump()
        _write(_path(),rules)
    return rule.model_dump()

def delete_rule(ident):
    if not ID_RE.fullmatch(ident):raise ValueError('Invalid container ID')
    with LOCK:
        rules=_read(_path(),{})
        existed=ident in rules
        rules.pop(ident,None)
        _write(_path(),rules)
    return existed

def list_alerts():
    with LOCK:return _read(_state_path(),{'active':{},'events':[]})

def acknowledge(key, actor):
    with LOCK:
        data=_read(_state_path(),{'active':{},'events':[]})
        item=data.get('active',{}).get(key)
        if not item:return False
        item['acknowledged_at']=int(time.time())
        item['acknowledged_by']=actor[:64]
        data.setdefault('events',[]).append({'event':'acknowledged','key':key,'type':item.get('type'),'actor':actor[:64],'ts':item['acknowledged_at']})
        data['events']=data['events'][-500:]
        _write(_state_path(),data)
        return True

def _smtp_enabled():
    return os.environ.get('DOCKERFORGE_ALERT_SMTP_ENABLED','false').lower()=='true'

def send_notification(alert):
    """Optional SMTP TLS delivery; never log credentials or SMTP error text."""
    if not _smtp_enabled():return 'disabled'
    host=os.environ.get('DOCKERFORGE_ALERT_SMTP_HOST','')
    sender=os.environ.get('DOCKERFORGE_ALERT_SMTP_FROM','')
    recipient=os.environ.get('DOCKERFORGE_ALERT_SMTP_TO','')
    if not host or not sender or not recipient:return 'unconfigured'
    try:
        port=int(os.environ.get('DOCKERFORGE_ALERT_SMTP_PORT','465'))
        if not 1<=port<=65535:return 'invalid_config'
        msg=EmailMessage()
        msg['From']=sender;msg['To']=recipient
        msg['Subject']='DockerForge container alert'
        msg.set_content('DockerForge alert: '+alert['type']+' for container '+alert['container_id']+' (key '+alert['key']+').')
        with smtplib.SMTP_SSL(host,port,context=ssl.create_default_context(),timeout=5) as conn:
            user=os.environ.get('DOCKERFORGE_ALERT_SMTP_USER','')
            password=os.environ.get('DOCKERFORGE_ALERT_SMTP_PASSWORD','')
            if user:conn.login(user,password)
            conn.send_message(msg)
        return 'sent'
    except Exception:return 'failed'

def reconcile(running, stopped, now=None, notifier=send_notification):
    """Alert only on transition to active; ack suppresses repeated delivery until recovery."""
    now=int(time.time() if now is None else now)
    rules=list_rules()
    desired={}
    for ident,rule in rules.items():
        if not rule.get('enabled',True):continue
        short=ident[:12]
        matching=[(cid,metrics) for cid,metrics in running.items() if cid==ident or cid.startswith(ident)]
        if matching:
            cid,metrics=matching[0]
            for metric,field,threshold in [('cpu_high','cpu_percent','cpu_threshold'),('memory_high','memory_percent','memory_threshold')]:
                if float(metrics.get(field,0))>=float(rule.get(threshold,90)):
                    key=ident+':'+metric
                    desired[key]={'key':key,'container_id':short,'type':metric,'value':metrics.get(field),'threshold':rule.get(threshold)}
        elif rule.get('alert_on_stopped') and any(cid==ident or cid.startswith(ident) for cid in stopped):
            key=ident+':container_stopped'
            desired[key]={'key':key,'container_id':short,'type':'container_stopped'}
    new=[]
    with LOCK:
        state=_read(_state_path(),{'active':{},'events':[]})
        previous=state.get('active',{})
        active={}
        events=state.get('events',[])
        for key,alert in desired.items():
            if key in previous:
                record=previous[key]
                record.update({k:v for k,v in alert.items() if k in ('value','threshold')})
            else:
                record={**alert,'since':now,'acknowledged_at':None,'acknowledged_by':None,'delivery':'pending'}
                events.append({'key':key,'type':alert['type'],'event':'firing','ts':now})
                new.append(key)
            active[key]=record
        for key,record in previous.items():
            if key not in active:events.append({'key':key,'type':record['type'],'event':'resolved','ts':now})
        state={'active':active,'events':events[-500:]}
        _write(_state_path(),state)
    # Only one collector service should own notification delivery; no delivery on reads.
    for key in new:
        outcome=notifier(active[key])
        with LOCK:
            current=_read(_state_path(),{'active':{},'events':[]})
            if key in current.get('active',{}):
                current['active'][key]['delivery']=outcome
                _write(_state_path(),current)
    return list(active.values())


def smtp_configuration():
    """Safe public status: never return SMTP credentials or host secrets."""
    host=os.environ.get('DOCKERFORGE_ALERT_SMTP_HOST','')
    return {'enabled':_smtp_enabled(), 'configured':bool(host and os.environ.get('DOCKERFORGE_ALERT_SMTP_FROM') and os.environ.get('DOCKERFORGE_ALERT_SMTP_TO')), 'transport':'SMTP over TLS (465)', 'delivery_queue':False}

def test_notification():
    """Explicit admin-triggered test; no credentials or remote SMTP errors returned."""
    if not _smtp_enabled():return 'disabled'
    if not smtp_configuration()['configured']:return 'unconfigured'
    return send_notification({'type':'test','container_id':'test','key':'smtp-test'})
