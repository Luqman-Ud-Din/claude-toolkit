# OrderService

Order import and pricing API for the retail and wholesale channels.

## Projects

- `OrderService.Api/` - HTTP API (controllers, pricing, import)
- `OrderService.Worker/` - background import worker (Hangfire)

## Run

```bash
dotnet run --project OrderService.Api
```

See `docs/runbook.md` for on-call steps.
