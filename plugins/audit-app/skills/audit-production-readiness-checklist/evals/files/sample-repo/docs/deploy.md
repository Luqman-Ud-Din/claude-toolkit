# Deploying Ledger

1. Merge to `main`.
2. The pipeline builds the image and pushes it to the registry.
3. `docker compose up -d api` on the production host.

That's it.
