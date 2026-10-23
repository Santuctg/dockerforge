#!/usr/bin/env bash
set -Eeuo pipefail
printf 'Version: '; grep '^version' /opt/dockerforge/backend/pyproject.toml
printf 'Main: '; systemctl is-active dockerforge
printf 'Collector: '; systemctl is-active dockerforge-metrics
printf 'Health: '; curl -kfsS --max-time 4 https://127.0.0.1:9443/health; echo
printf 'Collector status: '; python3 - <<'PY'
import json
with open('/var/lib/dockerforge/metrics-collector.json') as f: s=json.load(f)
print(s.get('state'), '| collected', s.get('collected'), '| failed',s.get('failed'))
PY
