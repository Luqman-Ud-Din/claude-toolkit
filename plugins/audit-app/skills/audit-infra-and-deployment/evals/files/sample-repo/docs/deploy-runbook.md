# Deployment runbook

## Deploy
1. Build and push the API image: `docker build -t registry.example.com/inventory/api:latest Api/`
2. Apply manifests: `kubectl apply -f deploy/k8s/`

## Rollback
If a release is bad, rebuild the previous commit, push it as `latest` and re-apply
the manifests. This has not been rehearsed yet.

## Backups
The SQL Server database is backed up nightly by the hosting provider.
Restore procedure: TBD.
