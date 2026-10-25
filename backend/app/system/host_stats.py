"""Read-only bounded Linux host snapshot; no shell or external services."""
from pathlib import Path
import os
import shutil
import time


def _mem():
    values={}
    try:
        lines=Path('/proc/meminfo').read_text().splitlines()
    except OSError:
        lines=[]
    for line in lines:
        k,sep,v=line.partition(':')
        if not sep or k not in ('MemTotal','MemAvailable','SwapTotal','SwapFree'):
            continue
        try: values[k]=int(v.strip().split()[0])*1024
        except (ValueError,IndexError): continue
    if not values:
        # Non-Linux hosts (or a stripped container) have no procfs; fall back to
        # sysconf so the endpoint still returns a usable snapshot.
        try:
            page=int(os.sysconf('SC_PAGE_SIZE'))
            values['MemTotal']=int(os.sysconf('SC_PHYS_PAGES'))*page
            values['MemAvailable']=int(os.sysconf('SC_AVPHYS_PAGES'))*page
        except (ValueError,OSError,AttributeError):
            pass
    return values


def _net():
    data={}
    try:
        lines=Path('/proc/net/dev').read_text().splitlines()[2:]
    except OSError:
        return data
    for line in lines:
        name,sep,values=line.partition(':')
        name=name.strip()
        if not sep or name=='lo' or not name or len(name)>64:continue
        fields=values.split()
        if len(fields)<16:continue
        try: data[name]={'rx_bytes':int(fields[0]),'tx_bytes':int(fields[8])}
        except ValueError: continue
    return data


def host_snapshot():
    memory=_mem()
    usage=shutil.disk_usage('/')
    load=os.getloadavg()
    return {'sampled_at':int(time.time()),'cpu_cores':os.cpu_count() or 1,
            'load_1m':round(load[0],3),'load_5m':round(load[1],3),'load_15m':round(load[2],3),
            'memory_total_bytes':memory.get('MemTotal',0),
            'memory_available_bytes':memory.get('MemAvailable',0),
            'swap_total_bytes':memory.get('SwapTotal',0),
            'swap_free_bytes':memory.get('SwapFree',0),
            'root_disk_total_bytes':usage.total,'root_disk_free_bytes':usage.free,
            'network_interfaces':_net()}
