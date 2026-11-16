#!/usr/bin/env bash
# PostgreSQL backup for the compose stack. Keeps the last $KEEP dumps in $BACKUP_DIR.
#   ./deploy/backup.sh                    # from the repository root on the server
#   cron: 15 3 * * * cd /opt/polypilot && ./deploy/backup.sh >> /var/log/polypilot-backup.log 2>&1
# Restore (into a NEW database first, verify, then switch):
#   docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod exec -T db \
#     psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE polypilot_restore"
#   docker compose ... exec -T db pg_restore -U "$POSTGRES_USER" -d polypilot_restore --no-owner < backup.dump
set -euo pipefail
cd "$(dirname "$0")/.."
BACKUP_DIR=${BACKUP_DIR:-/var/backups/polypilot}
KEEP=${KEEP:-14}
DC="docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod"
U=$(grep '^POSTGRES_USER=' deploy/.env.prod | cut -d= -f2)
D=$(grep '^POSTGRES_DB=' deploy/.env.prod | cut -d= -f2)
mkdir -p "$BACKUP_DIR" && chmod 700 "$BACKUP_DIR"
OUT="$BACKUP_DIR/polypilot-$(date -u +%Y%m%dT%H%M%SZ).dump"
$DC exec -T db pg_dump -U "$U" -d "$D" -Fc > "$OUT.partial"
# Verify the archive is readable before accepting it.
$DC exec -T db pg_restore --list < "$OUT.partial" > /dev/null
mv "$OUT.partial" "$OUT" && chmod 600 "$OUT"
ls -1t "$BACKUP_DIR"/polypilot-*.dump | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "backup ok: $OUT ($(du -h "$OUT" | cut -f1))"
