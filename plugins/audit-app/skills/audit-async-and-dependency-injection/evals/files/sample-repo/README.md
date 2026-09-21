# Fixture: Billing.Api (.NET 8)

Planted issues (each marked with an `ASYNC (...)` comment):
- `Services/InvoiceService.cs` PostSync - `.Result` and `GetAwaiter().GetResult()` on async calls (BLOCK).
- `Services/InvoiceService.cs` NotifyPosted - `async void`, errors lost (VOID).
- `Program.cs` + `Services/ReportCache.cs` - `AddSingleton<ReportCache>` whose constructor takes the scoped `BillingDbContext` (DI captive scoped).
- `Controllers/InvoicesController.cs` Pdf - `new HttpClient()` inside a request handler (HTTP).

Negatives that must NOT be flagged: `InvoiceService.PostAsync` (async + token), `TaxRateCache` (singleton with `IServiceScopeFactory` + `IMemoryCache` only), `FbrClient` (typed client via `AddHttpClient` with Timeout), `InvoicesController.Post` (async action with `CancellationToken`).
