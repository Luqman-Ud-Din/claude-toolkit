#!/usr/bin/env bash
# Nightly database backup - runs from cron at 02:00 UTC on the db host.
set -euo pipefail
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
pg_dump "$DATABASE_URL" | gzip > "/var/backups/inventory-$STAMP.sql.gz"
aws s3 cp "/var/backups/inventory-$STAMP.sql.gz" "s3://acme-db-backups/inventory/" --sse AES256
# retention: keep 30 days
find /var/backups -name 'inventory-*.sql.gz' -mtime +30 -delete
