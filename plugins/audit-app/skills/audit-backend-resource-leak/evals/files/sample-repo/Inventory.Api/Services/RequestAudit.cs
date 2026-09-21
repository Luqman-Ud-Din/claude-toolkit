namespace Inventory.Api.Services;

/// Registered as a singleton. Every request appends; nothing ever removes.
public class RequestAudit
{
    // LEAK (STAT): static list grows for the life of the process, one entry per request.
    private static readonly List<string> _requests = new();

    // OK: bounded, initialised once, never written - must NOT be flagged.
    private static readonly Dictionary<string, string> _routeNames = new()
    {
        ["products"] = "Products",
        ["orders"] = "Orders",
    };

    public void Record(HttpContext ctx)
    {
        _requests.Add($"{DateTime.UtcNow:o} {ctx.TraceIdentifier} {ctx.Request.Path}");
    }

    public int Count => _requests.Count;
    public string? NameFor(string route) => _routeNames.GetValueOrDefault(route);
}
