#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# -eq 1 ]] || { echo "Usage: $0 /root/dockerforge-upgrade-backup-TIMESTAMP" >&2; exit 2; }
DIR="$(realpath -e -- "$1")"
[[ -d "$DIR/backend/app" && -f "$DIR/dockerforge.db" ]] || { echo 'Missing backend or primary database' >&2; exit 1; }
python3 - "$DIR" <<'PYVERIFY'
import sqlite3,sys,os
from pathlib import Path
root=Path(sys.argv[1]);files=['dockerforge.db']
if (root/'metrics.db').exists():files.append('metrics.db')
for name in files:
    db=sqlite3.connect(f'file:{root/name}?mode=ro',uri=True)
    result=db.execute('PRAGMA integrity_check').fetchone()[0]
    db.close()
    print(f'{name}: {result}')
    if result!='ok':raise SystemExit(1)
for name in ('etc-dockerforge','stacks'):
    print(f'{name}:', 'present' if (root/name).exists() else 'not included')
PYVERIFY
