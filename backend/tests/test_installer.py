import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / 'installer' / 'lib.sh'


def sh(script, env=None):
    return subprocess.run(['bash', '-c', f'set -euo pipefail; source "{LIB}"; {script}'],
                          capture_output=True, text=True, env={**os.environ, **(env or {})})


def os_release(tmp_path, body, name='os-release'):
    path = tmp_path / name
    path.write_text(body)
    return path


def test_detect_family_known_ids(tmp_path):
    cases = [('ID=ubuntu', 'debian'), ('ID=debian', 'debian'), ('ID=rocky', 'rhel'),
             ('ID=almalinux', 'rhel'), ('ID=fedora', 'rhel'), ('ID="opensuse-leap"', 'suse'),
             ('ID=sles', 'suse')]
    for i, (body, family) in enumerate(cases):
        path = os_release(tmp_path, body + '\n', f'os-{i}')
        r = sh(f'detect_family "{path}"')
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == family


def test_detect_family_id_like(tmp_path):
    mint = os_release(tmp_path, 'ID=linuxmint\nID_LIKE="ubuntu debian"\n', 'mint')
    oracle = os_release(tmp_path, 'ID=ol\nID_LIKE="fedora"\n', 'ol')
    assert sh(f'detect_family "{mint}"').stdout.strip() == 'debian'
    assert sh(f'detect_family "{oracle}"').stdout.strip() == 'rhel'


def test_detect_family_unsupported(tmp_path):
    arch = os_release(tmp_path, 'ID=arch\n')
    r = sh(f'detect_family "{arch}"')
    assert r.returncode == 1
    assert 'Unsupported distribution: arch' in r.stderr


def test_pkg_manager():
    for family, manager in [('debian', 'apt-get'), ('rhel', 'dnf'), ('suse', 'zypper')]:
        assert sh(f'pkg_manager {family}').stdout.strip() == manager


def test_python_version_ok(tmp_path):
    assert sh(f'python_version_ok "{sys.executable}"').returncode == 0
    fake = tmp_path / 'fakepy'
    fake.write_text('#!/bin/sh\nexit 1\n')
    fake.chmod(0o755)
    assert sh(f'python_version_ok "{fake}"').returncode != 0


def test_ensure_env_file_creates_then_keeps(tmp_path):
    env = tmp_path / 'dockerforge.env'
    first = sh(f'ensure_env_file "{env}"')
    assert first.returncode == 0, first.stderr
    assert first.stdout.strip() == 'created'
    assert env.stat().st_mode & 0o777 == 0o640
    content = env.read_bytes()
    assert re.search(rb'^DOCKERFORGE_SETUP_TOKEN=[0-9a-f]{48}$', content, re.M)
    assert b'DOCKERFORGE_DB=/var/lib/dockerforge/dockerforge.db' in content
    second = sh(f'ensure_env_file "{env}"')
    assert second.stdout.strip() == 'kept'
    assert env.read_bytes() == content
