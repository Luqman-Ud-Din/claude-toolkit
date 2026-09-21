# Fixture: Inventory.Api (.NET 8)

Planted issues (each marked with a `LEAK (...)` comment):
- `Services/ReportService.cs` Export - FileStream never disposed (DISP).
- `Services/RequestAudit.cs` - static List that only grows (STAT).
- `Services/ProductCache.cs` Remember + `Program.cs` AddMemoryCache() - cache with no size limit, no expiration, user-keyed (CACHE).
- `Workers/StockSyncWorker.cs` - BackgroundService with an empty catch and a per-instance list appended every iteration (BG).

Negatives that must NOT be flagged: `ReadTemplateAsync` (await using), `SubmitAsync` (IHttpClientFactory + using response), `_routeNames` (bounded static readonly), `GetOrLoad` (SetSize + SlidingExpiration).
