#!/usr/bin/env python3
"""Opt-in DockerForge data backup job. Refuses failure-prone/missing configuration and logs failures."""
import argparse, json, os, pathlib, subprocess, sys, time
ROOT=pathlib.Path('/etc/dockerforge/data-backup.json')
ARCHIVE=pathlib.Path('/var/backups/dockerforge')

def run(args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=3600)
    if result.returncode:
        raise RuntimeError('Command failed: '+args[0]+' '+args[1]+' (exit '+str(result.returncode)+'): '+result.stderr[-1000:])
    print(result.stdout.strip(),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=pathlib.Path,default=ROOT)
    a=p.parse_args()
    if os.geteuid():raise RuntimeError('root required')
    if a.config.is_symlink() or not a.config.is_file() or a.config.stat().st_mode & 0o077:
        raise RuntimeError('Config missing, symlinked or not root-private (chmod 600)')
    data=json.loads(a.config.read_text())
    if data.get('enabled') is not True:raise RuntimeError('Data backup explicitly disabled; no work done')
    keep=data.get('keep',7)
    if type(keep)!=int or not 1<=keep<=90:raise RuntimeError('keep must be 1..90')
    vols=data.get('volumes',[]);binds=data.get('binds',[])
    if not isinstance(vols,list) or not isinstance(binds,list) or not vols and not binds:raise RuntimeError('No data backup targets configured')
    if len(vols)+len(binds)>50:raise RuntimeError('Too many targets')
    created=[]
    for name in vols:
        if not isinstance(name,str):raise RuntimeError('Invalid volume')
        run(['/usr/local/sbin/dockerforge-volume-backup','create',name]); created.append('volume')
    for binding in binds:
        if not isinstance(binding,dict) or set(binding)!={'directory','allow_root'}:raise RuntimeError('Invalid bind target')
        run(['/usr/local/sbin/dockerforge-bind-backup','create',binding['directory'],'--allow-root',binding['allow_root']]);created.append('bind')
    for folder,pattern in ((ARCHIVE/'volumes','dockerforge-volume-*.tar.gz'),(ARCHIVE/'binds','dockerforge-volume-*.tar.gz')):
        if not folder.exists():continue
        if folder.is_symlink():raise RuntimeError('Symlinked backup directory')
        items=sorted(folder.glob(pattern),key=lambda x:x.stat().st_mtime,reverse=True)
        # Keep backups per named target, not globally across unrelated data sources.
        groups={}
        for item in items:
            if item.is_symlink():raise RuntimeError('Symlink archive, abort retention')
            # Archive format: dockerforge-volume-<name>-YYYYMMDDTHHMMSSZ-<pid>.tar.gz
            prefix=item.name.rsplit('-',2)[0]
            groups.setdefault(prefix,[]).append(item)
        for group in groups.values():
            for old in group[keep:]:old.unlink()
    print('DATA_BACKUP_OK',len(created),'targets; keep',keep)
if __name__=='__main__':
    try:main()
    except Exception as exc:print('DATA_BACKUP_FAILED:',str(exc),file=sys.stderr);sys.exit(1)
