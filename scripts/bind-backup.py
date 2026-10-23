#!/usr/bin/env python3
"""Explicit, offline-only bind directory backup to verified archive; restore to new staging only."""
import argparse, os, json, subprocess, sys, re
from pathlib import Path
from importlib.machinery import SourceFileLoader
volume=SourceFileLoader('volume_backup',str(Path(__file__).with_name('volume-backup.py'))).load_module()

class Failure(Exception):pass

def check_source(src, allowed):
    if os.geteuid():raise Failure('root required')
    if not src.is_absolute() or src.is_symlink() or not src.is_dir():raise Failure('absolute existing real directory required')
    src=src.resolve(strict=True)
    if allowed.is_symlink():raise Failure('symlinked allow-root forbidden')
    allow=allowed.resolve(strict=True)
    if not allow.is_dir() or allow in (Path('/'),Path('/var')):raise Failure('Unsafe allow-root')
    if not src.is_relative_to(allow):raise Failure('source outside explicitly approved root')
    forbidden=(Path('/proc'),Path('/sys'),Path('/dev'),Path('/run'),Path('/etc'),Path('/root'),Path('/var/lib/docker'),Path('/var/lib/dockerforge'))
    if any(src==p or src.is_relative_to(p) for p in forbidden):raise Failure('system/DockerForge paths prohibited')
    result=subprocess.run(['docker','ps','-aq'],capture_output=True,text=True,timeout=30)
    if result.returncode:raise Failure('Cannot check Docker container bind mounts')
    ids=result.stdout.split()
    if ids:
        inspection=subprocess.run(['docker','inspect',*ids],capture_output=True,text=True,timeout=60)
        if inspection.returncode:raise Failure('Docker inspect failed')
        for container in json.loads(inspection.stdout):
            for mount in container.get('Mounts') or []:
                if mount.get('Type')!='bind':continue
                bound=Path(mount['Source']).resolve()
                if src==bound or src.is_relative_to(bound) or bound.is_relative_to(src):
                    raise Failure('Path overlaps container bind mount; manual consistent/offline backup required')
    return src

def main():
    p=argparse.ArgumentParser(description=__doc__)
    subs=p.add_subparsers(dest='op',required=True)
    c=subs.add_parser('create');c.add_argument('directory',type=Path);c.add_argument('--allow-root',type=Path,required=True);c.add_argument('--dest',type=Path,default=Path('/var/backups/dockerforge/binds'))
    v=subs.add_parser('verify');v.add_argument('archive',type=Path)
    r=subs.add_parser('restore-staging');r.add_argument('archive',type=Path);r.add_argument('new_directory',type=Path)
    args=p.parse_args()
    if args.op=='create':
        src=check_source(args.directory,args.allow_root)
        # Reuse hardened archive writer while supplying a synthetic name, no Docker volume modification.
        slug=re.sub('[^A-Za-z0-9_.-]','_',str(src).strip('/'))[:100]
        if not slug:raise Failure('invalid directory')
        volume.inspect_volume=lambda name: src
        volume.docker=lambda args: '' # container-overlap was independently checked above
        volume.create('bind_'+slug,args.dest)
    elif args.op=='verify':volume.verify(args.archive)
    else:volume.restore(args.archive,args.new_directory)
if __name__=='__main__':
    try:main()
    except (Failure,volume.BackupFailure,OSError,ValueError,subprocess.TimeoutExpired,json.JSONDecodeError) as e:
        print('BIND_BACKUP_ERROR:',e,file=sys.stderr);sys.exit(1)
