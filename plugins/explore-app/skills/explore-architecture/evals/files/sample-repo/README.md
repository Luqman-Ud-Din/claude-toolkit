# Orderly

Order and stock management API for a small wholesaler.

## Architecture (as documented)

Clean layered design: `routes -> controllers -> services -> models`. Services never
import each other; all cross-service coordination happens in controllers.
Business rules live exclusively in the `services/` layer. Integrations are behind
the `integrations/` folder and are swappable.

Deployment: single Docker container + Postgres, eu-west-1.
