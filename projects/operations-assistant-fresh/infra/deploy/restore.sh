#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
target= file= database= confirm= execute=false
while (($#)); do
  case "$1" in
    --target) target=${2:?}; shift 2;;
    --file) file=${2:?}; shift 2;;
    --database) database=${2:?}; shift 2;;
    --confirm) confirm=${2:?}; shift 2;;
    --execute) execute=true; shift;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2;;
  esac
done
[[ "$target" == mysql || "$target" == postgres ]] && [[ -f "$file" ]] && [[ "$database" =~ ^[a-z][a-z0-9_]{0,62}$ ]] || { echo 'Required: --target mysql|postgres --file PATH --database NAME'; exit 2; }
printf 'Restore preview: service=%s database=%s file=%s bytes=%s\n' "$target" "$database" "$file" "$(wc -c < "$file")"
if [[ "$execute" == false ]]; then exit 0; fi
[[ "$confirm" == "$database" ]] || { echo 'Execution requires --confirm matching --database'; exit 2; }
if [[ "$target" == mysql ]]; then
  bash dc.sh exec -T mysql sh -c 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql -uroot "$1"' sh "$database" < "$file"
else
  bash dc.sh exec -T postgres sh -c 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_restore -U "$POSTGRES_USER" --exit-on-error --no-owner -d "$1"' sh "$database" < "$file"
  # ES索引可从PG正文重建；恢复后登记全部文档，下一次检索或同步CLI重建关键词索引。
  bash dc.sh exec -T postgres psql -X -v ON_ERROR_STOP=1 -U postgres -d "$database" -c 'INSERT INTO knowledge_search_jobs(document_id,revision,deleted) SELECT id,revision,false FROM knowledge_documents ON CONFLICT(document_id) DO UPDATE SET revision=EXCLUDED.revision,deleted=false,queued_at=now();'
fi
printf 'Restore completed: %s\n' "$database"
