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
              'step_config', 'step_firewall', 'step_tls', 'step_services', 'step_verify']


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


UNINSTALL = REPO / 'installer' / 'uninstall.sh'


def test_uninstall_help():
    r = run_script(UNINSTALL, '--help')
    assert r.returncode == 0
    assert '--purge' in r.stdout


def test_uninstall_unknown_option():
    assert run_script(UNINSTALL, '--bogus').returncode == 2


# --- final review fixes: install.sh functions run against stubbed system commands ---

def run_install_fn(tmp_path, body, stubs=None):
    """Source install.sh, override system commands with recording stubs, run body."""
    bindir = tmp_path / 'bin'
    bindir.mkdir(exist_ok=True)
    log = tmp_path / 'calls.log'
    for name, code in (stubs or {}).items():
        stub = bindir / name
        stub.write_text(f'#!/bin/bash\necho "{name} $*" >> "{log}"\n{code}\n')
        stub.chmod(0o755)
    script = (f'source "{INSTALL}" --source-only; set +e; '
              f'pkg_install() {{ echo "pkg_install $*" >> "{log}"; }}; '
              f'PATH="{bindir}:$PATH"; {body}')
    r = subprocess.run(['bash', '-c', script], capture_output=True, text=True)
    return r, (log.read_text() if log.exists() else '')


def test_firewall_runs_before_tls():
    r = subprocess.run(['bash', '-c', f'source "{INSTALL}" --source-only; printf "%s\\n" "${{STEPS[@]}}"'],
                       capture_output=True, text=True)
    steps = r.stdout.split()
    assert steps.index('step_firewall') < steps.index('step_tls')


def test_docker_install_method():
    cases = [('debian', 'ubuntu', 'get.docker.com'), ('rhel', 'fedora', 'get.docker.com'),
             ('rhel', 'rocky', 'docker-ce-repo'), ('rhel', 'almalinux', 'docker-ce-repo'),
             ('rhel', 'rhel', 'docker-ce-repo'), ('suse', 'opensuse-leap', 'zypper')]
    for family, os_id, method in cases:
        r = subprocess.run(['bash', '-c', f'source "{INSTALL}" --source-only; docker_install_method {family} {os_id}'],
                           capture_output=True, text=True)
        assert r.stdout.strip() == method, (family, os_id, r.stderr)


def test_existing_docker_gets_only_compose_plugin(tmp_path):
    r, calls = run_install_fn(tmp_path, 'FAMILY=debian; OS_ID=ubuntu; ASSUME_YES=1; step_docker',
                              {'docker': '[[ "$1" == compose ]] && exit 1; exit 0',
                               'curl': 'exit 0', 'systemctl': 'exit 0'})
    assert 'pkg_install docker-compose-plugin' in calls or 'pkg_install docker-compose-v2' in calls
    assert 'curl ' not in calls


def test_renew_timer_installed_when_distro_has_none(tmp_path):
    unit_dir = tmp_path / 'units'
    unit_dir.mkdir()
    r, calls = run_install_fn(tmp_path, f'SYSTEMD_DIR="{unit_dir}"; ensure_renew_timer',
                              {'systemctl': '[[ "$1" == list-unit-files ]] && exit 0; exit 0'})
    assert r.returncode == 0, r.stderr
    assert (unit_dir / 'dockerforge-certbot-renew.timer').is_file()
    assert 'certbot renew' in (unit_dir / 'dockerforge-certbot-renew.service').read_text()
    assert 'systemctl enable --now dockerforge-certbot-renew.timer' in calls


def test_renew_timer_uses_distro_timer(tmp_path):
    unit_dir = tmp_path / 'units'
    unit_dir.mkdir()
    r, calls = run_install_fn(tmp_path, f'SYSTEMD_DIR="{unit_dir}"; ensure_renew_timer',
                              {'systemctl': '[[ "$1" == list-unit-files ]] && { echo "certbot-renew.timer disabled enabled"; exit 0; }; exit 0'})
    assert 'systemctl enable --now certbot-renew.timer' in calls
    assert not (unit_dir / 'dockerforge-certbot-renew.timer').exists()


def test_stage_backend_excludes_tests_and_caches(tmp_path):
    src = tmp_path / 'src'
    (src / 'app' / '__pycache__').mkdir(parents=True)
    (src / 'app' / 'core.py').write_text('x')
    (src / 'app' / '__pycache__' / 'core.pyc').write_text('x')
    (src / 'tests').mkdir()
    (src / '.pytest_cache').mkdir()
    (src / 'pyproject.toml').write_text('x')
    dest = tmp_path / 'dest'
    r = subprocess.run(['bash', '-c', f'source "{INSTALL}" --source-only; stage_backend "{src}" "{dest}"'],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (dest / 'app' / 'core.py').is_file() and (dest / 'pyproject.toml').is_file()
    assert not (dest / 'tests').exists() and not (dest / '.pytest_cache').exists()
    assert not (dest / 'app' / '__pycache__').exists()
    if os.geteuid() == 0:
        assert all(p.stat().st_uid == 0 for p in [dest, *dest.rglob('*')])


def test_rhel_skips_curl_when_present(tmp_path):
    r, calls = run_install_fn(tmp_path, 'FAMILY=rhel; OS_ID=rocky; DOMAIN=; find_python() { echo /usr/bin/python3; }; step_packages',
                              {'curl': 'exit 0'})
    line = next(l for l in calls.splitlines() if l.startswith('pkg_install'))
    assert 'curl' not in line.split()


def test_rollback_before_swap_leaves_live_code(tmp_path):
    app = tmp_path / 'live'
    app.mkdir()
    (app / 'marker').write_text('live')
    backup = tmp_path / 'backup'
    (backup / 'backend').mkdir(parents=True)
    r, calls = run_install_fn(tmp_path, f'APP="{app}"; BACKUP="{backup}"; APP_SWAPPED=0; rollback',
                              {'systemctl': 'exit 0'})
    assert (app / 'marker').read_text() == 'live'
    assert 'systemctl restart' not in calls


def test_step_config_fails_when_token_generation_fails(tmp_path):
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    (bindir / 'openssl').write_text('#!/bin/sh\nexit 1\n')
    (bindir / 'openssl').chmod(0o755)
    conf = tmp_path / 'conf'
    conf.mkdir()
    (conf / 'data-backup.json').write_text('{}')
    env = conf / 'dockerforge.env'
    script = (f'source "{INSTALL}" --source-only; PATH="{bindir}:$PATH"; CONF="{conf}"; '
              f'ENV_FILE="{env}"; chown() {{ :; }}; step_config')
    r = subprocess.run(['bash', '-c', script], capture_output=True, text=True)
    assert r.returncode != 0
    assert not env.exists()


def test_service_user_gets_own_group(tmp_path):
    r, calls = run_install_fn(tmp_path, 'install() { :; }; step_user_dirs',
                              {'getent': 'exit 2', 'useradd': 'exit 0', 'usermod': 'exit 0'})
    useradd = next(l for l in calls.splitlines() if l.startswith('useradd'))
    assert '--user-group' in useradd.split() or '-U' in useradd.split()
