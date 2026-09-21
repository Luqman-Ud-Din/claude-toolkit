using System.Security.Claims;

namespace Saas.Api.Infrastructure;

// Tenancy model: shared database, TenantId column on every tenant-owned table.
// Current tenant is resolved from the authenticated token claim, never from input.
public interface ITenantContext { int TenantId { get; } }

public class ClaimTenantContext : ITenantContext
{
    private readonly IHttpContextAccessor _http;
    public ClaimTenantContext(IHttpContextAccessor http) => _http = http;
    public int TenantId =>
        int.Parse(_http.HttpContext!.User.FindFirstValue("tenant_id")!);
}
