#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
out="backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p -- "$out"
bash dc.sh exec -T mysql sh -c 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysqldump -uroot --single-transaction --routines --triggers --no-tablespaces --set-gtid-purged=OFF "$MYSQL_DATABASE"' > "$out/mysql.sql"
if bash dc.sh ps --services --status running | grep -qx postgres; then
  bash dc.sh exec -T postgres sh -c 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$out/knowledge.dump"
fi
(cd -- "$out" && sha256sum mysql.sql > SHA256SUMS && { test ! -f knowledge.dump || sha256sum knowledge.dump >> SHA256SUMS; })
printf 'Backup completed: %s\n' "$out"
