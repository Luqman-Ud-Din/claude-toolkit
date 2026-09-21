# Fixture: shop-api (Express + Prisma) and shop-web (Angular)

Planted issues (each marked with a `PERF (...)` comment):
- `api/src/orders.service.ts` create - three independent upstream calls awaited in series (SEQ).
- `api/src/products.routes.ts` GET /api/products - full entities, no select/take, and `api/src/app.ts` has no compression middleware (PAYLOAD + COMPRESS).
- `api/src/app.ts` - express-session with the default in-process MemoryStore, no `store:` (STATE - blocks horizontal scaling).
- `web/src/app/dashboard/dashboard.component.ts` - the same `GET /api/products` issued five times on load (CALLS-PER-PAGE).

Negatives that must NOT be flagged: `OrdersService.availability` (Promise.all), `GET /api/products/summary` (select + take + Cache-Control), `UnitsService.getUnits` (shareReplay cache), axios clients created with `timeout`.
