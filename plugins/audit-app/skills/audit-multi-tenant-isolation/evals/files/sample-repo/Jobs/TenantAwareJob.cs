using Microsoft.EntityFrameworkCore;
using Saas.Api.Data;

namespace Saas.Api.Jobs;

// Negative: a background job that carries tenant context explicitly. Must NOT be flagged.
// The scheduler passes the tenant id, and every query filters by it.
public class TenantAwareJob
{
    private readonly AppDbContext _db;
    public TenantAwareJob(AppDbContext db) => _db = db;

    public void Run(int tenantId)
    {
        var invoices = _db.Invoices.IgnoreQueryFilters()
            .Where(i => i.TenantId == tenantId)   // explicit per-tenant scope
            .ToList();
        _ = invoices.Count;
    }
}
