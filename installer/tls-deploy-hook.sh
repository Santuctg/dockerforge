#!/usr/bin/env bash
# certbot --deploy-hook: copy the renewed certificate where the dockerforge user can read it.
set -Eeuo pipefail
[[ -n ${RENEWED_LINEAGE:-} ]] || { echo 'RENEWED_LINEAGE not set; run from certbot' >&2; exit 1; }
TLS_DIR=${DOCKERFORGE_TLS_DIR:-/etc/dockerforge/tls}
for name in fullchain.pem privkey.pem; do
  [[ -f $RENEWED_LINEAGE/$name ]] || { echo "Missing $RENEWED_LINEAGE/$name" >&2; exit 1; }
done
install -d -m 0750 -o root -g dockerforge "$TLS_DIR"
for name in fullchain.pem privkey.pem; do
  install -m 0640 -o root -g dockerforge "$RENEWED_LINEAGE/$name" "$TLS_DIR/$name"
done
systemctl try-restart dockerforge
