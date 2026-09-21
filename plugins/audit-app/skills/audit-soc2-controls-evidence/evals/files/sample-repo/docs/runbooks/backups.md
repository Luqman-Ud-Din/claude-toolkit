# Database backups

- `infra/backup.sh` runs nightly from cron on the database host.
- Dumps are gzipped, uploaded to `s3://acme-db-backups/inventory/` with server-side encryption, and kept for 30 days locally.
- S3 lifecycle rule keeps objects for 90 days.

## Restore

To restore, download the latest dump and run `gunzip -c dump.sql.gz | psql "$DATABASE_URL"`.
