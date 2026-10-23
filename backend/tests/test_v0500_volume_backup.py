"""Offline-volume archive validation. No Docker daemon touched."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import pytest

SCRIPT=Path(__file__).resolve().parents[2]/'scripts'/'volume-backup.py'
spec=importlib.util.spec_from_file_location('volume_backup',SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def make_archive(path, data_name='data/hello.txt', payload=b'hello', checksum=None):
    m={'format':1,'name':'testvol','files':{'hello.txt':checksum or mod.sha_bytes(payload)}}
    with tarfile.open(path,'w:gz') as t:
        f=tarfile.TarInfo(data_name);f.size=len(payload);t.addfile(f,io.BytesIO(payload))
        b=json.dumps(m).encode()
        f=tarfile.TarInfo('manifest.json');f.size=len(b);t.addfile(f,io.BytesIO(b))

def test_verified_archive_and_staging_restore(tmp_path,monkeypatch):
    f=tmp_path/'test.tar.gz';make_archive(f)
    assert mod.verify(f)['name']=='testvol'
    monkeypatch.setattr(mod.os,'geteuid',lambda:0)
    target=tmp_path/'fresh'
    mod.restore(f,target)
    assert (target/'hello.txt').read_text()=='hello'
    with pytest.raises(mod.BackupFailure):mod.restore(f,target)

def test_checksum_mismatch_rejected(tmp_path):
    f=tmp_path/'bad.tar.gz';make_archive(f,checksum='0'*64)
    with pytest.raises(mod.BackupFailure,match='Checksum mismatch'):mod.scan(f)

def test_archive_traversal_rejected(tmp_path):
    f=tmp_path/'traversal.tar.gz';make_archive(f,data_name='data/../oops')
    with pytest.raises(mod.BackupFailure):mod.scan(f)

def test_invalid_volume_name_rejected():
    with pytest.raises(mod.BackupFailure):mod.inspect_volume('../test')
