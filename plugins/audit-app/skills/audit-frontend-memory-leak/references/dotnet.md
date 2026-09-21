# .NET / C# reference for audit-frontend-memory-leak

This skill audits frontend memory. An ASP.NET Core backend in the same repo
matters here only as the *server end* of long-lived client connections: if the
client leaks a SignalR/WebSocket/SSE connection per navigation, the server
accumulates one per leak too, and the server-side design decides how visible
that becomes. Check the items below; everything else server-side belongs to
`audit-backend-resource-leak`.

## Stack markers

`*.csproj` with `Microsoft.AspNetCore.SignalR` (or the framework-bundled hub support),
`app.MapHub<T>(...)`, `app.UseWebSockets()`, endpoints returning `text/event-stream`.
Frontend counterpart: `@microsoft/signalr` in `package.json`, `HubConnectionBuilder`.

## Where the relevant code lives

`Hubs/*.cs`, `Program.cs` (`AddSignalR`, `MapHub`, `UseWebSockets`), any controller writing
`text/event-stream`, `BackgroundJobs/` or `IHostedService` implementations that push to
clients via `IHubContext<T>`; on the client, `core/services/signalr*.service.ts` or
`lib/socket.ts`.

## Dangerous / interesting APIs and patterns (this skill's slice only)

- A hub with no `OnDisconnectedAsync` cleanup while it stores per-connection state in a
  static `Dictionary`/`ConcurrentDictionary` (`_connections[Context.ConnectionId] = ...`):
  every client-side leaked connection becomes a server-side leaked entry.
- `Groups.AddToGroupAsync` in `OnConnectedAsync` per tenant/branch without a bound on how many
  connections one user can hold - a leaking client multiplies group fan-out cost.
- No `KeepAliveInterval`/`ClientTimeoutInterval` tuning and no `MaximumReceiveMessageSize`:
  leaked idle connections hang around until the default 30 s timeout, which is fine, but a
  client that keeps a reference and *reconnects* (`withAutomaticReconnect`) each navigation
  never times out.
- SSE endpoints (`Response.ContentType = "text/event-stream"`) that loop `while (true)` without
  honouring `HttpContext.RequestAborted`: a client that navigates away leaks a server loop.
- Server pushing unbounded payloads (`Clients.All.SendAsync("rows", entireTable)`) - the client
  buffers them per leaked handler; note it in the client finding's Impact.

## What "good" looks like

```csharp
public class InventoryHub : Hub
{
    private static readonly ConcurrentDictionary<string, string> _tenantByConnection = new();
    public override async Task OnConnectedAsync()
    {
        var tenant = Context.User!.FindFirst("tenant")!.Value;
        _tenantByConnection[Context.ConnectionId] = tenant;
        await Groups.AddToGroupAsync(Context.ConnectionId, tenant);
    }
    public override Task OnDisconnectedAsync(Exception? ex)
    {
        _tenantByConnection.TryRemove(Context.ConnectionId, out _);
        return base.OnDisconnectedAsync(ex);
    }
}
// SSE
while (!ct.IsCancellationRequested) { await WriteEventAsync(...); await Task.Delay(1000, ct); }
```
Client pairing (Angular): one `HubConnection` in a `providedIn: 'root'` service, `start()` once
after login, `stop()` on logout; components use `connection.on(name, handler)` in init and
`connection.off(name, handler)` in destroy.

## Manual trace checklist

1. Find the hub(s) and the client service that builds the connection. Is the connection created
   once per session or once per component instance? The latter is the client finding; the
   server file is Evidence for the Impact.
2. `OnDisconnectedAsync` present and removing everything `OnConnectedAsync` added?
3. SSE/long-poll endpoints observe `RequestAborted`?
4. Any server-side per-connection cache keyed by connection id: bounded and cleaned?

## Stack-specific false positives

- A hub with no per-connection state at all needs no `OnDisconnectedAsync` override.
- `IHubContext<T>` used from a background job: not a leak by itself.
- `withAutomaticReconnect()` on the client is correct when there is exactly one connection.

## Tooling

`dotnet-counters monitor --counters Microsoft.AspNetCore.Http.Connections` (current-connections)
while the frontend heap-snapshot procedure runs: a server connection count that climbs with each
navigation confirms the client leak from the other side.

## Deferred to sibling skills

Everything else server-side (DbContext lifetime, HttpClient, streams, timers, hosted services):
`audit-backend-resource-leak`. Hub authorization and tenant isolation:
`audit-authz-and-access-control`, `audit-multi-tenant-isolation`.

## References

SignalR hubs lifetime: https://learn.microsoft.com/aspnet/core/signalr/hubs; SignalR JS client
`off`: https://learn.microsoft.com/aspnet/core/signalr/javascript-client; CWE-401, CWE-772, CWE-400.
