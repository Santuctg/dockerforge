import importlib.util
import sqlite3
from pathlib import Path
import pytest

SCRIPT=Path(__file__).resolve().parents[2]/'scripts'/'backup-manager.py'
spec=importlib.util.spec_from_file_location('backup_manager',SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_verified_backup_and_retention(tmp_path):
    source=tmp_path/'state';source.mkdir()
    cfg=tmp_path/'config';cfg.mkdir()
    (cfg/'dockerforge.env').write_text('PRIVATE=yes')
    (source/'stacks').mkdir();(source/'stacks'/'demo.yaml').write_text('services: {}')
    for name in ('dockerforge.db','metrics.db'):
        with sqlite3.connect(source/name) as c:c.execute('create table demo (id integer)')
    dest=tmp_path/'out'
    first=module.create(source,cfg,dest,keep=1)
    module.verify(first)
    assert first.stat().st_mode & 0o077 == 0
    second=module.create(source,cfg,dest,keep=1)
    assert second.exists()
    assert len(list(dest.glob('dockerforge-app-*.tar.gz')))==1

def test_rejects_missing_database(tmp_path):
    with pytest.raises(RuntimeError,match='Application database missing'):
        module.create(tmp_path,tmp_path,tmp_path/'dest',14)
