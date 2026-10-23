#!/usr/bin/env python3
"""DockerForge named-volume snapshots. Offline restore to NEW directory only.

This utility does not snapshot open databases consistently. Stop writers first.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import time

NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
DEFAULT_DEST = Path('/var/backups/dockerforge/volumes')

class BackupFailure(Exception):
    pass

def sha_bytes(payload):
    return hashlib.sha256(payload).hexdigest()

def docker(args):
    proc = subprocess.run(['docker', *args], capture_output=True, timeout=30,
                          env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':'/root',
                               'DOCKER_CONFIG':'/root/.docker','DOCKER_HOST':'unix:///var/run/docker.sock'})
    if proc.returncode:
        raise BackupFailure('Docker lookup failed; details omitted')
    return proc.stdout.decode('utf-8')

def inspect_volume(name):
    if not NAME.fullmatch(name):
        raise BackupFailure('Invalid volume name')
    data = json.loads(docker(['volume','inspect',name]))
    if len(data) != 1 or data[0]['Name'] != name or data[0].get('Driver') != 'local':
        raise BackupFailure('Only local named volumes are supported')
    # Refuse external/mounted plugin volumes, arbitrary host paths and bind-backed local volumes.
    opts = data[0].get('Options') or {}
    if opts:
        raise BackupFailure('Volume has driver options: require separate backup procedure')
    point = Path(data[0]['Mountpoint'])
    base = Path('/var/lib/docker/volumes')
    expected = base / name / '_data'
    if point != expected or expected.is_symlink() or expected.resolve() != expected:
        raise BackupFailure('Unexpected or symlinked volume mount point')
    if not expected.is_dir():
        raise BackupFailure('Volume data directory is missing')
    return expected

def get_members(source):
    result = []
    for root, dirs, files in os.walk(source, followlinks=False):
        relroot = Path(root).relative_to(source)
        for name in dirs + files:
            path = Path(root)/name
            mode = path.lstat().st_mode
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise BackupFailure('Symlink or special file present; backup refused: '+str(relroot/name))
            result.append((path, (relroot/name).as_posix()))
    return sorted(result,key=lambda item:item[1])

def create(name, dest, allow_in_use=False):
    if os.geteuid() != 0: raise BackupFailure('Root required')
    source = inspect_volume(name)
    if not allow_in_use and docker(['ps','-aq','--filter','volume='+name]).strip():
        raise BackupFailure('Volume referenced by a container; stop and detach writers first; --allow-in-use is crash-consistent at best')
    if dest.is_symlink(): raise BackupFailure('Destination symlink refused')
    dest.mkdir(mode=0o700,parents=True,exist_ok=True)
    dest.chmod(0o700)
    timestamp = time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    archive = dest / f'dockerforge-volume-{name}-{timestamp}-{os.getpid()}.tar.gz'
    with tempfile.NamedTemporaryFile(dir=dest,prefix='.pending-',delete=False) as temp:
        partial = Path(temp.name)
    try:
        members = get_members(source)
        checksums={}
        with tarfile.open(partial,'w:gz',format=tarfile.PAX_FORMAT) as tar:
            for path,relative in members:
                # Explicitly store under data/ and reject changes in file types during walk.
                if path.is_symlink() or not (path.is_file() or path.is_dir()):
                    raise BackupFailure('Source changed while archiving')
                info = tar.gettarinfo(str(path),arcname='data/'+relative)
                if info.isfile():
                    class HashingReader:
                        def __init__(self, stream):
                            self.stream=stream
                            self.digest=hashlib.sha256()
                        def read(self, length):
                            value=self.stream.read(length)
                            self.digest.update(value)
                            return value
                    with path.open('rb') as f:
                        reader=HashingReader(f)
                        tar.addfile(info,reader)
                        checksums[relative]=reader.digest.hexdigest()
                elif info.isdir():tar.addfile(info)
                else:raise BackupFailure('Unsupported source type')
            manifest={'format':1,'scope':'local Docker named volume', 'name':name,
                      'created_utc':timestamp,'consistent':not allow_in_use,
                      'files':checksums}
            payload=json.dumps(manifest,sort_keys=True).encode()
            info=tarfile.TarInfo('manifest.json');info.size=len(payload);info.mode=0o600
            tar.addfile(info,io.BytesIO(payload))
        os.chmod(partial,0o600)
        verify(partial)
        os.replace(partial,archive)
    finally:
        partial.unlink(missing_ok=True)
    print('VOLUME_BACKUP_OK',archive)
    return archive

def scan(archive):
    with tarfile.open(archive,'r:gz') as tar:
        manifest_entries=[m for m in tar.getmembers() if m.name=='manifest.json']
        if len(manifest_entries)!=1:raise BackupFailure('Manifest missing or duplicate')
        manifest=json.load(tar.extractfile(manifest_entries[0]))
        if manifest.get('format') != 1 or not NAME.fullmatch(manifest.get('name','')):
            raise BackupFailure('Invalid manifest')
        expected=manifest.get('files',{})
        if not isinstance(expected,dict):raise BackupFailure('Invalid checksum set')
        seen=set()
        for member in tar.getmembers():
            name=member.name
            p=Path(name)
            if p.is_absolute() or '..' in p.parts or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                raise BackupFailure('Unsafe archive entry')
            if name in seen:raise BackupFailure('Duplicate archive entry')
            seen.add(name)
            if name=='manifest.json':continue
            if not name.startswith('data/') or name=='data/':raise BackupFailure('Unexpected archive path')
            rel=name[5:].rstrip('/')
            if member.isfile():
                if rel not in expected:raise BackupFailure('Unlisted file')
                digest=hashlib.sha256()
                f=tar.extractfile(member)
                for chunk in iter(lambda:f.read(1048576),b''):digest.update(chunk)
                if digest.hexdigest()!=expected[rel]:raise BackupFailure('Checksum mismatch: '+rel)
        for rel in expected:
            if 'data/'+rel not in seen:raise BackupFailure('Missing file: '+rel)
        return manifest

def verify(archive):
    m=scan(archive)
    print('VOLUME_VERIFY_OK',m['name'],len(m['files']),'files')
    return m

def restore(archive,target):
    if os.geteuid()!=0:raise BackupFailure('Root required')
    m=scan(archive)
    if target.exists() or target.is_symlink():raise BackupFailure('Target already exists; only new empty target permitted')
    targetparent=target.parent.resolve(strict=True)
    if targetparent in (Path('/'),Path('/var/lib/docker'),Path('/var/lib/docker/volumes')) or str(targetparent).startswith('/var/lib/docker/volumes/'):
        raise BackupFailure('Direct Docker volume restore forbidden; restore to staging path')
    target.mkdir(mode=0o700)
    try:
        with tarfile.open(archive,'r:gz') as tar:
            for member in tar:
                if member.name=='manifest.json':continue
                rel=Path(member.name).relative_to('data')
                output=target/rel
                if member.isdir():
                    output.mkdir(parents=True,exist_ok=True)
                else:
                    output.parent.mkdir(parents=True,exist_ok=True)
                    with tar.extractfile(member) as src, output.open('xb') as dest:
                        while part:=src.read(1048576):dest.write(part)
                    os.chmod(output,member.mode & 0o777)
        print('VOLUME_RESTORE_STAGING_OK',m['name'],target)
    except BaseException:
        # Do not leave an apparently-valid partial restore.
        import shutil
        shutil.rmtree(target)
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_subparsers(dest='action',required=True)
    c=s.add_parser('create');c.add_argument('name');c.add_argument('--dest',type=Path,default=DEFAULT_DEST);c.add_argument('--allow-in-use',action='store_true')
    v=s.add_parser('verify');v.add_argument('archive',type=Path)
    r=s.add_parser('restore-staging');r.add_argument('archive',type=Path);r.add_argument('new_directory',type=Path)
    a=p.parse_args()
    if a.action=='create':create(a.name,a.dest,a.allow_in_use)
    if a.action=='verify':verify(a.archive)
    if a.action=='restore-staging':restore(a.archive,a.new_directory)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,subprocess.TimeoutExpired,tarfile.TarError,BackupFailure) as e:
        print('VOLUME_BACKUP_ERROR:',e,file=sys.stderr);sys.exit(1)
