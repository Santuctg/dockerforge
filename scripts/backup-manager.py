#!/usr/bin/env python3
"""DockerForge application-data snapshot utility (not Docker volumes)."""
import argparse, hashlib, json, os, shutil, sqlite3, stat, sys, tarfile, tempfile, time
from pathlib import Path

DEFAULT_SOURCE = Path('/var/lib/dockerforge')
DEFAULT_CONFIG = Path('/etc/dockerforge')
DEFAULT_DEST = Path('/var/backups/dockerforge')

def _sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def _sqlite_backup(src,dst):
    with sqlite3.connect(f'file:{src}?mode=ro',uri=True) as source,sqlite3.connect(dst) as target:
        source.backup(target)
        result=target.execute('PRAGMA integrity_check').fetchone()[0]
        if result!='ok':raise RuntimeError('SQLite backup integrity failed')

def _copy_if_exists(src,dst):
    if src.is_symlink():raise RuntimeError('Refusing symlink source: '+str(src))
    if src.is_dir():shutil.copytree(src,dst,symlinks=False)
    elif src.is_file():shutil.copy2(src,dst)

def create(source, config, destination, keep):
    os.umask(0o077)
    if not (source/'dockerforge.db').is_file():raise RuntimeError('Application database missing')
    if source.is_symlink() or destination.is_symlink():raise RuntimeError('Symlink directory not allowed')
    destination.mkdir(parents=True,exist_ok=True,mode=0o700)
    destination.chmod(0o700)
    now=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    with tempfile.TemporaryDirectory(prefix='.dockerforge-backup-',dir=destination) as staging:
        staging=Path(staging)
        files=staging/'files';files.mkdir(mode=0o700)
        _sqlite_backup(source/'dockerforge.db',files/'dockerforge.db')
        if (source/'metrics.db').is_file():_sqlite_backup(source/'metrics.db',files/'metrics.db')
        for name in ['stacks','alert-rules.json','alert-state.json']:_copy_if_exists(source/name,files/name)
        _copy_if_exists(config,files/'etc-dockerforge')
        # Secrets remain encrypted by filesystem permissions only; protect archives carefully.
        if any(p.is_symlink() for p in files.rglob('*')):raise RuntimeError('Symlinks in backup source are not allowed')
        checksums={str(p.relative_to(files)):_sha(p) for p in sorted(files.rglob('*')) if p.is_file()}
        (staging/'manifest.json').write_text(json.dumps({'format':1,'created_utc':now,'files':checksums,'scope':'application only; excludes docker volumes and bind mounts'},indent=2))
        temp=destination/('.pending-'+now+'-'+str(os.getpid())+'.tar.gz')
        with tarfile.open(temp,'w:gz') as tf:
            tf.add(files,arcname='files',recursive=True)
            tf.add(staging/'manifest.json',arcname='manifest.json')
        os.chmod(temp,0o600)
        final=destination/('dockerforge-app-'+now+'.tar.gz')
        if final.exists():final=destination/('dockerforge-app-'+now+'-'+str(os.getpid())+'.tar.gz')
        os.replace(temp,final)
    verify(final)
    archives=sorted(destination.glob('dockerforge-app-*.tar.gz'),key=lambda x:x.stat().st_mtime,reverse=True)
    for archive in archives[keep:]:archive.unlink()
    print('BACKUP_OK',final)
    return final

def verify(archive):
    with tarfile.open(archive,'r:gz') as tf:
        members=tf.getmembers()
        for m in members:
            p=Path(m.name)
            if p.is_absolute() or '..' in p.parts or not (m.isfile() or m.isdir()) or m.issym() or m.islnk():
                raise RuntimeError('Unsafe archive entry')
        manifest=json.load(tf.extractfile('manifest.json'))
        for name,expected in manifest['files'].items():
            member=tf.extractfile('files/'+name)
            if member is None:raise RuntimeError('Missing '+name)
            h=hashlib.sha256()
            for chunk in iter(lambda:member.read(1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=expected:raise RuntimeError('Checksum mismatch: '+name)
    print('VERIFY_OK',len(manifest['files']),'files')

def main():
    parser=argparse.ArgumentParser(description='DockerForge app backups; excludes Docker volumes/bind mounts')
    sub=parser.add_subparsers(dest='command',required=True)
    createp=sub.add_parser('create')
    createp.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    createp.add_argument('--config',type=Path,default=DEFAULT_CONFIG)
    createp.add_argument('--dest',type=Path,default=DEFAULT_DEST)
    createp.add_argument('--keep',type=int,default=14)
    check=sub.add_parser('verify');check.add_argument('archive',type=Path)
    args=parser.parse_args()
    if args.command=='create':
        if os.geteuid()!=0:raise SystemExit('Root required for secrets/database consistency')
        if not 1<=args.keep<=365:raise SystemExit('keep must be 1..365')
        create(args.source,args.config,args.dest,args.keep)
    else:verify(args.archive)
if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,tarfile.TarError) as exc:print('BACKUP_ERROR',exc,file=sys.stderr);sys.exit(1)
