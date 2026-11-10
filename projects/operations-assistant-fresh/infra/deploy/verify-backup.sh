#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
folder=${1:?Usage: bash verify-backup.sh backups/TIMESTAMP}
(cd -- "$folder" && sha256sum -c SHA256SUMS)
temporary="restore_check_$(date +%s)_$RANDOM"
cleanup() {
  bash dc.sh exec -T mysql sh -c 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; mysql -uroot -e "DROP DATABASE IF EXISTS \`$1\`"' sh "$temporary"
  if [[ -f "$folder/knowledge.dump" ]]; then
    bash dc.sh exec -T postgres dropdb -U postgres --if-exists "$temporary"
  fi
}
trap cleanup EXIT
bash dc.sh exec -T mysql sh -c 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; mysql -uroot -e "CREATE DATABASE \`$1\` CHARACTER SET utf8mb4"' sh "$temporary"
bash restore.sh --target mysql --file "$folder/mysql.sql" --database "$temporary" --execute --confirm "$temporary"
bash dc.sh exec -T mysql sh -c 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; mysql -uroot "$1" -e "SELECT COUNT(*) inventory_rows FROM ops_inventory; SELECT COUNT(*) automation_runs FROM ops_automation_runs"' sh "$temporary"
if [[ -f "$folder/knowledge.dump" ]]; then
  bash dc.sh exec -T postgres createdb -U postgres "$temporary"
  bash restore.sh --target postgres --file "$folder/knowledge.dump" --database "$temporary" --execute --confirm "$temporary"
  bash dc.sh exec -T postgres psql -X -v ON_ERROR_STOP=1 -U postgres -d "$temporary" -c 'SELECT count(*) FROM knowledge_documents; SELECT count(*) FROM knowledge_chunks;'
fi
echo 'Backup checksum, temporary restore and table queries passed'
