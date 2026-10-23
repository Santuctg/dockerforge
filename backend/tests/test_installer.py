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


def test_service_unit_contents():
    unit = (REPO / 'systemd' / 'dockerforge.service').read_text()
    lines = set(unit.splitlines())
    for expected in ['User=dockerforge', 'EnvironmentFile=/etc/dockerforge/dockerforge.env',
                     'WorkingDirectory=/opt/dockerforge/backend', 'NoNewPrivileges=true',
                     'ProtectSystem=strict', 'ProtectHome=true', 'PrivateTmp=true',
                     'ReadWritePaths=/var/lib/dockerforge', 'Restart=on-failure',
                     'WantedBy=multi-user.target']:
        assert expected in lines
    exec_start = next(l for l in lines if l.startswith('ExecStart='))
    for part in ['/opt/dockerforge/venv/bin/uvicorn app.main:app', '--port 9443',
                 '--ssl-certfile /etc/dockerforge/tls/fullchain.pem',
                 '--ssl-keyfile /etc/dockerforge/tls/privkey.pem']:
        assert part in exec_start


def test_tls_hook_requires_lineage():
    env = {k: v for k, v in os.environ.items() if k != 'RENEWED_LINEAGE'}
    r = subprocess.run(['bash', str(REPO / 'installer' / 'tls-deploy-hook.sh')],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 1


INSTALL = REPO / 'installer' / 'install.sh'
STEP_NAMES = ['step_preflight', 'step_packages', 'step_docker', 'step_user_dirs', 'step_app',
              'step_config', 'step_tls', 'step_services', 'step_firewall', 'step_verify']


def run_script(path, *args, env=None):
    return subprocess.run(['bash', str(path), *args], capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def test_install_help():
    r = run_script(INSTALL, '--help')
    assert r.returncode == 0
    assert '--domain' in r.stdout and '--check' in r.stdout


def test_install_domain_requires_email():
    r = run_script(INSTALL, '--domain', 'x.example.com')
    assert r.returncode == 2
    assert '--email is required' in r.stderr


def test_install_unknown_option():
    assert run_script(INSTALL, '--bogus').returncode == 2


def test_install_step_order():
    r = subprocess.run(['bash', '-c', f'source "{INSTALL}" --source-only; printf "%s\\n" "${{STEPS[@]}}"'],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == STEP_NAMES


def test_install_check_unsupported(tmp_path):
    arch = os_release(tmp_path, 'ID=arch\n')
    r = run_script(INSTALL, '--check', env={'DOCKERFORGE_OS_RELEASE': str(arch)})
    assert r.returncode == 1
    assert 'Unsupported distribution' in r.stderr


def test_backend_requirements():
    r = sh(f'backend_requirements "{sys.executable}" "{REPO / "backend" / "pyproject.toml"}"')
    assert r.returncode == 0, r.stderr
    assert r.stdout.split('\n')[:4] == ['fastapi>=0.110,<1', 'uvicorn>=0.27,<1', 'argon2-cffi>=23,<26', 'pydantic>=2,<3']
